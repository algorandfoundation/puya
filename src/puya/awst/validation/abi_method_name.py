import re
import typing

from puya import log
from puya.awst import nodes as awst_nodes
from puya.awst.awst_traverser import AWSTTraverser
from puya.parse import SourceLocation

logger = log.get_logger(__name__)

_VALID_NAME_PATTERN = re.compile("^[_A-Za-z][A-Za-z0-9_]*$")


def _validate_method_name(method_name: str, source_location: SourceLocation) -> None:
    if not _VALID_NAME_PATTERN.match(method_name):
        logger.warning(
            f"method name '{method_name}' does not conform to ARC-4 spec",
            location=source_location,
        )


class AbiMethodNameValidator(AWSTTraverser):
    """
    Validates that ABI method names conform to the ARC-4 specification.
    """

    @classmethod
    def validate(cls, module: awst_nodes.AWST) -> None:
        for module_statement in module:
            validator = cls()
            module_statement.accept(validator)

    @typing.override
    def visit_contract_method(self, statement: awst_nodes.ContractMethod) -> None:
        if statement.arc4_method_config is not None and isinstance(
            statement.arc4_method_config, awst_nodes.ARC4ABIMethodConfig
        ):
            _validate_method_name(statement.arc4_method_config.name, statement.source_location)
        super().visit_contract_method(statement)

    @typing.override
    def visit_method_constant(self, expr: awst_nodes.MethodConstant) -> None:
        if isinstance(expr.value, awst_nodes.MethodSignature):
            _validate_method_name(expr.value.name, expr.value.source_location)
