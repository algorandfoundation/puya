from __future__ import annotations

import typing

from immutabledict import immutabledict

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import Expression, Literal, UInt64Constant
from puya.awst_build.eb.base import ExpressionBuilder, TypeClassExpressionBuilder
from puya.awst_build.eb.reference_types.base import UInt64BackedReferenceValueExpressionBuilder
from puya.awst_build.utils import expect_operand_wtype

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.nodes

    from puya.awst_build import pytypes
    from puya.parse import SourceLocation


logger = log.get_logger(__name__)


class ApplicationClassExpressionBuilder(TypeClassExpressionBuilder):
    def produces(self) -> wtypes.WType:
        return wtypes.application_wtype

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
        return ApplicationExpressionBuilder(uint64_expr)


class ApplicationExpressionBuilder(UInt64BackedReferenceValueExpressionBuilder):
    wtype = wtypes.application_wtype
    native_access_member = "id"
    field_mapping = immutabledict(
        {
            "approval_program": ("AppApprovalProgram", wtypes.bytes_wtype),
            "clear_state_program": ("AppClearStateProgram", wtypes.bytes_wtype),
            "global_num_uint": ("AppGlobalNumUint", wtypes.uint64_wtype),
            "global_num_bytes": ("AppGlobalNumByteSlice", wtypes.uint64_wtype),
            "local_num_uint": ("AppLocalNumUint", wtypes.uint64_wtype),
            "local_num_bytes": ("AppLocalNumByteSlice", wtypes.uint64_wtype),
            "extra_program_pages": ("AppExtraProgramPages", wtypes.uint64_wtype),
            "creator": ("AppCreator", wtypes.account_wtype),
            "address": ("AppAddress", wtypes.account_wtype),
        }
    )
    field_op_code = "app_params_get"
    field_bool_comment = "application exists"
