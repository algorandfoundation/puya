import typing

from puya.awst import nodes as awst_nodes
from puya.awst.function_traverser import FunctionTraverser
from puya.awst.visitors import ModuleStatementVisitor


class AWSTTraverser(FunctionTraverser, ModuleStatementVisitor[None]):
    @typing.override
    def visit_subroutine(self, statement: awst_nodes.Subroutine) -> None:
        statement.body.accept(self)

    @typing.override
    def visit_contract_fragment(self, statement: awst_nodes.ContractFragment) -> None:
        for storage in statement.app_state.values():
            self.visit_app_state_definition(storage)
        for method in statement.methods.values():
            method.accept(self)

    def visit_app_state_definition(self, state_defn: awst_nodes.AppStorageDefinition) -> None:
        pass

    @typing.override
    def visit_contract_method(self, statement: awst_nodes.ContractMethod) -> None:
        statement.body.accept(self)

    @typing.override
    def visit_logic_signature(self, statement: awst_nodes.LogicSignature) -> None:
        statement.program.accept(self)
