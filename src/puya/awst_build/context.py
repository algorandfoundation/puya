import contextlib
from collections.abc import Iterator, Sequence

import attrs
import mypy.nodes
import mypy.types

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    ConstantValue,
    ContractReference,
    Literal as AWSTLiteral,
)
from puya.awst_build import constants
from puya.awst_build.contract_data import AppStorageDeclaration
from puya.awst_build.eb.base import TypeClassExpressionBuilder
from puya.context import CompileContext
from puya.errors import CodeError, InternalError, log_exceptions
from puya.parse import SourceLocation
from puya.utils import attrs_extend

logger = log.get_logger(__name__)


@attrs.frozen(kw_only=True)
class ASTConversionContext(CompileContext):
    constants: dict[str, ConstantValue] = attrs.field(factory=dict)
    type_map: dict[str, wtypes.WStructType | wtypes.ARC4Struct] = attrs.field(factory=dict)

    def for_module(self, current_module: mypy.nodes.MypyFile) -> "ASTConversionModuleContext":
        return attrs_extend(ASTConversionModuleContext, self, current_module=current_module)


@attrs.frozen(kw_only=True)
class ASTConversionModuleContext(ASTConversionContext):
    current_module: mypy.nodes.MypyFile
    state_defs: dict[ContractReference, dict[str, AppStorageDeclaration]] = attrs.field(
        factory=dict
    )

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

    def type_to_wtype(
        self, typ: mypy.types.Type, *, source_location: SourceLocation | mypy.nodes.Context
    ) -> wtypes.WType:
        return self._type_to_builder(typ, source_location=source_location).produces()

    def _type_to_builder(
        self, typ: mypy.types.Type, *, source_location: SourceLocation | mypy.nodes.Context
    ) -> TypeClassExpressionBuilder:
        from puya.awst_build.eb.arc4.tuple import ARC4TupleClassExpressionBuilder
        from puya.awst_build.eb.tuple import TupleTypeExpressionBuilder
        from puya.awst_build.eb.void import VoidTypeExpressionBuilder

        loc = self._maybe_convert_location(source_location)
        proper_type = mypy.types.get_proper_type(typ)
        match proper_type:
            case mypy.types.NoneType() | mypy.types.PartialType(type=None):
                return VoidTypeExpressionBuilder(loc)
            case mypy.types.LiteralType(fallback=fallback):
                return self._type_to_builder(fallback, source_location=loc)
            case mypy.types.TupleType(items=items, partial_fallback=true_type):
                types = [self._type_to_builder(it, source_location=loc) for it in items]
                tuple_builder: TupleTypeExpressionBuilder | ARC4TupleClassExpressionBuilder
                if true_type.type.fullname != constants.CLS_ARC4_TUPLE:
                    tuple_builder = TupleTypeExpressionBuilder(loc)
                else:
                    tuple_builder = ARC4TupleClassExpressionBuilder(loc)
                return tuple_builder.index_multiple(types, loc)
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
                if len(items) > 1:
                    raise CodeError("Type unions are unsupported at this location", loc)
                return self._type_to_builder(items[0], source_location=loc)
            case mypy.types.AnyType():
                raise CodeError("Any type is not supported", loc)
            case _:
                raise CodeError(
                    f"Unable to resolve mypy type {typ!r} to known algopy type",
                    loc,
                )

    def resolve_type_from_name_and_args(
        self, type_fullname: str, inst_args: Sequence[mypy.types.Type] | None, loc: SourceLocation
    ) -> TypeClassExpressionBuilder:
        from puya.awst_build.eb.arc4.struct import ARC4StructClassExpressionBuilder
        from puya.awst_build.eb.struct import StructSubclassExpressionBuilder
        from puya.awst_build.eb.type_registry import get_type_builder

        try:
            mapped_wtype = self.type_map[type_fullname]
        except KeyError:
            pass
        else:
            if isinstance(mapped_wtype, wtypes.ARC4Struct):
                return ARC4StructClassExpressionBuilder(mapped_wtype, loc)
            else:
                return StructSubclassExpressionBuilder(mapped_wtype, loc)

        cls_type_builder = get_type_builder(type_fullname, loc)
        if not inst_args:
            if not isinstance(cls_type_builder, TypeClassExpressionBuilder):
                raise CodeError(f"Missing generic type parameter(s) for {type_fullname}", loc)
            return cls_type_builder

        if any(isinstance(a, mypy.types.AnyType) for a in inst_args):
            raise CodeError(f"Unresolved generic type parameter for {type_fullname}", loc)

        type_args_resolved: list[TypeClassExpressionBuilder | AWSTLiteral] = [
            (
                AWSTLiteral(value=ta.value, source_location=loc)  # type: ignore[arg-type]
                if isinstance(ta, mypy.types.LiteralType)
                else self._type_to_builder(ta, source_location=loc)
            )
            for ta in inst_args
        ]
        if len(type_args_resolved) == 1:
            indexed_type = cls_type_builder.index(type_args_resolved[0], loc)
        else:
            indexed_type = cls_type_builder.index_multiple(type_args_resolved, loc)
        if not isinstance(indexed_type, TypeClassExpressionBuilder):
            raise InternalError(
                f"Expected TypeClassExpressionBuilder got: {type(indexed_type).__name__}", loc
            )
        return indexed_type

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
