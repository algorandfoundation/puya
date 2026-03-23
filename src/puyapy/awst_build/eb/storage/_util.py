from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    BoxValueExpression,
    CheckedMaybe,
    Expression,
    IntegerConstant,
    IntrinsicCall,
)
from puya.parse import SourceLocation
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb.interface import NodeBuilder

logger = log.get_logger(__name__)


def resolve_account(account: NodeBuilder) -> Expression:
    """Resolve an account argument to an Expression, validating constant index bounds."""
    # TODO: maybe resolve literal should allow functions, so we can validate
    #       constant values inside e.g. conditional expressions, not just plain constants
    #       like we check below with matching on IntegerConstant
    account_expr = expect.argument_of_type_else_dummy(
        account,
        pytypes.UInt64Type,
        pytypes.AccountType,
        resolve_literal=True,
    ).resolve()
    # https://dev.algorand.co/concepts/smart-contracts/resource-usage/
    # Note that the sender address is implicitly included in the array,
    # but doesn't count towards the limit of 4, so the <= 4 below is correct
    # and intended
    if isinstance(account_expr, IntegerConstant) and not (0 <= account_expr.value <= 4):
        logger.error(
            "account index should be between 0 and 4 inclusive",
            location=account_expr.source_location,
        )
    return account_expr


def box_length_checked(box: BoxValueExpression, location: SourceLocation) -> Expression:
    box_len_expr = _box_len(box.key, location)
    return CheckedMaybe(box_len_expr, comment=box.exists_assertion_message or "box exists")


def _box_len(box_key: Expression, location: SourceLocation) -> IntrinsicCall:
    assert box_key.wtype == wtypes.box_key
    return IntrinsicCall(
        op_code="box_len",
        wtype=wtypes.WTuple([wtypes.uint64_wtype, wtypes.bool_wtype], source_location=location),
        stack_args=[box_key],
        source_location=location,
    )
