import contextlib
from collections.abc import Iterator, Sequence

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
    state_defs: dict[ContractReference, dict[str, AppStorageDeclaration]] = attrs.field(
        factory=dict
    )

    def for_module(self, current_module: mypy.nodes.MypyFile) -> "ASTConversionModuleContext":
        return attrs_extend(ASTConversionModuleContext, self, current_module=current_module)

    def register_pytype(self, typ: pytypes.PyType, *, alias: str | None = None) -> None:
        name = alias or typ.name
        existing_entry = self._pytypes.get(name)
        if existing_entry is None:
            self._pytypes[name] = typ
        elif existing_entry is typ:
            logger.debug(f"Duplicate registration of {typ}")
        else:
            raise InternalError(f"Duplicate mapping of {name}")

    def lookup_pytype(self, name: str) -> pytypes.PyType | None:
        """Lookup type by the canonical fully qualified name"""
        return self._pytypes.get(name)


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
            case mypy.types.AnyType():
                # TODO: look at type_of_any to improve error message
                raise CodeError("Any type is not supported", loc)
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
