import typing

from puya.awst import nodes as awst_nodes
from puya.awst.function_traverser import FunctionTraverser
from puya.awst.visitors import ContractMemberVisitor, RootNodeVisitor


class AWSTTraverser(FunctionTraverser, RootNodeVisitor[None], ContractMemberVisitor[None]):
    @typing.override
    def visit_subroutine(self, statement: awst_nodes.Subroutine) -> None:
        statement.body.accept(self)

    @typing.override
    def visit_contract_fragment(self, statement: awst_nodes.ContractFragment) -> None:
        for storage in statement.app_state.values():
            storage.accept(self)
        for method in statement.methods.values():
            method.accept(self)

    @typing.override
    def visit_logic_signature(self, statement: awst_nodes.LogicSignature) -> None:
        statement.program.accept(self)

    @typing.override
    def visit_app_storage_definition(self, defn: awst_nodes.AppStorageDefinition) -> None:
        defn.key.accept(self)

    @typing.override
    def visit_contract_method(self, statement: awst_nodes.ContractMethod) -> None:
        statement.body.accept(self)
