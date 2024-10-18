import contextlib
import typing
from collections.abc import Iterator

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
    def __init__(self) -> None:
        self._contract: awst_nodes.Contract | None = None

    @property
    def contract(self) -> awst_nodes.Contract | None:
        return self._contract

    @contextlib.contextmanager
    def _enter_contract(self, contract: awst_nodes.Contract) -> Iterator[None]:
        assert self._contract is None
        self._contract = contract
        try:
            yield
        finally:
            self._contract = None

    @classmethod
    def validate(cls, module: awst_nodes.AWST) -> None:
        validator = cls()
        for module_statement in module:
            module_statement.accept(validator)

    @typing.override
    def visit_contract(self, statement: awst_nodes.Contract) -> None:
        with self._enter_contract(statement):
            super().visit_contract(statement)

    @typing.override
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
                    caller_ref = caller_class.id
                    if (
                        target_class != caller_ref
                        and target_class not in caller_class.method_resolution_order
                    ):
                        logger.error(
                            "invocation of a contract method outside of current hierarchy",
                            location=expr.source_location,
                        )
            case invalid:
                typing.assert_never(invalid)
