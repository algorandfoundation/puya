import contextlib
from collections.abc import Iterator, Mapping, Sequence

import attrs
import mypy.nodes
import mypy.types

from puya import log
from puya.awst.nodes import ConstantValue, ContractReference
from puya.awst_build import pytypes
from puya.awst_build.contract_data import AppStorageDeclaration
from puya.awst_build.exceptions import TypeUnionError
from puya.context import CompileContext
from puya.errors import CodeError, InternalError, log_exceptions
from puya.parse import SourceLocation
from puya.utils import attrs_extend

logger = log.get_logger(__name__)


@attrs.frozen(kw_only=True)
class ASTConversionContext(CompileContext):
    constants: dict[str, ConstantValue] = attrs.field(factory=dict)
    _pytypes: dict[str, pytypes.PyType] = attrs.field(factory=pytypes.builtins_registry)
    _state_defs: dict[ContractReference, dict[str, AppStorageDeclaration]] = attrs.field(
        factory=dict
    )

    def for_module(self, current_module: mypy.nodes.MypyFile) -> "ASTConversionModuleContext":
        return attrs_extend(ASTConversionModuleContext, self, current_module=current_module)

    def state_defs(self, cref: ContractReference) -> Mapping[str, AppStorageDeclaration]:
        return self._state_defs[cref]

    def set_state_defs(
        self, cref: ContractReference, data: dict[str, AppStorageDeclaration]
    ) -> None:
        if cref in self._state_defs:
            raise InternalError(f"Tried to reinitialise state defs for {cref.full_name}")
        self._state_defs[cref] = data

    def add_state_def(self, cref: ContractReference, decl: AppStorageDeclaration) -> None:
        for_contract = self._state_defs.get(cref)
        if for_contract is None:
            logger.error(
                f"Failed to look up state definition of {cref.full_name}",
                location=decl.source_location,
            )
        else:
            existing_def = for_contract.get(decl.member_name)
            if existing_def:
                logger.info(
                    f"Previous definition of {decl.member_name} was here",
                    location=existing_def.source_location,
                )
                logger.error(
                    f"Redefinition of {decl.member_name}",
                    location=decl.source_location,
                )
            for_contract[decl.member_name] = decl

    def register_pytype(self, typ: pytypes.PyType, *, alias: str | None = None) -> None:
        name = alias or typ.name
        existing_entry = self._pytypes.get(name)

        if existing_entry is typ:
            logger.debug(f"Duplicate registration of {typ}")
        else:
            if existing_entry is not None:
                logger.error(f"Redefinition of type {name}")
            self._pytypes[name] = typ

    def lookup_pytype(self, name: str) -> pytypes.PyType | None:
        """Lookup type by the canonical fully qualified name"""
        return self._pytypes.get(name)

    def require_ptype(self, name: str, source_location: SourceLocation) -> pytypes.PyType:
        try:
            return self._pytypes[name]
        except KeyError:
            raise CodeError(f"Unknown type {name}", source_location) from None


