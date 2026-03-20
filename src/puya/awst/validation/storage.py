import typing
from collections import defaultdict

from puya import log
from puya.avm import AVMType
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.awst.awst_traverser import AWSTTraverser
from puya.awst.nodes import AppStorageKind
from puya.parse import SourceLocation
from puya.utils import set_add

logger = log.get_logger(__name__)


class StorageTypesValidator(AWSTTraverser):
    @classmethod
    def validate(cls, module: awst_nodes.AWST) -> None:
        for module_statement in module:
            # create a new instance for each top level construct,
            # either subroutine or contract class, so that we can de-dupe
            # messages (where possible) there
            validator = cls()
            module_statement.accept(validator)

    def __init__(self) -> None:
        super().__init__()
        self._seen_keys = defaultdict[AppStorageKind, set[bytes | str]](set)

    @typing.override
    def visit_app_storage_definition(self, defn: awst_nodes.AppStorageDefinition) -> None:
        super().visit_app_storage_definition(defn)
        _validate_persistable(defn.storage_wtype, defn.source_location)
        if defn.key_wtype is not None:
            _validate_persistable(defn.key_wtype, defn.source_location)

    @typing.override
    def visit_app_state_expression(self, expr: awst_nodes.AppStateExpression) -> None:
        super().visit_app_state_expression(expr)
        self._validate_usage(expr, AppStorageKind.app_global)

    @typing.override
    def visit_app_account_state_expression(
        self, expr: awst_nodes.AppAccountStateExpression
    ) -> None:
        super().visit_app_account_state_expression(expr)
        self._validate_usage(expr, AppStorageKind.account_local)

    @typing.override
    def visit_box_value_expression(self, expr: awst_nodes.BoxValueExpression) -> None:
        super().visit_box_value_expression(expr)
        self._validate_usage(expr, AppStorageKind.box)

    @typing.override
    def visit_map_prefixed_key_expression(self, expr: awst_nodes.MapPrefixedKeyExpression) -> None:
        super().visit_map_prefixed_key_expression(expr)
        _validate_persistable(expr.key.wtype, expr.key.source_location)
        _validate_persistable(expr.prefix.wtype, expr.prefix.source_location)

    @typing.override
    def visit_contract(self, statement: awst_nodes.Contract) -> None:
        super().visit_contract(statement)
        state_totals = statement.state_totals or awst_nodes.StateTotals()
        for state in statement.app_state:
            _check_map_state_totals(state, state_totals, statement.source_location)

    def _validate_usage(self, expr: awst_nodes.StorageExpression, kind: AppStorageKind) -> None:
        key = _unwrap_reinterpret_casts(expr.key)
        if isinstance(key, awst_nodes.BytesConstant | awst_nodes.StringConstant) and not set_add(
            self._seen_keys[kind], key.value
        ):
            return
        _validate_persistable(expr.wtype, expr.source_location)


def _check_map_state_totals(
    state: awst_nodes.AppStorageDefinition,
    state_totals: awst_nodes.StateTotals,
    contract_loc: SourceLocation,
) -> None:
    if not state.key_wtype:
        return
    match state.kind, state.storage_wtype.scalar_type:
        case (AppStorageKind.account_local, AVMType.uint64) if state_totals.local_uints is None:
            desc = "local uint"
        case (AppStorageKind.account_local, AVMType.bytes) if state_totals.local_bytes is None:
            desc = "local bytes"
        case (AppStorageKind.app_global, AVMType.uint64) if state_totals.global_uints is None:
            desc = "global uint"
        case (AppStorageKind.app_global, AVMType.bytes) if state_totals.global_bytes is None:
            desc = "global bytes"
        case _:
            return
    logger.warning(
        f"no {desc} state total defined for contract but {state.member_name!r} map is defined",
        location=contract_loc,
    )


def _validate_persistable(wtype: wtypes.WType, location: SourceLocation) -> bool:
    if not wtype.persistable:
        logger.error("type is not suitable for storage", location=location)
        return False
    return True


def _unwrap_reinterpret_casts(expr: awst_nodes.Expression) -> awst_nodes.Expression:
    if isinstance(expr, awst_nodes.ReinterpretCast):
        return expr.expr
    return expr
