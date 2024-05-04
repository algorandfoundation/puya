import contextlib
from collections.abc import Iterator

from puya.awst import nodes as awst_nodes
from puya.awst.function_traverser import FunctionTraverser
from puya.awst.visitors import ModuleStatementVisitor


class AWSTTraverser(FunctionTraverser, ModuleStatementVisitor[None]):
    def __init__(self) -> None:
        self._contract: awst_nodes.ContractFragment | None = None

    @property
    def contract(self) -> awst_nodes.ContractFragment | None:
        return self._contract

    @contextlib.contextmanager
    def _enter_contract(self, contract: awst_nodes.ContractFragment) -> Iterator[None]:
        assert self._contract is None
        self._contract = contract
        try:
            yield
        finally:
            self._contract = None

    def visit_subroutine(self, statement: awst_nodes.Subroutine) -> None:
        statement.body.accept(self)

    def visit_contract_fragment(self, statement: awst_nodes.ContractFragment) -> None:
        with self._enter_contract(statement):
            for node in statement.symtable.values():
                if isinstance(node, awst_nodes.ContractMethod):
                    node.accept(self)
                else:
                    self.visit_app_state_definition(node)

    def visit_app_state_definition(self, state_defn: awst_nodes.AppStorageDefinition) -> None:
        pass

    def visit_structure_definition(self, statement: awst_nodes.StructureDefinition) -> None:
        pass

    def visit_contract_method(self, statement: awst_nodes.ContractMethod) -> None:
        statement.body.accept(self)

    def visit_constant_declaration(self, statement: awst_nodes.ConstantDeclaration) -> None:
        pass

    def visit_logic_signature(self, statement: awst_nodes.LogicSignature) -> None:
        statement.program.accept(self)
