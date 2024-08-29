import typing

import mypy.nodes
import mypy.types
import mypy.visitor
from puya import log
from puya.errors import InternalError
from puya.models import ContractReference

from puyapy.awst_build import constants
from puyapy.awst_build.arc4_utils import get_arc4_abimethod_data
from puyapy.awst_build.base_mypy_visitor import BaseMyPyStatementVisitor
from puyapy.awst_build.context import ASTConversionModuleContext
from puyapy.awst_build.utils import get_decorators_by_fullname

logger = log.get_logger(__name__)


class ARC4ClientASTVisitor(BaseMyPyStatementVisitor[None]):
    def __init__(self, context: ASTConversionModuleContext, cref: ContractReference):
        super().__init__(context=context)
        self.cref: typing.Final = cref

    @classmethod
    def visit(cls, context: ASTConversionModuleContext, class_def: mypy.nodes.ClassDef) -> None:
        cref = ContractReference(class_def.info.fullname)
        visitor = ARC4ClientASTVisitor(context, cref)
        for stmt in class_def.defs.body:
            with context.log_exceptions(fallback_location=stmt):
                stmt.accept(visitor)

    def empty_statement(self, _stmt: mypy.nodes.Statement) -> None:
        return None

    def visit_function(
        self,
        func_def: mypy.nodes.FuncDef,
        decorator: mypy.nodes.Decorator | None,
    ) -> None:
        func_loc = self._location(func_def)
        if decorator is not None:
            dec_by_fullname = get_decorators_by_fullname(self.context, decorator, original=True)
            abimethod_dec = dec_by_fullname.pop(constants.ABIMETHOD_DECORATOR, None)
            for dec_fullname, dec in dec_by_fullname.items():
                logger.error(
                    f'unsupported decorator in ARC4Client: "{dec_fullname}"',
                    location=self._location(dec),
                )
            if abimethod_dec is not None:
                arc4_method_data = get_arc4_abimethod_data(self.context, abimethod_dec, func_def)
                return self.context.add_arc4_method_data(
                    self.cref, func_def.name, arc4_method_data
                )
        logger.error(f"expected an {constants.ABIMETHOD_DECORATOR} decorator", location=func_loc)

    def visit_block(self, o: mypy.nodes.Block) -> None:
        raise InternalError("shouldn't get here", self._location(o))

    def visit_return_stmt(self, stmt: mypy.nodes.ReturnStmt) -> None:
        self._error("illegal Python syntax, return in class body", location=stmt)

    def visit_class_def(self, cdef: mypy.nodes.ClassDef) -> None:
        self._error("nested classes are not supported", location=cdef)

    def _unsupported_stmt(self, kind: str, stmt: mypy.nodes.Statement) -> None:
        self._error(
            f"{kind} statements are not supported in the class body of an ARC4Client",
            location=stmt,
        )

    def visit_assignment_stmt(self, stmt: mypy.nodes.AssignmentStmt) -> None:
        self._unsupported_stmt("assignment", stmt)

    def visit_operator_assignment_stmt(self, stmt: mypy.nodes.OperatorAssignmentStmt) -> None:
        self._unsupported_stmt("operator assignment", stmt)

    def visit_expression_stmt(self, stmt: mypy.nodes.ExpressionStmt) -> None:
        if isinstance(stmt.expr, mypy.nodes.StrExpr):
            # ignore class docstring, already extracted
            # TODO: should we capture field "docstrings"?
            pass
        else:
            self._unsupported_stmt("expression statement", stmt)

    def visit_if_stmt(self, stmt: mypy.nodes.IfStmt) -> None:
        self._unsupported_stmt("if", stmt)

    def visit_while_stmt(self, stmt: mypy.nodes.WhileStmt) -> None:
        self._unsupported_stmt("while", stmt)

    def visit_for_stmt(self, stmt: mypy.nodes.ForStmt) -> None:
        self._unsupported_stmt("for", stmt)

    def visit_break_stmt(self, stmt: mypy.nodes.BreakStmt) -> None:
        self._unsupported_stmt("break", stmt)

    def visit_continue_stmt(self, stmt: mypy.nodes.ContinueStmt) -> None:
        self._unsupported_stmt("continue", stmt)

    def visit_assert_stmt(self, stmt: mypy.nodes.AssertStmt) -> None:
        self._unsupported_stmt("assert", stmt)

    def visit_del_stmt(self, stmt: mypy.nodes.DelStmt) -> None:
        self._unsupported_stmt("del", stmt)

    def visit_match_stmt(self, stmt: mypy.nodes.MatchStmt) -> None:
        self._unsupported_stmt("match", stmt)

    def visit_type_alias_stmt(self, stmt: mypy.nodes.TypeAliasStmt) -> None:
        self._unsupported_stmt("type", stmt)