@attrs.frozen(kw_only=True)
class ASTConversionModuleContext(ASTConversionContext):
    current_module: mypy.nodes.MypyFile

    @property
    def module_name(self) -> str:
        return self.current_module.fullname

    @property
    def module_path(self) -> str:
        return self.current_module.path

    def node_location(
        self,
        node: mypy.nodes.Context,
        module_src: mypy.nodes.TypeInfo | None = None,
    ) -> SourceLocation:
        if not module_src:
            module_path = self.module_path
        else:
            module_name = module_src.module_name
            try:
                module_path = self.module_paths[module_name]
            except KeyError as ex:
                raise CodeError(f"Could not find module '{module_name}'") from ex
        loc = SourceLocation.from_mypy(file=module_path, node=node)
        lines = self.try_get_source(loc).code
        if loc.line > 1:
            prior_code = self.try_get_source(
                SourceLocation(file=module_path, line=1, end_line=loc.line - 1)
            ).code
            unchop = 0
            for line in reversed(prior_code or ()):
                if not line.strip().startswith("#"):
                    break
                unchop += 1
            if unchop:
                loc = attrs.evolve(loc, line=loc.line - unchop)
        if loc.end_line is not None and loc.end_line != loc.line:
            chop = 0
            for line in reversed(lines or ()):
                l_stripped = line.lstrip()
                if l_stripped and not l_stripped.startswith("#"):
                    break
                chop += 1
            if chop:
                loc = attrs.evolve(loc, end_line=loc.end_line - chop)
        return loc

    def _maybe_convert_location(
        self, location: mypy.nodes.Context | SourceLocation
    ) -> SourceLocation:
        if isinstance(location, mypy.nodes.Context):
            return self.node_location(location)
        return location

    def error(self, msg: str, location: mypy.nodes.Context | SourceLocation) -> None:
        logger.error(msg, location=self._maybe_convert_location(location))

    def info(self, msg: str, location: mypy.nodes.Context | SourceLocation) -> None:
        logger.info(msg, location=self._maybe_convert_location(location))

    def warning(self, msg: str, location: mypy.nodes.Context | SourceLocation) -> None:
        logger.warning(msg, location=self._maybe_convert_location(location))

    @contextlib.contextmanager
    def log_exceptions(
        self, fallback_location: mypy.nodes.Context | SourceLocation
    ) -> Iterator[None]:
        with log_exceptions(self._maybe_convert_location(fallback_location)):
            yield

    def mypy_expr_node_type(self, expr: mypy.nodes.Expression) -> pytypes.PyType:
        expr_loc = self.node_location(expr)
        if isinstance(expr, mypy.nodes.TupleExpr):
            # for some reason these don't appear in mypy type tables...
            item_types = [self.mypy_expr_node_type(it) for it in expr.items]
            return pytypes.GenericTupleType.parameterise(item_types, expr_loc)
        mypy_type = self.parse_result.manager.all_types.get(expr)
        if mypy_type is None:
            raise InternalError(f"mypy expression not present in type table: {expr}", expr_loc)
        return self.type_to_pytype(mypy_type, source_location=expr_loc)

    def type_to_pytype(
        self, mypy_type: mypy.types.Type, *, source_location: SourceLocation | mypy.nodes.Context
    ) -> pytypes.PyType:
        loc = self._maybe_convert_location(source_location)
        proper_type_or_alias: mypy.types.ProperType | mypy.types.TypeAliasType
        if isinstance(mypy_type, mypy.types.TypeAliasType):
            proper_type_or_alias = mypy_type
        else:
            proper_type_or_alias = mypy.types.get_proper_type(mypy_type)
        match proper_type_or_alias:
            case mypy.types.TypeAliasType(alias=alias, args=args):
                if alias is None:
                    raise InternalError("mypy type alias type missing alias reference", loc)
                result = self._pytypes.get(alias.fullname)
                if result is None:
                    return self.type_to_pytype(
                        mypy.types.get_proper_type(proper_type_or_alias), source_location=loc
                    )
                if args:
                    result = self._parameterise_pytype(result, args, loc)
                return result
            case mypy.types.Instance(args=args) as inst:
                fullname = inst.type.fullname
                result = self._pytypes.get(fullname)
                if result is None:
                    if fullname.startswith("builtins."):
                        msg = f"Unsupported builtin type: {fullname.removeprefix('builtins.')}"
                    else:
                        msg = f"Unknown type: {fullname}"
                    raise CodeError(msg, loc)
                if args:
                    result = self._parameterise_pytype(result, args, loc)
                return result
            case mypy.types.TupleType(items=items, partial_fallback=true_type):
                types = [self.type_to_pytype(it, source_location=loc) for it in items]
                generic = self._pytypes.get(true_type.type.fullname)
                if generic is None:
                    raise CodeError(f"Unknown tuple base type: {true_type.type.fullname}", loc)
                return generic.parameterise(types, loc)
            case mypy.types.LiteralType(fallback=fallback):
                return self.type_to_pytype(fallback, source_location=loc)
            case mypy.types.UnionType(items=items):
                types = [self.type_to_pytype(it, source_location=loc) for it in items]
                if not types:
                    raise CodeError("Cannot resolve empty type", loc)
                if len(types) == 1:
                    return types[0]
                else:
                    raise TypeUnionError(types, loc)
            case mypy.types.NoneType() | mypy.types.PartialType(type=None):
                return pytypes.NoneType
            case mypy.types.UninhabitedType():
                raise CodeError("Cannot resolve empty type", loc)
            case mypy.types.AnyType(type_of_any=type_of_any):
                msg = _type_of_any_to_error_message(type_of_any, loc)
                raise CodeError(msg, loc)
            case mypy.types.FunctionLike() as func_like:
                if func_like.is_type_obj():
                    msg = "References to type objects are not supported"
                else:
                    msg = "Function references are not supported"
                raise CodeError(msg, loc)
            case _:
                raise CodeError(
                    f"Unable to resolve mypy type {mypy_type!r} to known algopy type", loc
                )

    def _parameterise_pytype(
        self, generic: pytypes.PyType, inst_args: Sequence[mypy.types.Type], loc: SourceLocation
    ) -> pytypes.PyType:
        type_args_resolved = list[pytypes.TypeArg]()
        for idx, ta in enumerate(inst_args):
            if isinstance(ta, mypy.types.AnyType):
                raise CodeError(
                    f"Unresolved generic type parameter for {generic} at index {idx}", loc
                )
            if isinstance(ta, mypy.types.NoneType):
                type_args_resolved.append(None)
            elif isinstance(ta, mypy.types.LiteralType):
                if isinstance(ta.value, float):
                    raise CodeError(f"float value encountered in typing.Literal: {ta.value}", loc)
                type_args_resolved.append(ta.value)
            else:
                type_args_resolved.append(self.type_to_pytype(ta, source_location=loc))
        result = generic.parameterise(type_args_resolved, loc)
        return result


def _type_of_any_to_error_message(type_of_any: int, source_location: SourceLocation) -> str:
    from mypy.types import TypeOfAny

    match type_of_any:
        case TypeOfAny.unannotated:
            msg = "type annotation is required at this location"
        case TypeOfAny.explicit | TypeOfAny.from_another_any:
            msg = "Any type is not supported"
        case TypeOfAny.from_unimported_type:
            msg = "unknown type from import"
        case TypeOfAny.from_omitted_generics:
            msg = "type parameters are required at this location"
        case TypeOfAny.from_error:
            msg = "typing error prevents type resolution"
        case TypeOfAny.special_form:
            msg = "unsupported type form"
        case TypeOfAny.implementation_artifact | TypeOfAny.suggestion_engine:
            msg = "mypy cannot handle this type form, try providing an explicit annotation"
        case _:
            logger.debug(f"Unknown TypeOfAny value: {type_of_any}", location=source_location)
            msg = "Any type is not supported"
    return msg
