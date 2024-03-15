import typing

from puya.awst import nodes as awst_nodes
from puya.awst.nodes import (
    BaseClassSubroutineTarget,
    ContractReference,
    FreeSubroutineTarget,
    InstanceSubroutineTarget,
)
from puya.awst_build.validation.awst_traverser import AWSTTraverser
from puya.context import CompileContext


class BaseInvokerValidator(AWSTTraverser):
    @classmethod
    def validate(cls, context: CompileContext, module: awst_nodes.Module) -> None:
        validator = cls(context)
        for module_statement in module.body:
            module_statement.accept(validator)

    def __init__(self, context: CompileContext) -> None:
        super().__init__()
        self._context = context

    def visit_subroutine_call_expression(self, expr: awst_nodes.SubroutineCallExpression) -> None:
        super().visit_subroutine_call_expression(expr)
        match expr.target:
            case FreeSubroutineTarget():
                # always okay
                pass
            case InstanceSubroutineTarget():
                if self.contract is None:
                    self._context.errors.error(
                        "Invocation of instance method outside of a contract method",
                        expr.source_location,
                    )
            case BaseClassSubroutineTarget(base_class=target_class):
                caller_class = self.contract
                if caller_class is None:
                    self._context.errors.error(
                        "Invocation of instance method outside of a contract method",
                        expr.source_location,
                    )
                else:
                    caller_ref = ContractReference(
                        module_name=caller_class.module_name, class_name=caller_class.name
                    )
                    if target_class != caller_ref and target_class not in caller_class.bases:
                        self._context.errors.error(
                            "Invocation of a base method outside of current hierarchy",
                            expr.source_location,
                        )
            case _:
                typing.assert_never(expr.target)
