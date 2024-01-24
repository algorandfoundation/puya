from puya.awst import nodes as awst_nodes
from puya.awst.function_traverser import FunctionTraverser
from puya.awst.visitors import ModuleStatementVisitor


class AWSTTraverser(FunctionTraverser, ModuleStatementVisitor[None]):
    def visit_subroutine(self, statement: awst_nodes.Subroutine) -> None:
        statement.body.accept(self)

    def visit_contract_fragment(self, statement: awst_nodes.ContractFragment) -> None:
        if statement.approval_program:
            statement.approval_program.accept(self)
        if statement.clear_program:
            statement.clear_program.accept(self)
        for cm in statement.subroutines:
            cm.accept(self)

    def visit_structure_definition(self, statement: awst_nodes.StructureDefinition) -> None:
        pass

    def visit_contract_method(self, statement: awst_nodes.ContractMethod) -> None:
        statement.body.accept(self)

    def visit_constant_declaration(self, statement: awst_nodes.ConstantDeclaration) -> None:
        pass
