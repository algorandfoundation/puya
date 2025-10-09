from __future__ import annotations  # needed to break import cycle

import abc
import typing

if typing.TYPE_CHECKING:
    from puyapy.fast import nodes


class StatementVisitor[T](abc.ABC):
    @abc.abstractmethod
    def visit_function_def(self, func_def: nodes.FunctionDef) -> T: ...
    @abc.abstractmethod
    def visit_class_def(self, class_def: nodes.ClassDef) -> T: ...
    @abc.abstractmethod
    def visit_module_import(self, module_import: nodes.ModuleImport) -> T: ...
    @abc.abstractmethod
    def visit_from_import(self, from_import: nodes.FromImport) -> T: ...
    @abc.abstractmethod
    def visit_expression_statement(self, stmt: nodes.ExpressionStatement) -> T: ...


class ExpressionVisitor[T](abc.ABC):
    @abc.abstractmethod
    def visit_constant(self, constant: nodes.Constant) -> T: ...
