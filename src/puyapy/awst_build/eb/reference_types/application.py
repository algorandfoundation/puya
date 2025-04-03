import typing
from collections.abc import Sequence

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import Expression, ReinterpretCast, UInt64Constant
from puya.parse import SourceLocation
from puyapy import models
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb.interface import (
    InstanceBuilder,
    LiteralBuilder,
    NodeBuilder,
    TypeBuilder,
)
from puyapy.awst_build.eb.reference_types._base import UInt64BackedReferenceValueExpressionBuilder

logger = log.get_logger(__name__)


class ApplicationTypeBuilder(TypeBuilder):
    def __init__(self, location: SourceLocation):
        super().__init__(pytypes.ApplicationType, location)

    @typing.override
    def try_convert_literal(
        self, literal: LiteralBuilder, location: SourceLocation
    ) -> InstanceBuilder | None:
        match literal.value:
            case int(int_value):
                if int_value < 0 or int_value.bit_length() > 64:  # TODO: should this be 256?
                    logger.error("invalid application ID", location=literal.source_location)
                const = UInt64Constant(value=int_value, source_location=location)
                expr = ReinterpretCast(
                    expr=const, wtype=wtypes.application_wtype, source_location=location
                )
                return ApplicationExpressionBuilder(expr)
        return None

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        arg = expect.at_most_one_arg(args, location)
        match arg:
            case InstanceBuilder(pytype=pytypes.IntLiteralType):
                return arg.resolve_literal(ApplicationTypeBuilder(location))
            case None:
                uint64_expr: Expression = UInt64Constant(value=0, source_location=location)
            case _:
                arg = expect.argument_of_type_else_dummy(arg, pytypes.UInt64Type)
                uint64_expr = arg.resolve()
        app_expr = ReinterpretCast(
            source_location=location, wtype=wtypes.application_wtype, expr=uint64_expr
        )
        return ApplicationExpressionBuilder(app_expr)


class ApplicationExpressionBuilder(UInt64BackedReferenceValueExpressionBuilder):
    def __init__(self, expr: Expression):
        native_access_member = "id"
        field_mapping = {
            "approval_program": ("AppApprovalProgram", pytypes.BytesType),
            "clear_state_program": ("AppClearStateProgram", pytypes.BytesType),
            "global_num_uint": ("AppGlobalNumUint", pytypes.UInt64Type),
            "global_num_bytes": ("AppGlobalNumByteSlice", pytypes.UInt64Type),
            "local_num_uint": ("AppLocalNumUint", pytypes.UInt64Type),
            "local_num_bytes": ("AppLocalNumByteSlice", pytypes.UInt64Type),
            "extra_program_pages": ("AppExtraProgramPages", pytypes.UInt64Type),
            "creator": ("AppCreator", pytypes.AccountType),
            "address": ("AppAddress", pytypes.AccountType),
        }
        field_op_code = "app_params_get"
        field_bool_comment = "application exists"
        super().__init__(
            expr,
            typ=pytypes.ApplicationType,
            typ_literal_converter=ApplicationTypeBuilder,
            native_access_member=native_access_member,
            field_mapping=field_mapping,
            field_op_code=field_op_code,
            field_bool_comment=field_bool_comment,
        )
