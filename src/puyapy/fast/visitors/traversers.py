import typing

from puyapy.fast import nodes
from puyapy.fast.visitors import ExpressionVisitor, MatchPatternVisitor, StatementVisitor


class ExpressionTraverser(ExpressionVisitor[None]):
    @typing.override
    def visit_constant(self, constant: nodes.Constant) -> None:
        pass

    @typing.override
    def visit_name(self, name: nodes.Name) -> None:
        pass

    @typing.override
    def visit_attribute(self, attribute: nodes.Attribute) -> None:
        attribute.base.accept(self)

    @typing.override
    def visit_subscript(self, subscript: nodes.Subscript) -> None:
        subscript.base.accept(self)
        for index in subscript.indexes:
            if isinstance(index, nodes.Slice):
                if index.lower is not None:
                    index.lower.accept(self)
                if index.upper is not None:
                    index.upper.accept(self)
                if index.step is not None:
                    index.step.accept(self)
            else:
                index.accept(self)

    @typing.override
    def visit_bool_op(self, bool_op: nodes.BoolOp) -> None:
        for value in bool_op.values:
            value.accept(self)

    @typing.override
    def visit_named_expr(self, named_expr: nodes.NamedExpr) -> None:
        named_expr.target.accept(self)
        named_expr.value.accept(self)

    @typing.override
    def visit_bin_op(self, bin_op: nodes.BinOp) -> None:
        bin_op.left.accept(self)
        bin_op.right.accept(self)

    @typing.override
    def visit_unary_op(self, unary_op: nodes.UnaryOp) -> None:
        unary_op.operand.accept(self)

    @typing.override
    def visit_if_exp(self, if_exp: nodes.IfExp) -> None:
        if_exp.test.accept(self)
        if_exp.true.accept(self)
        if_exp.false.accept(self)

    @typing.override
    def visit_compare(self, compare: nodes.Compare) -> None:
        compare.left.accept(self)
        for comparator in compare.comparators:
            comparator.accept(self)

    @typing.override
    def visit_call(self, call: nodes.Call) -> None:
        call.func.accept(self)
        for arg in call.args:
            arg.accept(self)
        for kwarg in call.kwargs.values():
            kwarg.accept(self)

    @typing.override
    def visit_formatted_value(self, formatted_value: nodes.FormattedValue) -> None:
        formatted_value.value.accept(self)
        if formatted_value.format_spec is not None:
            formatted_value.format_spec.accept(self)

    @typing.override
    def visit_joined_str(self, joined_str: nodes.JoinedStr) -> None:
        for value in joined_str.values:
            value.accept(self)

    @typing.override
    def visit_tuple_expr(self, tuple_expr: nodes.TupleExpr) -> None:
        for element in tuple_expr.elements:
            element.accept(self)

    @typing.override
    def visit_list_expr(self, list_expr: nodes.ListExpr) -> None:
        for element in list_expr.elements:
            element.accept(self)

    @typing.override
    def visit_dict_expr(self, dict_expr: nodes.DictExpr) -> None:
        for key, value in dict_expr.pairs:
            if key is not None:
                key.accept(self)
            value.accept(self)


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


class MatchPatternTraverser(MatchPatternVisitor[None]):
    @typing.override
    def visit_match_value(self, match_value: nodes.MatchValue) -> None:
        pass

    @typing.override
    def visit_match_sequence(self, match_sequence: nodes.MatchSequence) -> None:
        for pattern in match_sequence.patterns:
            pattern.accept(self)

    @typing.override
    def visit_match_singleton(self, match_singleton: nodes.MatchSingleton) -> None:
        pass

    @typing.override
    def visit_match_star(self, match_star: nodes.MatchStar) -> None:
        pass

    @typing.override
    def visit_match_mapping(self, match_mapping: nodes.MatchMapping) -> None:
        for pattern in match_mapping.kwd_patterns.values():
            pattern.accept(self)

    @typing.override
    def visit_match_class(self, match_class: nodes.MatchClass) -> None:
        for pattern in match_class.patterns:
            pattern.accept(self)
        for pattern in match_class.kwd_patterns.values():
            pattern.accept(self)

    @typing.override
    def visit_match_as(self, match_as: nodes.MatchAs) -> None:
        if match_as.pattern is not None:
            match_as.pattern.accept(self)

    @typing.override
    def visit_match_or(self, match_or: nodes.MatchOr) -> None:
        for pattern in match_or.patterns:
            pattern.accept(self)
