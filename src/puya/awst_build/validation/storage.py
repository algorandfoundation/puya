from collections import defaultdict

from puya import log
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.awst.nodes import AppStorageKind
from puya.awst_build.validation.awst_traverser import AWSTTraverser

logger = log.get_logger(__name__)


class StorageTypesValidator(AWSTTraverser):
    @classmethod
    def validate(cls, module: awst_nodes.Module) -> None:
        for module_statement in module.body:
            validator = cls()
            module_statement.accept(validator)

    def __init__(self) -> None:
        super().__init__()
        self._seen_keys = defaultdict[AppStorageKind, set[bytes]](set)
        self._seen_key_prefixes = defaultdict[AppStorageKind, set[bytes]](set)

    def visit_app_state_definition(self, state_defn: awst_nodes.AppStorageDefinition) -> None:
        super().visit_app_state_definition(state_defn)
        if state_defn.key_wtype is None:
            self._seen_keys[state_defn.kind].add(state_defn.key.value)
        else:
            self._seen_key_prefixes[state_defn.kind].add(state_defn.key.value)
        wtypes.validate_persistable(state_defn.storage_wtype, state_defn.source_location)
        if state_defn.key_wtype is not None:
            wtypes.validate_persistable(state_defn.key_wtype, state_defn.source_location)

    def visit_app_account_state_expression(
        self, expr: awst_nodes.AppAccountStateExpression
    ) -> None:
        super().visit_app_account_state_expression(expr)

    def visit_app_state_expression(self, expr: awst_nodes.AppStateExpression) -> None:
        super().visit_app_state_expression(expr)

    def visit_box_value_expression(self, expr: awst_nodes.BoxValueExpression) -> None:
        super().visit_box_value_expression(expr)
