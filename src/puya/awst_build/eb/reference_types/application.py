import typing
from collections.abc import Sequence

import mypy.nodes

from puya import log
from puya.awst.nodes import Expression, ReinterpretCast, UInt64Constant
from puya.awst_build import pytypes
from puya.awst_build.eb.interface import InstanceBuilder, LiteralBuilder, NodeBuilder, TypeBuilder
from puya.awst_build.eb.reference_types._base import UInt64BackedReferenceValueExpressionBuilder
from puya.parse import SourceLocation

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
                if int_value < 0:  # TODO: should this be 256?
                    logger.error("invalid application ID", location=literal.source_location)
                const = UInt64Constant(value=int_value, source_location=location)
                expr = ReinterpretCast(
                    expr=const, wtype=self.produces().wtype, source_location=location
                )
                return ApplicationExpressionBuilder(expr)
        return None

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        match args:
            case [InstanceBuilder(pytype=pytypes.IntLiteralType) as arg]:
                return arg.resolve_literal(ApplicationTypeBuilder(location))
            case []:
                uint64_expr: Expression = UInt64Constant(value=0, source_location=location)
            case [LiteralBuilder(value=int(int_value), source_location=loc)]:
                uint64_expr = UInt64Constant(value=int_value, source_location=loc)
            case [InstanceBuilder(pytype=pytypes.UInt64Type) as eb]:
                uint64_expr = eb.resolve()
            case _:
                logger.error("Invalid/unhandled arguments", location=location)
                # dummy value to continue with
                uint64_expr = UInt64Constant(value=0, source_location=location)
        app_expr = ReinterpretCast(
            source_location=location, wtype=self.produces().wtype, expr=uint64_expr
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
