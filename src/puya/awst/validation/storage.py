import typing
from collections import defaultdict

from puya import log
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
        self._seen_definitions = defaultdict[
            AppStorageKind, dict[bytes, awst_nodes.AppStorageDefinition]
        ](dict)

    @typing.override
    def visit_app_storage_definition(self, defn: awst_nodes.AppStorageDefinition) -> None:
        super().visit_app_storage_definition(defn)
        _validate_persistable(defn.storage_wtype, defn.source_location)
        if defn.key_wtype is not None:
            _validate_persistable(defn.key_wtype, defn.source_location)
        self._validate_definition_key_collisions(defn)

    def _validate_definition_key_collisions(self, defn: awst_nodes.AppStorageDefinition) -> None:
        kind_labels = {
            AppStorageKind.app_global: "global state key",
            AppStorageKind.account_local: "local state key",
            AppStorageKind.box: "box key or prefix",
        }
        kind_label = kind_labels.get(defn.kind)
        if kind_label is None:
            return

        existing = self._seen_definitions[defn.kind].get(defn.key.value)
        if existing is not None:
            logger.info(
                f"previous definition of {kind_label} was here",
                location=existing.source_location,
            )
            logger.error(
                f"duplicate {kind_label} {defn.key.value!r}",
                location=defn.source_location,
            )
        else:
            self._seen_definitions[defn.kind][defn.key.value] = defn

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
    def visit_box_prefixed_key_expression(self, expr: awst_nodes.BoxPrefixedKeyExpression) -> None:
        super().visit_box_prefixed_key_expression(expr)
        _validate_persistable(expr.key.wtype, expr.key.source_location)
        _validate_persistable(expr.prefix.wtype, expr.prefix.source_location)

    def _validate_usage(self, expr: awst_nodes.StorageExpression, kind: AppStorageKind) -> None:
        key = _unwrap_reinterpret_casts(expr.key)
        if isinstance(key, awst_nodes.BytesConstant | awst_nodes.StringConstant) and not set_add(
            self._seen_keys[kind], key.value
        ):
            return
        _validate_persistable(expr.wtype, expr.source_location)


def _validate_persistable(wtype: wtypes.WType, location: SourceLocation) -> bool:
    if not wtype.persistable:
        logger.error("type is not suitable for storage", location=location)
        return False
    return True


def _unwrap_reinterpret_casts(expr: awst_nodes.Expression) -> awst_nodes.Expression:
    if isinstance(expr, awst_nodes.ReinterpretCast):
        return expr.expr
    return expr
