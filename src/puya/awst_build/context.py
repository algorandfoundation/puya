import ast
import contextlib
import functools
from collections.abc import Iterator, Mapping, Sequence

import attrs
import mypy.nodes
import mypy.types

from puya import log
from puya.awst.nodes import ConstantValue
from puya.awst_build import pytypes
from puya.awst_build.contract_data import AppStorageDeclaration
from puya.awst_build.exceptions import TypeUnionError
from puya.context import CompileContext
from puya.errors import CodeError, InternalError, log_exceptions
from puya.models import ContractReference
from puya.parse import ParseResult, SourceLocation
from puya.utils import attrs_extend

logger = log.get_logger(__name__)


@attrs.frozen(kw_only=True)
class ASTConversionContext(CompileContext):
    parse_result: ParseResult
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

    def type_to_pytype(
        self,
        mypy_type: mypy.types.Type,
        *,
        source_location: mypy.nodes.Context | SourceLocation,
        in_type_args: bool = False,
    ) -> pytypes.PyType:
        return type_to_pytype(
            self._pytypes,
            mypy_type,
            source_location=self._maybe_convert_location(source_location),
            in_type_args=in_type_args,
        )


def type_to_pytype(
    registry: Mapping[str, pytypes.PyType],
    mypy_type: mypy.types.Type,
    *,
    source_location: SourceLocation | None,
    in_type_args: bool = False,
    in_func_sig: bool = False,
) -> pytypes.PyType:
    loc = source_location
    proper_type_or_alias: mypy.types.ProperType | mypy.types.TypeAliasType
    if isinstance(mypy_type, mypy.types.TypeAliasType):
        proper_type_or_alias = mypy_type
    else:
        proper_type_or_alias = mypy.types.get_proper_type(mypy_type)
    recurse = functools.partial(
        type_to_pytype,
        registry,
        source_location=loc,
        in_type_args=in_type_args,
        in_func_sig=in_func_sig,
    )
    match proper_type_or_alias:
        case mypy.types.TypeAliasType(alias=alias, args=args):
            if alias is None:
                raise InternalError("mypy type alias type missing alias reference", loc)
            result = registry.get(alias.fullname)
            if result is None:
                return recurse(mypy.types.get_proper_type(proper_type_or_alias))
            return _maybe_parameterise_pytype(registry, result, args, loc)
        # this is how variadic tuples are represented in mypy types...
        case mypy.types.Instance(type=mypy.nodes.TypeInfo(fullname="builtins.tuple"), args=args):
            try:
                (arg,) = args
            except ValueError:
                raise InternalError(
                    f"mypy tuple type as instance had unrecognised args: {args}", loc
                ) from None
            if not in_func_sig:
                raise CodeError("variadic tuples are not supported", loc)
            return pytypes.VariadicTupleType(items=recurse(arg))
        case mypy.types.Instance(args=args) as inst:
            fullname = inst.type.fullname
            result = registry.get(fullname)
            if result is None:
                if fullname.startswith("builtins."):
                    msg = f"Unsupported builtin type: {fullname.removeprefix('builtins.')}"
                else:
                    msg = f"Unknown type: {fullname}"
                raise CodeError(msg, loc)
            return _maybe_parameterise_pytype(registry, result, args, loc)
        case mypy.types.TupleType(items=items, partial_fallback=true_type):
            generic = registry.get(true_type.type.fullname)
            if generic is None:
                raise CodeError(f"Unknown tuple base type: {true_type.type.fullname}", loc)
            return _maybe_parameterise_pytype(registry, generic, items, loc)
        case mypy.types.LiteralType(fallback=fallback, value=literal_value) as mypy_literal_type:
            if not in_type_args:
                # this is a bit clumsy, but exists because for some reason, bool types
                # can be "narrowed" down to a typing.Literal. e.g. in the case of:
                #   assert a
                #   assert a or b
                # then the type of `a or b` becomes typing.Literal[True]
                return recurse(fallback)
            if mypy_literal_type.is_enum_literal():
                raise CodeError("typing literals of enum are not supported", loc)
            our_literal_value: pytypes.TypingLiteralValue
            if fallback.type.fullname == "builtins.bytes":  # WHY^2
                bytes_literal_value = ast.literal_eval("b" + repr(literal_value))
                assert isinstance(bytes_literal_value, bytes)
                our_literal_value = bytes_literal_value
            elif isinstance(literal_value, float):  # WHY
                raise CodeError("typing literals with float values are not supported", loc)
            else:
                our_literal_value = literal_value
            return pytypes.TypingLiteralType(value=our_literal_value, source_location=loc)
        case mypy.types.UnionType(items=items):
            types = [recurse(it) for it in items]
            if not types:
                raise CodeError("Cannot resolve empty type", loc)
            if len(types) == 1:
                return types[0]
            else:
                raise TypeUnionError(types, loc)
        case mypy.types.NoneType() | mypy.types.PartialType(type=None):
            return pytypes.NoneType
        case mypy.types.UninhabitedType():
            return pytypes.NeverType
        case mypy.types.AnyType(type_of_any=type_of_any):
            msg = _type_of_any_to_error_message(type_of_any, loc)
            raise CodeError(msg, loc)
        case mypy.types.TypeType(item=inner_type):
            inner_pytype = recurse(inner_type)
            return pytypes.TypeType(inner_pytype)
        case mypy.types.FunctionLike() as func_like:
            if func_like.is_type_obj():
                # note sure if this will always work for overloads, but the only overloaded
                # constructor we have is arc4.StaticArray, so...
                ret_type = func_like.items[0].ret_type
                cls_typ = recurse(ret_type)
                return pytypes.TypeType(cls_typ)
            else:
                if not isinstance(func_like, mypy.types.CallableType):  # vs Overloaded
                    raise CodeError("References to overloaded functions are not supported", loc)
                ret_pytype = recurse(func_like.ret_type)
                func_args = []
                for at, name, kind in zip(
                    func_like.arg_types, func_like.arg_names, func_like.arg_kinds, strict=True
                ):
                    try:
                        pt = type_to_pytype(
                            registry,
                            at,
                            source_location=loc,
                            in_type_args=in_type_args,
                            in_func_sig=True,
                        )
                    except TypeUnionError as union:
                        pts = union.types
                    else:
                        pts = [pt]
                    func_args.append(pytypes.FuncArg(types=pts, kind=kind, name=name))
                if None in func_like.bound_args:
                    logger.debug(
                        "None contained in bound args for function reference", location=loc
                    )
                bound_args = [
                    type_to_pytype(
                        registry,
                        ba,
                        source_location=loc,
                        in_type_args=in_type_args,
                        in_func_sig=True,
                    )
                    for ba in func_like.bound_args
                    if ba is not None
                ]
                if func_like.definition is not None:
                    name = func_like.definition.fullname
                else:
                    name = repr(func_like)
                return pytypes.FuncType(
                    name=name,
                    args=func_args,
                    ret_type=ret_pytype,
                    bound_arg_types=bound_args,
                )
        case _:
            raise CodeError(f"Unable to resolve mypy type {mypy_type!r} to known algopy type", loc)


def _maybe_parameterise_pytype(
    registry: Mapping[str, pytypes.PyType],
    maybe_generic: pytypes.PyType,
    mypy_type_args: Sequence[mypy.types.Type],
    loc: SourceLocation | None,
) -> pytypes.PyType:
    if not mypy_type_args:
        return maybe_generic
    if all(isinstance(t, mypy.types.TypeVarType | mypy.types.UnpackType) for t in mypy_type_args):
        return maybe_generic
    type_args_resolved = [
        type_to_pytype(registry, mta, source_location=loc, in_type_args=True)
        for mta in mypy_type_args
    ]
    result = maybe_generic.parameterise(type_args_resolved, loc)
    return result


def _type_of_any_to_error_message(type_of_any: int, source_location: SourceLocation | None) -> str:
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
