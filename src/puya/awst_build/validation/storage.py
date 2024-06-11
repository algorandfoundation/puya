from collections import defaultdict

from puya import log
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.awst.awst_traverser import AWSTTraverser
from puya.awst.nodes import AppStorageKind
from puya.utils import set_add

logger = log.get_logger(__name__)


class StorageTypesValidator(AWSTTraverser):
    @classmethod
    def validate(cls, module: awst_nodes.Module) -> None:
        for module_statement in module.body:
            # create a new instance for each top level construct,
            # either subroutine or contract class, so that we can de-dupe
            # messages (where possible) there
            validator = cls()
            module_statement.accept(validator)

    def __init__(self) -> None:
        super().__init__()
        self._seen_keys = defaultdict[AppStorageKind, set[bytes]](set)

    def visit_app_state_definition(self, state_defn: awst_nodes.AppStorageDefinition) -> None:
        super().visit_app_state_definition(state_defn)
        wtypes.validate_persistable(state_defn.storage_wtype, state_defn.source_location)
        if state_defn.key_wtype is not None:
            wtypes.validate_persistable(state_defn.key_wtype, state_defn.source_location)

    def visit_app_state_expression(self, expr: awst_nodes.AppStateExpression) -> None:
        super().visit_app_state_expression(expr)
        self._validate_usage(expr, AppStorageKind.app_global)

    def visit_app_account_state_expression(
        self, expr: awst_nodes.AppAccountStateExpression
    ) -> None:
        super().visit_app_account_state_expression(expr)
        self._validate_usage(expr, AppStorageKind.account_local)

    def visit_box_value_expression(self, expr: awst_nodes.BoxValueExpression) -> None:
        super().visit_box_value_expression(expr)
        self._validate_usage(expr, AppStorageKind.box)

    def _validate_usage(self, expr: awst_nodes.StorageExpression, kind: AppStorageKind) -> None:
        if isinstance(expr.key, awst_nodes.BytesConstant) and not set_add(
            self._seen_keys[kind], expr.key.value
        ):
            return
        wtypes.validate_persistable(expr.wtype, expr.source_location)
