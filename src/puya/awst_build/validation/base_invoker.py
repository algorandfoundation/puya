import typing

from puya import log
from puya.awst import nodes as awst_nodes
from puya.awst.awst_traverser import AWSTTraverser
from puya.awst.nodes import (
    BaseClassSubroutineTarget,
    FreeSubroutineTarget,
    InstanceSubroutineTarget,
)
from puya.models import ContractReference

logger = log.get_logger(__name__)


class BaseInvokerValidator(AWSTTraverser):
    @classmethod
    def validate(cls, module: awst_nodes.Module) -> None:
        validator = cls()
        for module_statement in module.body:
            module_statement.accept(validator)

    def visit_subroutine_call_expression(self, expr: awst_nodes.SubroutineCallExpression) -> None:
        super().visit_subroutine_call_expression(expr)
        match expr.target:
            case FreeSubroutineTarget():
                # always okay
                pass
            case InstanceSubroutineTarget():
                if self.contract is None:
                    logger.error(
                        "Invocation of instance method outside of a contract method",
                        location=expr.source_location,
                    )
            case BaseClassSubroutineTarget(base_class=target_class):
                caller_class = self.contract
                if caller_class is None:
                    logger.error(
                        "Invocation of instance method outside of a contract method",
                        location=expr.source_location,
                    )
                else:
                    caller_ref = ContractReference(
                        module_name=caller_class.module_name, class_name=caller_class.name
                    )
                    if target_class != caller_ref and target_class not in caller_class.bases:
                        logger.error(
                            "Invocation of a base method outside of current hierarchy",
                            location=expr.source_location,
                        )
            case _:
                typing.assert_never(expr.target)
