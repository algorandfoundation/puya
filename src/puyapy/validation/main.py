from puya.awst import nodes as awst_nodes
from puyapy.validation.arc4_copy import ARC4CopyValidator


def validate_awst(module: awst_nodes.AWST) -> None:
    ARC4CopyValidator.validate(module)
