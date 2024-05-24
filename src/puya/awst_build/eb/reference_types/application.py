from __future__ import annotations

import typing

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import Expression, Literal, ReinterpretCast, UInt64Constant
from puya.awst_build import pytypes
from puya.awst_build.eb.base import ExpressionBuilder, TypeClassExpressionBuilder
from puya.awst_build.eb.reference_types.base import UInt64BackedReferenceValueExpressionBuilder
from puya.awst_build.utils import expect_operand_wtype

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.nodes

    from puya.parse import SourceLocation


logger = log.get_logger(__name__)


class ApplicationClassExpressionBuilder(TypeClassExpressionBuilder):
    def __init__(self, location: SourceLocation):
        super().__init__(pytypes.ApplicationType, location)

    @typing.override
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        match args:
            case []:
                uint64_expr: Expression = UInt64Constant(value=0, source_location=location)
            case [Literal(value=int(int_value), source_location=loc)]:
                uint64_expr = UInt64Constant(value=int_value, source_location=loc)
            case [ExpressionBuilder() as eb]:
                uint64_expr = expect_operand_wtype(eb, wtypes.uint64_wtype)
            case _:
                logger.error("Invalid/unhandled arguments", location=location)
                # dummy value to continue with
                uint64_expr = UInt64Constant(value=0, source_location=location)
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
            native_access_member=native_access_member,
            field_mapping=field_mapping,
            field_op_code=field_op_code,
            field_bool_comment=field_bool_comment,
        )
