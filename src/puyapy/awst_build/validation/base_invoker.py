import typing

from puya import log
from puya.awst import nodes as awst_nodes
from puya.awst.awst_traverser import AWSTTraverser
from puya.awst.nodes import (
    ContractMethodTarget,
    InstanceMethodTarget,
    InstanceSuperMethodTarget,
    SubroutineID,
)

logger = log.get_logger(__name__)


class BaseInvokerValidator(AWSTTraverser):
    @classmethod
    def validate(cls, module: awst_nodes.AWST) -> None:
        validator = cls()
        for module_statement in module:
            module_statement.accept(validator)

    def visit_subroutine_call_expression(self, expr: awst_nodes.SubroutineCallExpression) -> None:
        super().visit_subroutine_call_expression(expr)
        match expr.target:
            case SubroutineID():
                # always okay
                pass
            case InstanceMethodTarget() | InstanceSuperMethodTarget():
                if self.contract is None:
                    logger.error(
                        "invocation of instance method outside of a contract method",
                        location=expr.source_location,
                    )
            case ContractMethodTarget(cref=target_class):
                caller_class = self.contract
                if caller_class is None:
                    logger.error(
                        "invocation of contract method outside of a contract method",
                        location=expr.source_location,
                    )
                else:
                    caller_ref = caller_class.cref
                    if target_class != caller_ref and target_class not in caller_class.bases:
                        logger.error(
                            "invocation of a contract method outside of current hierarchy",
                            location=expr.source_location,
                        )
            case invalid:
                typing.assert_never(invalid)
