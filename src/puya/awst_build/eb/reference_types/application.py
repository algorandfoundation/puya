from __future__ import annotations

import typing

from immutabledict import immutabledict

from puya.awst import wtypes
from puya.awst.nodes import Literal, UInt64Constant
from puya.awst_build.eb.base import ExpressionBuilder, TypeClassExpressionBuilder
from puya.awst_build.eb.reference_types.base import (
    UInt64BackedReferenceValueExpressionBuilder,
)
from puya.awst_build.utils import expect_operand_wtype
from puya.errors import CodeError

if typing.TYPE_CHECKING:
    import mypy.nodes

    from puya.parse import SourceLocation


class ApplicationClassExpressionBuilder(TypeClassExpressionBuilder):
    def produces(self) -> wtypes.WType:
        return wtypes.application_wtype

    def call(
        self,
        args: typing.Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        match args:
            case [ExpressionBuilder() as eb]:
                uint64_expr = expect_operand_wtype(eb, wtypes.uint64_wtype)
                return ApplicationExpressionBuilder(uint64_expr)
            case [Literal(value=int(int_value), source_location=loc)]:
                const = UInt64Constant(value=int_value, source_location=loc)
                return ApplicationExpressionBuilder(const)
            case _:
                raise CodeError("Invalid/unhandled arguments", location)


class ApplicationExpressionBuilder(UInt64BackedReferenceValueExpressionBuilder):
    wtype = wtypes.application_wtype
    native_access_member = "application_id"
    field_mapping = immutabledict(
        {
            "approval_program": ("AppApprovalProgram", wtypes.bytes_wtype),
            "clear_state_program": ("AppClearStateProgram", wtypes.bytes_wtype),
            "global_num_uint": ("AppGlobalNumUint", wtypes.uint64_wtype),
            "global_num_byte_slice": ("AppGlobalNumByteSlice", wtypes.uint64_wtype),
            "local_num_uint": ("AppLocalNumUint", wtypes.uint64_wtype),
            "local_num_byte_slice": ("AppLocalNumByteSlice", wtypes.uint64_wtype),
            "extra_program_pages": ("AppExtraProgramPages", wtypes.uint64_wtype),
            "creator": ("AppCreator", wtypes.account_wtype),
            "address": ("AppAddress", wtypes.account_wtype),
        }
    )
    field_op_code = "app_params_get"
    field_bool_comment = "application exists"
