from collections import defaultdict

from puya import log
from puya.awst import nodes as awst_nodes
from puya.awst.function_traverser import FunctionTraverser

logger = log.get_logger(__name__)


class LabelsValidator(FunctionTraverser):
    @classmethod
    def validate(cls, module: awst_nodes.AWST) -> None:
        for module_statement in module:
            if isinstance(module_statement, awst_nodes.Subroutine):
                cls(module_statement)
            elif isinstance(module_statement, awst_nodes.Contract):
                for method in module_statement.all_methods:
                    cls(method)

    def __init__(self, function: awst_nodes.Function) -> None:
        self._labelled_blocks = dict[awst_nodes.Label, awst_nodes.Block]()
        self._seen_targets = defaultdict[awst_nodes.Label, list[awst_nodes.Goto]](list)
        function.body.accept(self)
        for target, goto_list in self._seen_targets.items():
            if target not in self._labelled_blocks:
                for goto in goto_list:
                    logger.error(
                        f"label target {target} does not exist", location=goto.source_location
                    )

    def visit_goto(self, goto: awst_nodes.Goto) -> None:
        self._seen_targets[goto.target].append(goto)

    def visit_block(self, block: awst_nodes.Block) -> None:
        if block.label is not None:
            first_seen = self._labelled_blocks.setdefault(block.label, block)
            if block is not first_seen:
                logger.error(
                    f"block has duplicate label {block.label}", location=block.source_location
                )
                logger.info("label first seen here", location=first_seen.source_location)
