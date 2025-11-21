import typing

from puyapy.fast import nodes
from puyapy.fast.visitors import StatementVisitor


class StatementTraverser(StatementVisitor[None]):
    def visit_module(self, module: nodes.Module) -> None:
        for stmt in module.body:
            stmt.accept(self)

    @typing.override
    def visit_function_def(self, func_def: nodes.FunctionDef) -> None:
        for stmt in func_def.body:
            stmt.accept(self)

    @typing.override
    def visit_class_def(self, class_def: nodes.ClassDef) -> None:
        for stmt in class_def.body:
            stmt.accept(self)

    @typing.override
    def visit_for(self, for_stmt: nodes.For) -> None:
        for stmt in for_stmt.body:
            stmt.accept(self)
        for stmt in for_stmt.else_body or ():
            stmt.accept(self)

    @typing.override
    def visit_while(self, while_stmt: nodes.While) -> None:
        for stmt in while_stmt.body:
            stmt.accept(self)
        for stmt in while_stmt.else_body or ():
            stmt.accept(self)

    @typing.override
    def visit_if(self, if_stmt: nodes.If) -> None:
        for stmt in if_stmt.body:
            stmt.accept(self)
        for stmt in if_stmt.else_body or ():
            stmt.accept(self)

    @typing.override
    def visit_match(self, match_stmt: nodes.Match) -> None:
        for case in match_stmt.cases:
            for stmt in case.body:
                stmt.accept(self)

    @typing.override
    def visit_module_import(self, module_import: nodes.ModuleImport) -> None:
        pass

    @typing.override
    def visit_from_import(self, from_import: nodes.FromImport) -> None:
        pass

    @typing.override
    def visit_expression_statement(self, stmt: nodes.ExpressionStatement) -> None:
        pass

    @typing.override
    def visit_return(self, ret: nodes.Return) -> None:
        pass

    @typing.override
    def visit_delete(self, delete: nodes.Delete) -> None:
        pass

    @typing.override
    def visit_assign(self, assign: nodes.Assign) -> None:
        pass

    @typing.override
    def visit_multi_assign(self, multi_assign: nodes.MultiAssign) -> None:
        pass

    @typing.override
    def visit_aug_assign(self, aug_assign: nodes.AugAssign) -> None:
        pass

    @typing.override
    def visit_annotation(self, annotation: nodes.AnnotationStatement) -> None:
        pass

    @typing.override
    def visit_assert(self, assert_stmt: nodes.Assert) -> None:
        pass

    @typing.override
    def visit_pass(self, pass_stmt: nodes.Pass) -> None:
        pass

    @typing.override
    def visit_break(self, break_stmt: nodes.Break) -> None:
        pass

    @typing.override
    def visit_continue(self, continue_stmt: nodes.Continue) -> None:
        pass
