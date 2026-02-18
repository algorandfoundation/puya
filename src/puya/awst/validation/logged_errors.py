from puya import log
from puya.awst import nodes as awst_nodes
from puya.awst.awst_traverser import AWSTTraverser

logger = log.get_logger(__name__)


class LoggedErrorsValidator(AWSTTraverser):
    """Validates that logged errors are not used in logic signatures,
    as logic signatures do not support the log opcode."""

    def __init__(self) -> None:
        super().__init__()
        self._in_logic_sig = False

    @classmethod
    def validate(cls, module: awst_nodes.AWST) -> None:
        for module_statement in module:
            validator = cls()
            module_statement.accept(validator)

    def visit_logic_signature(self, statement: awst_nodes.LogicSignature) -> None:
        self._in_logic_sig = True
        super().visit_logic_signature(statement)
        self._in_logic_sig = False

    def visit_assert_expression(self, expr: awst_nodes.AssertExpression) -> None:
        if self._in_logic_sig and expr.log_error:
            logger.error(
                "logged errors are not supported in logic signatures",
                location=expr.source_location,
            )
        super().visit_assert_expression(expr)
