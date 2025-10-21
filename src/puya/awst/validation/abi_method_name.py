import re

from puya import log
from puya.awst import nodes as awst_nodes
from puya.awst.awst_traverser import AWSTTraverser

logger = log.get_logger(__name__)


_VALID_NAME_PATTERN = re.compile("^[_A-Za-z][A-Za-z0-9_]*$")


class AbiMethodNameValidator(AWSTTraverser):
    """
    Validates that ABI method names conform to the ARC-4 specification.
    """

    @classmethod
    def validate(cls, module: awst_nodes.AWST) -> None:
        for module_statement in module:
            validator = cls()
            module_statement.accept(validator)

    def visit_contract_method(self, statement: awst_nodes.ContractMethod) -> None:
        if statement.arc4_method_config is not None and isinstance(
            statement.arc4_method_config, awst_nodes.ARC4ABIMethodConfig
        ):
            method_name = statement.arc4_method_config.name
            if not _VALID_NAME_PATTERN.match(method_name):
                logger.warning(
                    f"method name '{method_name}' does not conform to ARC-4 spec",
                    location=statement.source_location,
                )
