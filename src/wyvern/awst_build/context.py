import contextlib
import typing as t
from collections.abc import Iterator, Mapping, Sequence

import attrs
import mypy.nodes
import mypy.types

from wyvern.awst import wtypes
from wyvern.awst.nodes import ConstantValue, Module
from wyvern.awst_build import constants as awst_constants
from wyvern.context import CompileContext
from wyvern.errors import CodeError, InternalError, WyvernError, crash_report
from wyvern.parse import SourceLocation
from wyvern.utils import attrs_extend


@attrs.frozen(kw_only=True)
class ASTConversionContext(CompileContext):
    module_asts: Mapping[str, Module]
    constants: dict[str, ConstantValue] = attrs.field(factory=dict)
    type_map: dict[str, wtypes.WType] = attrs.field(
        # TODO: rm hax?
        factory=lambda: {
            awst_constants.CLS_UINT64: wtypes.uint64_wtype,
            awst_constants.CLS_BIGUINT: wtypes.biguint_wtype,
            awst_constants.CLS_ADDRESS: wtypes.address_wtype,
            awst_constants.CLS_BYTES: wtypes.bytes_wtype,
            awst_constants.CLS_ABI_STRING: wtypes.abi_string_wtype,
            awst_constants.CLS_ASSET: wtypes.asset_wtype,
            "builtins.bool": wtypes.bool_wtype,
        }
    )
    generics_type_map: dict[
        str, t.Callable[[Sequence[wtypes.WType | mypy.types.LiteralValue]], wtypes.WType]
    ] = attrs.field(
        factory=lambda: {
            awst_constants.CLS_ARRAY: lambda args: wtypes.WArray.from_element_type(*args),
            awst_constants.CLS_ABI_DYNAMIC_ARRAY: (
                lambda args: wtypes.AbiDynamicArray.from_element_type(*args)
            ),
            awst_constants.CLS_ABI_STATIC_ARRAY: (
                lambda args: wtypes.AbiStaticArray.from_element_type_and_size(*args)
            ),
            awst_constants.CLS_ABI_UINTN: (lambda args: wtypes.AbiUIntN.from_scale(*args)),
        }
    )

    def for_module(self, current_module: mypy.nodes.MypyFile) -> "ASTConversionModuleContext":
        return attrs_extend(ASTConversionModuleContext, self, current_module=current_module)


@attrs.frozen(kw_only=True)
class ASTConversionModuleContext(ASTConversionContext):
    current_module: mypy.nodes.MypyFile

    @property
    def module_name(self) -> str:
        return self.current_module.fullname

    @property
    def module_path(self) -> str:
        return self.current_module.path

    def node_location(self, node: mypy.nodes.Context) -> SourceLocation:
        return SourceLocation.from_mypy(file=self.module_path, node=node)

    def _maybe_convert_location(
        self, location: mypy.nodes.Context | SourceLocation
    ) -> SourceLocation:
        if isinstance(location, mypy.nodes.Context):
            return self.node_location(location)
        return location

    def error(self, msg: str, location: mypy.nodes.Context | SourceLocation) -> None:
        self.errors.error(msg, self._maybe_convert_location(location))

    def note(self, msg: str, location: mypy.nodes.Context | SourceLocation) -> None:
        self.errors.note(msg, self._maybe_convert_location(location))

    def warning(self, msg: str, location: mypy.nodes.Context | SourceLocation) -> None:
        self.errors.warning(msg, self._maybe_convert_location(location))

    @contextlib.contextmanager
    def log_exceptions(
        self, fallback_location: mypy.nodes.Context | SourceLocation
    ) -> Iterator[None]:
        try:
            yield
        except CodeError as ex:
            self.error(str(ex), location=ex.location or fallback_location)
        except InternalError as ex:
            self.error(f"FATAL {ex!s}", location=ex.location or fallback_location)
            crash_report(ex.location or self._maybe_convert_location(fallback_location))
        except Exception as ex:
            self.error(f"UNEXPECTED {ex!s}", location=fallback_location)
            crash_report(self._maybe_convert_location(fallback_location))

    def type_to_wtype(
        self, typ: mypy.types.Type, *, source_location: SourceLocation | mypy.nodes.Context
    ) -> wtypes.WType:
        loc = self._maybe_convert_location(source_location)
        match mypy.types.get_proper_type(typ):
            case mypy.types.NoneType() | mypy.types.PartialType(type=None):
                return wtypes.void_wtype
            case mypy.types.LiteralType(fallback=fallback):
                return self.type_to_wtype(fallback, source_location=loc)
            case mypy.types.TupleType(items=items):
                types = [self.type_to_wtype(it, source_location=loc) for it in items]
                if wtypes.void_wtype in types:
                    raise CodeError("Tuples cannot contain None values", loc)
                return wtypes.WTuple.from_types(types)
            case mypy.types.Instance(type=mypy.nodes.TypeInfo(is_enum=True, bases=bases)):
                for base in bases:
                    try:
                        return self.type_to_wtype(base, source_location=loc)
                    except WyvernError:
                        pass
                raise CodeError("Cannot resolve enum type to an appropriate base type", loc)
            case mypy.types.Instance() as inst:
                return self.resolve_type_from_name_and_args(
                    type_fullname=inst.type.fullname,
                    inst_args=inst.args,
                    loc=loc,
                )
            case mypy.types.UninhabitedType():
                raise CodeError("Cannot resolve empty type", loc)
            case mypy.types.UnionType(items=items):
                if not items:
                    raise CodeError("Cannot resolve empty type", loc)
                elif len(items) == 1:
                    return self.type_to_wtype(items[0], source_location=loc)
                else:
                    raise CodeError("Type unions are unsupported at this location", loc)
            case mypy.types.AnyType():
                raise CodeError("Any type is not supported", loc)
            case _:
                raise CodeError(
                    f"Unable to resolve MyPy type {typ!r} to known AlgoPy type",
                    loc,
                )

    def resolve_type_from_name_and_args(
        self, type_fullname: str, inst_args: Sequence[mypy.types.Type] | None, loc: SourceLocation
    ) -> wtypes.WType:
        if not inst_args:
            try:
                return self.type_map[type_fullname]
            except KeyError as ex:
                raise CodeError(f"Unsupported type: {type_fullname}", loc) from ex
        wtype_callable = self.generics_type_map.get(type_fullname)
        if wtype_callable is None:
            raise CodeError(f"Unsupported generic type: {type_fullname}", loc)
        type_args_resolved = [
            ta.value
            if isinstance(ta, mypy.types.LiteralType)
            else self.type_to_wtype(ta, source_location=loc)
            for ta in inst_args
        ]
        try:
            return wtype_callable(type_args_resolved)
        except Exception as ex:
            raise CodeError(
                f"Invalid parametrisation of generic type: {type_fullname}"
                f" with {type_args_resolved}",
                loc,
            ) from ex

    def mypy_expr_node_type(self, expr: mypy.nodes.Expression) -> wtypes.WType:
        mypy_type = self.get_mypy_expr_type(expr)
        return self.type_to_wtype(mypy_type, source_location=self.node_location(expr))

    def get_mypy_expr_type(self, expr: mypy.nodes.Expression) -> mypy.types.Type:
        try:
            typ = self.parse_result.manager.all_types[expr]
        except KeyError as ex:
            raise InternalError(
                "MyPy Expression to MyPy Type lookup failed", self.node_location(expr)
            ) from ex
        return mypy.types.get_proper_type(typ)
