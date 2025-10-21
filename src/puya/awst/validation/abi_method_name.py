import re

from puya import log
from puya.awst import nodes as awst_nodes
from puya.awst.function_traverser import FunctionTraverser

logger = log.get_logger(__name__)


_VALID_NAME_PATTERN = re.compile("^[_A-Za-z][A-Za-z0-9_]*$")


class AbiMethodNameValidator(FunctionTraverser):
    @classmethod
    def validate(cls, module: awst_nodes.AWST) -> None:
        for module_statement in module:
            if isinstance(module_statement, awst_nodes.Contract):
                for method in module_statement.methods:
                    cls(method)

    def __init__(self, method: awst_nodes.ContractMethod) -> None:
        if method.arc4_method_config is not None and isinstance(
            method.arc4_method_config, awst_nodes.ARC4ABIMethodConfig
        ):
            method_name = method.arc4_method_config.name or method.member_name
            if not _VALID_NAME_PATTERN.match(method_name):
                logger.warning(
                    f"method name '{method_name}' does not conform to ARC4 spec",
                    location=method.source_location,
                )
