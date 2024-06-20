import abc
import typing
from collections.abc import Sequence

import mypy.nodes
import typing_extensions

from puya import log
from puya.awst.nodes import BytesConstant, BytesEncoding, CheckedMaybe, Copy, Expression
from puya.awst_build import intrinsic_factory, pytypes
from puya.awst_build.eb._base import FunctionBuilder
from puya.awst_build.eb._bytes_backed import BytesBackedTypeBuilder
from puya.awst_build.eb._utils import compare_expr_bytes, expect_exactly_one_arg, expect_no_args
from puya.awst_build.eb.factories import builder_for_instance
from puya.awst_build.eb.interface import BuilderComparisonOp, InstanceBuilder, NodeBuilder
from puya.parse import SourceLocation

logger = log.get_logger(__name__)


_TPyType_co = typing_extensions.TypeVar(
    "_TPyType_co", bound=pytypes.PyType, default=pytypes.PyType, covariant=True
)


class ARC4TypeBuilder(BytesBackedTypeBuilder[_TPyType_co], abc.ABC):
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        match name:
            case "from_log":
                return ARC4FromLogBuilder(location, self.produces())
            case _:
                return super().member_access(name, location)


class ARC4FromLogBuilder(FunctionBuilder):
    def __init__(self, location: SourceLocation, typ: pytypes.PyType):
        super().__init__(location=location)
        self.typ = typ

    @classmethod
    def abi_expr_from_log(
        cls, typ: pytypes.PyType, value: InstanceBuilder, location: SourceLocation
    ) -> Expression:
        tmp_value = value.single_eval().resolve()
        arc4_value = intrinsic_factory.extract(
            tmp_value, start=4, loc=location, result_type=typ.wtype
        )
        arc4_prefix = intrinsic_factory.extract(tmp_value, start=0, length=4, loc=location)
        arc4_prefix_is_valid = compare_expr_bytes(
            lhs=arc4_prefix,
            rhs=BytesConstant(
                value=b"\x15\x1f\x7c\x75",
                source_location=location,
                encoding=BytesEncoding.base16,
            ),
            op=BuilderComparisonOp.eq,
            source_location=location,
        )
        return CheckedMaybe.from_tuple_items(
            expr=arc4_value,
            check=arc4_prefix_is_valid.resolve(),
            source_location=location,
            comment="ARC4 prefix is valid",
        )

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        arg = expect_exactly_one_arg(args, location)
        result_expr = self.abi_expr_from_log(self.typ, arg, location)
        return builder_for_instance(self.typ, result_expr)


class CopyBuilder(FunctionBuilder):
    def __init__(self, expr: Expression, location: SourceLocation, typ: pytypes.PyType):
        super().__init__(location)
        self._typ = typ
        self.expr = expr

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        expect_no_args(args, location)
        expr_result = Copy(value=self.expr, source_location=location)
        return builder_for_instance(self._typ, expr_result)


def arc4_bool_bytes(
    builder: InstanceBuilder, false_bytes: bytes, location: SourceLocation, *, negate: bool
) -> InstanceBuilder:
    false_value = BytesConstant(
        value=false_bytes,
        encoding=BytesEncoding.base16,
        wtype=builder.pytype.wtype,
        source_location=location,
    )
    return compare_expr_bytes(
        op=BuilderComparisonOp.eq if negate else BuilderComparisonOp.ne,
        lhs=builder.resolve(),
        rhs=false_value,
        source_location=location,
    )
