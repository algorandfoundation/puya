from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.awst.function_traverser import FunctionTraverser
from puya.awst.visitors import ModuleStatementVisitor
from puya.context import CompileContext


def validate_awst(context: CompileContext, module_asts: dict[str, awst_nodes.Module]) -> None:
    validate_arc4_copy_semantics(context, module_asts)


def validate_arc4_copy_semantics(
    context: CompileContext, module_asts: dict[str, awst_nodes.Module]
) -> None:
    for module in module_asts.values():
        for module_statement in module.body:
            Arc4CopyValidator.validate(context, module_statement)


class AwstTraverser(FunctionTraverser, ModuleStatementVisitor[None]):
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


class Arc4CopyValidator(AwstTraverser):
    def __init__(self, context: CompileContext) -> None:
        self._context = context

    def visit_assignment_statement(self, statement: awst_nodes.AssignmentStatement) -> None:
        super().visit_assignment_statement(statement)
        self._check_for_arc4_copy(statement.value)

    def _check_for_arc4_copy(self, expr: awst_nodes.Expression) -> None:
        match expr.wtype:
            case wtypes.ARC4Array() | wtypes.ARC4Struct():
                match expr:
                    case awst_nodes.ARC4ArrayEncode():
                        return
                    case awst_nodes.ARC4Encode():
                        return
                    case awst_nodes.Copy():
                        return
                    case awst_nodes.ArrayConcat():
                        return
                    case awst_nodes.SubroutineCallExpression():
                        return

                self._context.errors.error(
                    f"{expr.wtype} must be copied using .copy() when assigning to a new local"
                    " or being passed to a subroutine.",
                    expr.source_location,
                )

    def visit_assignment_expression(self, expr: awst_nodes.AssignmentExpression) -> None:
        super().visit_assignment_expression(expr)
        self._check_for_arc4_copy(expr.value)

    def visit_subroutine_call_expression(self, expr: awst_nodes.SubroutineCallExpression) -> None:
        super().visit_subroutine_call_expression(expr)
        for arg in expr.args:
            self._check_for_arc4_copy(arg.value)

    @classmethod
    def validate(
        cls, context: CompileContext, module_statement: awst_nodes.ModuleStatement
    ) -> None:
        validator = cls(context)
        module_statement.accept(validator)
