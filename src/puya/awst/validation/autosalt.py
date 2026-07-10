import typing

from puya import log
from puya.awst import nodes as awst_nodes
from puya.awst.awst_traverser import AWSTTraverser

logger = log.get_logger(__name__)


class AutosaltValidator(AWSTTraverser):
    """Warns when an explicit ``autosalt`` override contradicts the kind-based default."""

    @classmethod
    def validate(cls, module: awst_nodes.AWST) -> None:
        for module_statement in module:
            module_statement.accept(cls())

    @typing.override
    def visit_logic_signature(self, statement: awst_nodes.LogicSignature) -> None:
        # matches go-algorand's warning for `#pragma autosalt false` on a logicsig
        if statement.autosalt is False:
            logger.warning(
                "autosalt=False leaves this LogicSig's address on-curve,"
                " i.e. potentially decodable as a public key",
                location=statement.source_location,
            )

    @typing.override
    def visit_contract(self, statement: awst_nodes.Contract) -> None:
        if statement.autosalt is True:
            logger.warning(
                "autosalt=True has no security benefit for a contract since"
                " its program hash is never used as a spendable address",
                location=statement.source_location,
            )
