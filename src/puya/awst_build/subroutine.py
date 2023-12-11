import contextlib
import typing
from collections.abc import Iterator, Sequence
from functools import partialmethod

import attrs
import mypy.nodes
import mypy.patterns
import mypy.types
import structlog

from puya.awst import wtypes
from puya.awst.nodes import (
    AppStateDefinition,
    AssertStatement,
    AssignmentExpression,
    AssignmentStatement,
    BaseClassSubroutineTarget,
    BinaryBooleanOperator,
    Block,
    BoolConstant,
    BooleanBinaryOperation,
    BreakStatement,
    CompileTimeConstantExpression,
    ConditionalExpression,
    ContinueStatement,
    ContractMethod,
    ContractReference,
    Expression,
    ExpressionStatement,
    ForInLoop,
    FreeSubroutineTarget,
    IfElse,
    Literal,
    Lvalue,
    Not,
    ReturnStatement,
    Statement,
    Subroutine,
    SubroutineArgument,
    Switch,
    TupleExpression,
    VarExpression,
    WhileLoop,
)
from puya.awst.wtypes import WType
from puya.awst_build import constants
from puya.awst_build.base_mypy_visitor import BaseMyPyVisitor
from puya.awst_build.context import ASTConversionModuleContext
from puya.awst_build.eb.arc4 import ARC4StructClassExpressionBuilder
from puya.awst_build.eb.base import (
    BuilderBinaryOp,
    BuilderComparisonOp,
    ExpressionBuilder,
    TypeClassExpressionBuilder,
)
from puya.awst_build.eb.bool import BoolClassExpressionBuilder
from puya.awst_build.eb.contracts import (
    ContractSelfExpressionBuilder,
    LocalStorageClassExpressionBuilder,
)
from puya.awst_build.eb.ensure_budget import EnsureBudgetBuilder, OpUpFeeSourceClassBuilder
from puya.awst_build.eb.intrinsics import (
    Arc4SignatureBuilder,
    IntrinsicEnumClassExpressionBuilder,
    IntrinsicFunctionExpressionBuilder,
    IntrinsicNamespaceClassExpressionBuilder,
)
from puya.awst_build.eb.named_int_constants import NamedIntegerConstsTypeBuilder
from puya.awst_build.eb.struct import StructSubclassExpressionBuilder
from puya.awst_build.eb.subroutine import SubroutineInvokerExpressionBuilder
from puya.awst_build.eb.temporary_assignment import TemporaryAssignmentExpressionBuilder
from puya.awst_build.eb.tuple import TupleTypeExpressionBuilder
from puya.awst_build.eb.type_registry import get_type_builder
from puya.awst_build.eb.unsigned_builtins import UnsignedEnumerateBuilder, UnsignedRangeBuilder
from puya.awst_build.eb.var_factory import var_expression
from puya.awst_build.exceptions import UnsupportedASTError
from puya.awst_build.utils import (
    bool_eval,
    expect_operand_wtype,
    extract_bytes_literal_from_mypy,
    extract_docstring,
    fold_binary_expr,
    fold_unary_expr,
    get_aliased_instance,
    get_unaliased_fullname,
    iterate_user_bases,
    qualified_class_name,
    require_expression_builder,
)
from puya.errors import CodeError, InternalError, PuyaError
from puya.metadata import ARC4MethodConfig
from puya.parse import SourceLocation
from puya.utils import invert_ordered_binary_op, lazy_setdefault

logger = structlog.get_logger(__name__)


@attrs.frozen
class ContractMethodInfo:
    type_info: mypy.nodes.TypeInfo
    cref: ContractReference
    app_state: dict[str, AppStateDefinition]
    arc4_method_config: ARC4MethodConfig | None


class FunctionASTConverter(
    BaseMyPyVisitor[Statement | Sequence[Statement] | None, ExpressionBuilder | Literal]
):
    def __init__(
        self,
        context: ASTConversionModuleContext,
        func_def: mypy.nodes.FuncDef,
        contract_method_info: ContractMethodInfo | None,
    ):
        super().__init__(context=context)
        func_loc = self._location(func_def)
        self.contract_method_info = contract_method_info
        self._is_bool_context = False
        self.func_def = func_def
        self._precondition(
            func_def.abstract_status == mypy.nodes.NOT_ABSTRACT,
            "abstract functions should be skipped at a higher level",
            func_loc,
        )
        type_info = func_def.type
        self._precondition(
            isinstance(type_info, mypy.types.CallableType),
            "should only receive functions/methods with a type of CallableType",
            func_loc,
        )
        assert isinstance(type_info, mypy.types.CallableType)
        self._precondition(
            len(type_info.arg_types) == len(func_def.arguments),
            "FuncDef argument type list length should match arguments list length",
            func_loc,
        )
        # convert the return type
        self._return_type = self.context.type_to_wtype(
            type_info.ret_type, source_location=func_loc
        )
        # check & convert the arguments
        mypy_args = func_def.arguments
        mypy_arg_types = type_info.arg_types
        if func_def.info is not mypy.nodes.FUNC_NO_INFO:  # why god why
            # function is a method
            self._precondition(
                bool(mypy_args) and mypy_args[0].variable.is_self,
                "if function is a method, first variable should be self-like",
                func_loc,
            )
            mypy_args = mypy_args[1:]
            mypy_arg_types = mypy_arg_types[1:]
        elif mypy_args:
            self._precondition(
                not mypy_args[0].variable.is_self,
                "if function is not a method, first variable should be self-like",
                func_loc,
            )
        # TODO: this should be more than just type?
        self._symtable = dict[str, WType]()
        args = list[SubroutineArgument]()
        for arg, arg_type in zip(mypy_args, mypy_arg_types, strict=True):
            if arg.kind.is_star():
                raise UnsupportedASTError(func_loc, details="variadic functions are not supported")
            if arg.initializer is not None:
                self._error(
                    "default function argument values are not supported yet", arg.initializer
                )
            wtype = self.context.type_to_wtype(arg_type, source_location=arg)
            arg_name = arg.variable.name
            args.append(SubroutineArgument(self._location(arg), arg_name, wtype))
            self._symtable[arg_name] = wtype
        # extract docstring if specified
        docstring = extract_docstring(func_def)
        # translate body
        translated_body = self.visit_block(func_def.body)
        # build result
        self.result: Subroutine | ContractMethod
        if self.contract_method_info is None:
            self.result = Subroutine(
                module_name=self.context.module_name,
                name=func_def.name,
                source_location=self._location(func_def),
                args=args,
                return_type=self._return_type,
                body=translated_body,
                docstring=docstring,
            )
        else:
            self.result = ContractMethod(
                module_name=self.contract_method_info.cref.module_name,
                class_name=self.contract_method_info.cref.class_name,
                name=func_def.name,
                source_location=self._location(func_def),
                args=args,
                return_type=self._return_type,
                body=translated_body,
                docstring=docstring,
                abimethod_config=self.contract_method_info.arc4_method_config,
            )

    @classmethod
    @typing.overload
    def convert(
        cls, context: ASTConversionModuleContext, func_def: mypy.nodes.FuncDef
    ) -> Subroutine:
        ...

    @classmethod
    @typing.overload
    def convert(
        cls,
        context: ASTConversionModuleContext,
        func_def: mypy.nodes.FuncDef,
        contract_method_info: ContractMethodInfo,
    ) -> ContractMethod:
        ...

    @classmethod
    def convert(
        cls,
        context: ASTConversionModuleContext,
        func_def: mypy.nodes.FuncDef,
        contract_method_info: ContractMethodInfo | None = None,
    ) -> Subroutine | ContractMethod:
        return cls(
            context=context, func_def=func_def, contract_method_info=contract_method_info
        ).result

    def visit_block(self, block: mypy.nodes.Block) -> Block:
        translated_body = []
        for stmt in block.body:
            translated_stmt = stmt.accept(self)
            if translated_stmt is None:
                pass
            elif isinstance(translated_stmt, Statement):
                translated_body.append(translated_stmt)
            else:
                translated_body.extend(translated_stmt)
        return Block(
            source_location=self._location(block),
            body=translated_body,
        )

    @contextlib.contextmanager
    def _set_bool_context(self, *, is_bool_context: bool) -> Iterator[None]:
        was_in_bool_context = self._is_bool_context
        self._is_bool_context = is_bool_context
        try:
            yield
        finally:
            self._is_bool_context = was_in_bool_context

    _enter_bool_context = partialmethod(_set_bool_context, is_bool_context=True)
    _leave_bool_context = partialmethod(_set_bool_context, is_bool_context=False)

    def visit_expression_stmt(self, stmt: mypy.nodes.ExpressionStmt) -> ExpressionStatement:
        self._precondition(
            stmt.line == stmt.expr.line
            and stmt.end_line == stmt.expr.end_line
            and stmt.column == stmt.expr.column
            and stmt.end_column == stmt.expr.end_column,
            "statement express location should match expression location",
            stmt,
        )
        stmt_loc = self._location(stmt)
        if isinstance(stmt.expr, mypy.nodes.TupleExpr) and len(stmt.expr.items) == 1:
            raise CodeError(
                "Tuple being constructed without assignment,"
                " check for a stray comma at the end of the statement",
                stmt_loc,
            )
        expr = require_expression_builder(stmt.expr.accept(self)).rvalue()
        if expr.wtype is not wtypes.void_wtype:
            # special case to ignore ignoring the result of typing.reveal_type
            if not (
                isinstance(stmt.expr, mypy.nodes.CallExpr)
                and isinstance(stmt.expr.analyzed, mypy.nodes.RevealExpr)
            ):
                self.context.warning("expression result is ignored", stmt_loc)
        else:
            # TODO: should we do some checks here to warn if it's something
            #       with zero side effects? Can we even determine that simply & reliably?
            pass
        return ExpressionStatement(expr=expr)

    def visit_assignment_stmt(self, stmt: mypy.nodes.AssignmentStmt) -> Sequence[Statement]:
        stmt_loc = self._location(stmt)
        match stmt.lvalues:
            case [mypy.nodes.NameExpr(is_special_form=True)]:
                self._error(
                    "type aliases, type vars, and type constructors"
                    " are not supported inside functions",
                    stmt_loc,
                )
                return []
        match stmt.rvalue:
            case mypy.nodes.TempNode(no_rhs=True):
                # forward type-declaration only
                self._precondition(
                    len(stmt.lvalues) == 1 and isinstance(stmt.lvalues[0], mypy.nodes.RefExpr),
                    "forward type declarations should only have one target,"
                    " and it should be a RefExpr",
                    stmt_loc,
                )
                return []
        rvalue = require_expression_builder(stmt.rvalue.accept(self))
        # special no-op case
        if isinstance(rvalue, LocalStorageClassExpressionBuilder):
            if len(stmt.lvalues) != 1:
                raise CodeError(
                    "Local state can only be assigned to a single member variable", stmt_loc
                )
            return []
        if len(stmt.lvalues) == 1:
            value = rvalue.build_assignment_source()
            (lvalue,) = stmt.lvalues
            target = self.resolve_lvalue(lvalue)
            return [AssignmentStatement(source_location=stmt_loc, target=target, value=value)]
        else:
            single_eval_wrapper = temporary_assignment_if_required(rvalue)
            return [
                AssignmentStatement(
                    source_location=stmt_loc,
                    target=self.resolve_lvalue(lvalue),
                    value=single_eval_wrapper.build_assignment_source(),
                )
                for lvalue in reversed(stmt.lvalues)
            ]

    def resolve_lvalue(self, lvalue: mypy.nodes.Expression) -> Lvalue:
        builder_or_literal = lvalue.accept(self)
        builder = require_expression_builder(builder_or_literal)
        return builder.lvalue()

    def empty_statement(self, _tmt: mypy.nodes.Statement) -> None:
        return None

    def visit_operator_assignment_stmt(self, stmt: mypy.nodes.OperatorAssignmentStmt) -> Statement:
        stmt_loc = self._location(stmt)
        builder = require_expression_builder(stmt.lvalue.accept(self))
        rhs = stmt.rvalue.accept(self)
        try:
            op = BuilderBinaryOp(stmt.op)
        except ValueError as ex:
            raise InternalError(f"Unknown binary operator: {stmt.op}") from ex
        return builder.augmented_assignment(op=op, rhs=rhs, location=stmt_loc)

    def visit_if_stmt(self, stmt: mypy.nodes.IfStmt) -> IfElse:
        self._precondition(
            len(stmt.body) == len(stmt.expr),
            "mismatch between if statement condition list length and body list length",
            stmt,
        )
        self._precondition(
            len(stmt.expr) == 1,
            "python ast module should produce normalised if statements",
            stmt,
        )
        (expr,) = stmt.expr
        (if_body,) = stmt.body
        condition = self._eval_condition(expr)
        if_branch = self.visit_block(if_body)
        else_branch = self.visit_block(stmt.else_body) if stmt.else_body else None
        return IfElse(
            source_location=self._location(stmt),
            condition=condition,
            if_branch=if_branch,
            else_branch=else_branch,
        )

    def _eval_condition(self, mypy_expr: mypy.nodes.Expression) -> Expression:
        with self._enter_bool_context():
            builder_or_literal = mypy_expr.accept(self)
        loc = self._location(mypy_expr)
        condition = bool_eval(builder_or_literal, loc)
        return condition.rvalue()

    def visit_while_stmt(self, stmt: mypy.nodes.WhileStmt) -> WhileLoop:
        if stmt.else_body is not None:
            self._error("else clause on while loop not supported", self._location(stmt))
        condition = self._eval_condition(stmt.expr)
        loop_body = self.visit_block(stmt.body)
        return WhileLoop(
            source_location=self._location(stmt),
            condition=condition,
            loop_body=loop_body,
        )

    def visit_for_stmt(self, stmt: mypy.nodes.ForStmt) -> ForInLoop:
        stmt_loc = self._location(stmt)
        if stmt.else_body is not None:
            self._error("else clause on for loop not supported", stmt_loc)
        sequence_builder = require_expression_builder(stmt.expr.accept(self))
        sequence = sequence_builder.iterate()
        items = self.resolve_lvalue(stmt.index)
        loop_body = self.visit_block(stmt.body)
        return ForInLoop(
            source_location=stmt_loc,
            items=items,
            sequence=sequence,
            loop_body=loop_body,
        )

    def visit_break_stmt(self, stmt: mypy.nodes.BreakStmt) -> BreakStatement:
        return BreakStatement(self._location(stmt))

    def visit_continue_stmt(self, stmt: mypy.nodes.ContinueStmt) -> ContinueStatement:
        return ContinueStatement(self._location(stmt))

    def visit_assert_stmt(self, stmt: mypy.nodes.AssertStmt) -> AssertStatement:
        comment: str | None
        match stmt.msg:
            case mypy.nodes.StrExpr() as str_expr:
                comment = str_expr.value
            case None:
                comment = None
            case _:
                self._error("only literal strings are supported as assertion messages", stmt)
                comment = None
        condition = self._eval_condition(stmt.expr)
        return AssertStatement(
            source_location=self._location(stmt),
            condition=condition,
            comment=comment,
        )

    def visit_del_stmt(self, stmt: mypy.nodes.DelStmt) -> Statement:
        stmt_expr = stmt.expr.accept(self)
        del_item = require_expression_builder(stmt_expr)
        return del_item.delete(self._location(stmt))

    def visit_return_stmt(self, stmt: mypy.nodes.ReturnStmt) -> ReturnStatement | None:
        loc = self._location(stmt)
        return_expr = stmt.expr
        if return_expr is None:
            if self._return_type != wtypes.void_wtype:
                self._error(
                    "function is typed as returning a value, so a value must be returned", loc
                )
            return ReturnStatement(source_location=loc, value=None)

        returning = require_expression_builder(return_expr.accept(self)).rvalue()
        if returning.wtype != self._return_type:
            self._error("invalid return type", loc)
        return ReturnStatement(source_location=loc, value=returning)

    def visit_match_stmt(self, stmt: mypy.nodes.MatchStmt) -> Switch | None:
        loc = self._location(stmt)
        subject = require_expression_builder(
            temporary_assignment_if_required(stmt.subject.accept(self))
        ).rvalue()
        case_block_map = dict[Expression, Block]()
        default_block: Block | None = None
        for pattern, guard, block in zip(stmt.patterns, stmt.guards, stmt.bodies, strict=True):
            match pattern, guard:
                case mypy.patterns.ValuePattern(expr=case_expr), None:
                    case_value_builder_or_literal = case_expr.accept(self)
                    case_value = expect_operand_wtype(case_value_builder_or_literal, subject.wtype)
                    case_block = self.visit_block(block)
                    case_block_map[case_value] = case_block
                case mypy.patterns.AsPattern(name=None, pattern=None), None:
                    default_block = self.visit_block(block)
                case _:
                    self._error(
                        "match statements only support value patterns without guards", stmt
                    )
                    break
        else:
            return Switch(
                source_location=loc,
                value=subject,
                cases=case_block_map,
                default_case=default_block,
            )
        return None

    # Unsupported statements

    def visit_function(self, fdef: mypy.nodes.FuncDef, _: mypy.nodes.Decorator | None) -> None:
        self._error("nested functions are not supported", fdef)

    def visit_nonlocal_decl(self, stmt: mypy.nodes.NonlocalDecl) -> None:
        self._error("nested functions are not supported", stmt)

    def visit_class_def(self, cdef: mypy.nodes.ClassDef) -> None:
        self._error("classes nested inside functions are not supported", cdef)

    # Expressions
    def _visit_ref_expr(
        self, expr: mypy.nodes.MemberExpr | mypy.nodes.NameExpr
    ) -> ExpressionBuilder | Literal:
        expr_loc = self._location(expr)
        builder_or_literal = self._visit_ref_expr_maybe_aliased(expr, expr_loc)
        # as an extra step, in case the resolved item was a type through a TypeAlias,
        # we need to apply the specified arguments to the type
        if aliased_type := get_aliased_instance(expr):
            if not isinstance(builder_or_literal, ExpressionBuilder):
                raise InternalError(
                    "Encountered an aliased instance that generated a Literal",
                    expr_loc,
                )
            alias_type_args = [self._visit_type_arg(a, expr_loc) for a in aliased_type.args]
            return _maybe_index(builder_or_literal, alias_type_args, expr_loc)
        return builder_or_literal

    def _visit_ref_expr_maybe_aliased(
        self, expr: mypy.nodes.MemberExpr | mypy.nodes.NameExpr, expr_loc: SourceLocation
    ) -> ExpressionBuilder | Literal:
        if expr.name == "__all__":
            # special case here, we allow __all__ at the module level for it's "public vs private"
            # control implications w.r.t linting etc, but we do so by ignoring it.
            # so this is here just in case someone tries to reference __all__ inside a function,
            # to give a more useful error message.
            raise CodeError("__all__ cannot be referenced inside functions", expr_loc)

        fullname = get_unaliased_fullname(expr)
        if fullname.startswith("builtins."):
            return self._visit_ref_expr_of_builtins(fullname, expr_loc)
        if fullname.startswith(constants.PUYAPY_PREFIX):
            return self._visit_ref_expr_of_puyapy(fullname, expr_loc, expr.node)
        match expr:
            case mypy.nodes.RefExpr(node=mypy.nodes.TypeInfo() as typ) if (
                typ.has_base(constants.STRUCT_BASE) or typ.has_base(constants.CLS_ARC4_STRUCT)
            ):
                try:
                    wtype = self.context.type_map[fullname]
                except KeyError:
                    raise CodeError(
                        f"Unknown struct subclass {fullname}"
                        " (declaration must currently precede usage)",
                        expr_loc,
                    ) from None
                if isinstance(wtype, wtypes.WStructType):
                    return StructSubclassExpressionBuilder(wtype, expr_loc)
                else:
                    return ARC4StructClassExpressionBuilder(wtype, expr_loc)
            case mypy.nodes.NameExpr(node=mypy.nodes.Var(is_self=True) as self_var):
                if self.contract_method_info is None:
                    raise InternalError(
                        "encountered variable marked as is_self in function", expr_loc
                    )
                self._precondition(
                    isinstance(self_var.type, mypy.types.Instance)
                    and self_var.type.type is self.contract_method_info.type_info,
                    "type info for self var does not match current class",
                    expr,
                )
                return ContractSelfExpressionBuilder(
                    context=self.context,
                    app_state=self.contract_method_info.app_state,
                    location=expr_loc,
                )
            case mypy.nodes.RefExpr(
                node=mypy.nodes.Decorator(
                    decorators=decorators,
                    type=mypy.types.CallableType() as func_type,
                )
            ) if any(
                get_unaliased_fullname(de) == constants.SUBROUTINE_HINT
                for de in decorators
                if isinstance(de, mypy.nodes.RefExpr)  # TODO: why wouldn't this be a RefExpr
            ):
                func_name = expr.name
                module_name = fullname.removesuffix(func_name).removesuffix(".")
                self._precondition(
                    bool(module_name), "unqualified name found in call to function", expr_loc
                )
                return SubroutineInvokerExpressionBuilder(
                    context=self.context,
                    target=FreeSubroutineTarget(module_name=module_name, name=func_name),
                    location=expr_loc,
                    func_type=func_type,
                )
            case mypy.nodes.RefExpr(node=mypy.nodes.FuncDef()):
                raise CodeError(
                    f"Cannot invoke {fullname} as it is not "
                    f"decorated with {constants.SUBROUTINE_HINT_ALIAS}",
                    expr_loc,
                )
            # TODO: is this enough to filter to only global variable references?
            #       it seems like it should be...
            case mypy.nodes.RefExpr(kind=mypy.nodes.GDEF, node=mypy.nodes.Var()):
                self._precondition(
                    not (
                        expr.is_new_def
                        or expr.is_inferred_def
                        or expr.is_alias_rvalue
                        or (isinstance(expr, mypy.nodes.NameExpr) and expr.is_special_form)
                    ),
                    "global variable reference with unexpected flags",
                    expr_loc,
                )
                try:
                    constant_value = self.context.constants[expr.fullname]
                except KeyError as ex:
                    # TODO: allow arbitrary ordering
                    raise CodeError(
                        "Unable to resolve global constant reference"
                        " - note that constants must appear before any references to them",
                        expr_loc,
                    ) from ex
                else:
                    return Literal(source_location=expr_loc, value=constant_value)
            case (
                mypy.nodes.NameExpr(
                    kind=mypy.nodes.LDEF, node=mypy.nodes.Var(), name=var_name
                ) as name_expr
            ):
                self._precondition(
                    not name_expr.is_special_form,
                    "special form lvalues should only appear"
                    " as a singular lvalue in an assignment statement",
                    expr_loc,
                )
                if var_name == "_":
                    # TODO: ignore "_"
                    raise CodeError("_ is not currently supported as a variable name", expr_loc)
                local_type = lazy_setdefault(
                    self._symtable,
                    key=var_name,
                    default=lambda _: self.context.mypy_expr_node_type(name_expr),
                )
                var_expr = VarExpression(
                    source_location=expr_loc,
                    wtype=local_type,
                    name=var_name,
                )
                return var_expression(var_expr)
        scope = {
            mypy.nodes.LDEF: "local",
            mypy.nodes.MDEF: "member",
            mypy.nodes.GDEF: "global",
            None: "unknown",
        }.get(expr.kind)
        raise InternalError(
            f'Unable to resolve reference to "{fullname}" with scope "{scope}"'
            f" (node = {expr.node})",
            expr_loc,
        )

    @staticmethod
    def _visit_ref_expr_of_builtins(
        fullname: str, location: SourceLocation
    ) -> ExpressionBuilder | Literal:
        assert fullname.startswith("builtins.")
        rest_of_name = fullname.removeprefix("builtins.")
        match rest_of_name:
            case "True":
                return Literal(source_location=location, value=True)
            case "False":
                return Literal(source_location=location, value=False)
            case "None":
                raise CodeError("None is not supported as a value, only a return type", location)
            case "bool":
                return BoolClassExpressionBuilder(location=location)
            case "len":
                raise CodeError(
                    "len() is not supported -"
                    " types with a length will have a .length property instead",
                    location,
                )
            case "range":
                raise CodeError("range() is not supported - use puyapy.urange() instead", location)
            case "enumerate":
                raise CodeError(
                    "enumerate() is not supported - use puyapy.uenumerate() instead", location
                )
            case _:
                raise CodeError(f"Unsupported builtin: {rest_of_name}", location)

    def _visit_ref_expr_of_puyapy(
        self, fullname: str, location: SourceLocation, node: mypy.nodes.SymbolNode | None
    ) -> ExpressionBuilder:
        if fullname.startswith(constants.PUYAPY_GEN_PREFIX):
            if isinstance(node, mypy.nodes.TypeAlias):
                t = mypy.types.get_proper_type(node.target)
                if isinstance(t, mypy.types.Instance):
                    node = t.type
            match node:
                case mypy.nodes.TypeInfo(is_enum=True):
                    return IntrinsicEnumClassExpressionBuilder(fullname, location=location)
                case mypy.nodes.TypeInfo() as type_info:
                    return IntrinsicNamespaceClassExpressionBuilder(type_info, location=location)
                case mypy.nodes.FuncDef() as func_def:
                    return IntrinsicFunctionExpressionBuilder(func_def, location=location)
                case _:
                    raise InternalError(f"Unhandled puyapy name: {fullname}", location)
        match fullname:
            case constants.URANGE:
                return UnsignedRangeBuilder(location=location)
            case constants.UENUMERATE:
                return UnsignedEnumerateBuilder(location=location)
            case constants.ARC4_SIGNATURE:
                return Arc4SignatureBuilder(location=location)
            case constants.ENSURE_BUDGET:
                return EnsureBudgetBuilder(location=location)
            case constants.OP_UP_FEE_SOURCE:
                return OpUpFeeSourceClassBuilder(location=location)
            case constants.LOCAL_PROXY_CLS:
                if self.contract_method_info is None:
                    raise CodeError(
                        f"{constants.LOCAL_PROXY_CLS} is only usable in contract instance methods",
                        location,
                    )
                return LocalStorageClassExpressionBuilder(location=location)
            case _ as enum_name if enum_name in constants.NAMED_INT_CONST_ENUM_DATA:
                return NamedIntegerConstsTypeBuilder(
                    enum_name=enum_name,
                    data=constants.NAMED_INT_CONST_ENUM_DATA[enum_name],
                    location=location,
                )
        return get_type_builder(fullname, location)

    def visit_name_expr(self, expr: mypy.nodes.NameExpr) -> ExpressionBuilder | Literal:
        return self._visit_ref_expr(expr)

    def _visit_type_arg(
        self, mypy_type: mypy.types.Type, location: SourceLocation
    ) -> ExpressionBuilder | Literal:
        match mypy_type:
            case mypy.types.Instance() as instance:
                fullname = instance.type.fullname
                if fullname.startswith("builtins."):
                    return self._visit_ref_expr_of_builtins(fullname, location)
                if fullname.startswith(constants.PUYAPY_PREFIX):
                    return self._visit_ref_expr_of_puyapy(fullname, location, None)
                raise InternalError("Cannot handle instance of this type: " + fullname)
            case mypy.types.LiteralType(value=literal_value):
                if isinstance(literal_value, float):
                    raise CodeError("Float literals are not supported", location)
                return Literal(value=literal_value, source_location=location)
            case mypy.types.TypeAliasType() as ta:
                typ = mypy.types.get_proper_type(ta)
                target = self._visit_type_arg(typ, location)
                if isinstance(target, ExpressionBuilder) and isinstance(typ, mypy.types.Instance):
                    args = [self._visit_type_arg(arg, location) for arg in typ.args]
                    return _maybe_index(target, args, location)
                return target
            case mypy.types.TupleType(items=items):
                tuple_eb = TupleTypeExpressionBuilder(location)
                return tuple_eb.index_multiple(
                    [self._visit_type_arg(item, location) for item in items], location
                )
        raise InternalError("Unsupported mypy_type argument")

    def visit_member_expr(self, expr: mypy.nodes.MemberExpr) -> ExpressionBuilder | Literal:
        if isinstance(expr.expr, mypy.nodes.RefExpr) and isinstance(
            expr.expr.node, mypy.nodes.MypyFile
        ):
            # special case for module attribute access
            return self._visit_ref_expr(expr)

        base = expr.expr.accept(self)
        base_builder = require_expression_builder(base)
        return base_builder.member_access(name=expr.name, location=self._location(expr))

    def visit_call_expr(self, call: mypy.nodes.CallExpr) -> ExpressionBuilder | Literal:
        if call.analyzed is not None:
            return self._visit_special_call_expr(call, analyzed=call.analyzed)

        callee = call.callee.accept(self)
        callee_builder = require_expression_builder(callee)
        if (
            isinstance(callee_builder, TypeClassExpressionBuilder)
            and callee_builder.produces() == wtypes.bool_wtype
        ):
            args_context: typing.Any = self._enter_bool_context
        else:
            args_context = contextlib.nullcontext
        with args_context():
            args = [arg.accept(self) for arg in call.args]
        return callee_builder.call(
            args=args,
            arg_kinds=call.arg_kinds,
            arg_names=call.arg_names,
            location=self._location(call),
            original_expr=call,
        )

    def _visit_special_call_expr(
        self, call: mypy.nodes.CallExpr, *, analyzed: mypy.nodes.Expression
    ) -> ExpressionBuilder | Literal:
        match analyzed:
            case mypy.nodes.CastExpr(expr=inner_expr):
                self.context.warning(
                    "use of typing.cast, output may be invalid or insecure TEAL", call
                )
                return inner_expr.accept(self)
            case mypy.nodes.AssertTypeExpr(expr=inner_expr):
                # just FYI... in case the user thinks this has a runtime effect
                # (it doesn't, not even in Python)
                self.context.warning(
                    "use of typing.assert_type has no effect on compilation", call
                )
                return inner_expr.accept(self)
            case mypy.nodes.RevealExpr(expr=mypy.nodes.Expression() as inner_expr):
                result = inner_expr.accept(self)
                if isinstance(result, Literal):
                    self.context.note(f"puyapy node is literal of {result.value!r}", call)
                else:
                    try:
                        the_value = result.rvalue()
                    except PuyaError:
                        self.context.note(f"puyapy node is {result!r}", call)
                    else:
                        self.context.note(f'puyapy type is "{the_value.wtype.name}"', call)
                return result
            case _:
                raise CodeError(
                    f"Unsupported special function call"
                    f" of analyzed type {type(analyzed).__name__}",
                    self._location(call),
                )

    def visit_unary_expr(self, node: mypy.nodes.UnaryExpr) -> ExpressionBuilder | Literal:
        expr_loc = self._location(node)
        builder_or_literal = node.expr.accept(self)
        if isinstance(builder_or_literal, Literal):
            folded_result = fold_unary_expr(expr_loc, node.op, builder_or_literal.value)
            return Literal(value=folded_result, source_location=expr_loc)
        match node.op:
            case "not":
                return builder_or_literal.bool_eval(expr_loc, negate=True)
            case "+":
                return builder_or_literal.unary_plus(expr_loc)
            case "-":
                return builder_or_literal.unary_minus(expr_loc)
            case "~":
                return builder_or_literal.bitwise_invert(expr_loc)
            case _:
                # guard against future python unary operators
                raise InternalError(f"Unable to interpret unary operator '{node.op}'", expr_loc)

    def visit_op_expr(self, node: mypy.nodes.OpExpr) -> Literal | ExpressionBuilder:
        node_loc = self._location(node)
        lhs = node.left.accept(self)
        rhs = node.right.accept(self)

        # constant fold if both literals
        if isinstance(lhs, Literal) and isinstance(rhs, Literal):
            # TODO: this shouldn't typecheck (as in our code, not user code), need to
            #       make mypy stricter (one day)
            folded_result = fold_binary_expr(
                location=node_loc, op=node.op, lhs=lhs.value, rhs=rhs.value
            )
            return Literal(value=folded_result, source_location=node_loc)

        # mypy combines ast.BoolOp and ast.BinOp, but they're kinda different...
        if node.op in ("and", "or"):
            bool_op = BinaryBooleanOperator(node.op)
            result_mypy_type = self.context.get_mypy_expr_type(node)
            bool_expr = self._visit_bool_op_expr(
                bool_op, result_mypy_type, lhs=lhs, rhs=rhs, location=node_loc
            )
            return var_expression(bool_expr)

        try:
            op = BuilderBinaryOp(node.op)
        except ValueError as ex:
            raise InternalError(f"Unknown binary operator: {node.op}") from ex

        result: ExpressionBuilder = NotImplemented
        if isinstance(lhs, ExpressionBuilder):
            result = lhs.binary_op(other=rhs, op=op, location=node_loc, reverse=False)
        if result is NotImplemented and isinstance(rhs, ExpressionBuilder):
            result = rhs.binary_op(other=lhs, op=op, location=node_loc, reverse=True)
        if result is NotImplemented:
            raise CodeError(f"Unsupported operation {op.value} between types", node_loc)
        return result

    def _visit_bool_op_expr(
        self,
        op: BinaryBooleanOperator,
        result_mypy_type: mypy.types.Type,
        lhs: ExpressionBuilder | Literal,
        rhs: ExpressionBuilder | Literal,
        location: SourceLocation,
    ) -> Expression:
        # when in a boolean evaluation context, we can side step issues of type unions
        # and what not, and just assume everything is boolean.
        # note that this won't solve all potential use cases, and indeed some of them are
        # unsolvable without a more runtime infrastructure.
        # for example, this will allow:
        # a = UInt64(...)
        # b = Bytes(...)
        # if a and b:
        #   ...
        # but obviously we cannot handle
        # c = a and b
        # you wouldn't be able to do anything with c, since in general we can't know at compile
        # time what the type of c is, and the AVM doesn't provide any type introspection.
        # even if there was an op that said whether a stack item or a scratch slot etc held
        # a bytes[] or a uint64, there are differences between logical types and physical types
        # that need to be accounted for - for example, biguint is a bytes[] but we would need
        # to use a different equality op b== instead of ==
        # also note, because we evaluate this to bool here, there will be mismatch between
        # mypy types and wtype after this, so if you tried, say:
        # assert (a and b) == a
        # this would fail to compile, due to (a and b) being wtype of bool.
        # this is fine and expected, there's no issues of semantic compatibility since we
        # reject compiling the program altogether.
        if isinstance(result_mypy_type, mypy.types.UnionType) and len(result_mypy_type.items) > 1:
            if not self._is_bool_context:
                raise CodeError(
                    "expression would produce a union type,"
                    " which isn't supported unless evaluating a boolean condition",
                    location,
                )
            target_wtype = wtypes.bool_wtype
            lhs_expr = bool_eval(lhs, location).rvalue()
            rhs_expr = bool_eval(rhs, location).rvalue()
        else:
            target_wtype = self.context.type_to_wtype(result_mypy_type, source_location=location)
            lhs_expr = expect_operand_wtype(lhs, target_wtype)
            rhs_expr = expect_operand_wtype(rhs, target_wtype)

        if target_wtype == wtypes.bool_wtype:
            return BooleanBinaryOperation(
                source_location=location, left=lhs_expr, op=op, right=rhs_expr
            )
        lhs_builder = temporary_assignment_if_required(lhs_expr)
        # (lhs:uint64 and rhs:uint64) => lhs_tmp_var if not bool(lhs_tmp_var := lhs) else rhs
        # (lhs:uint64 or rhs:uint64) => lhs_tmp_var if bool(lhs_tmp_var := lhs) else rhs
        # TODO: this is a bit convoluted in terms of ExpressionBuilder <-> Expression
        condition = lhs_builder.bool_eval(
            location, negate=op is BinaryBooleanOperator.and_
        ).rvalue()
        return ConditionalExpression(
            source_location=location,
            condition=condition,
            true_expr=lhs_builder.rvalue(),
            false_expr=rhs_expr,
            wtype=target_wtype,
        )

    def visit_index_expr(self, expr: mypy.nodes.IndexExpr) -> ExpressionBuilder | Literal:
        # short-circuit in case of application of typing.Literal to just evaluate the args
        if (
            isinstance(expr.base, mypy.nodes.RefExpr)
            and get_unaliased_fullname(expr.base) == "typing.Literal"
        ):
            return expr.index.accept(self)

        base_expr = expr.base.accept(self)
        if isinstance(base_expr, Literal):
            raise CodeError(
                "Python literals cannot be indexed or sliced", base_expr.source_location
            )
        expr_location = self._location(expr)
        match expr.index:
            # special case handling of SliceExpr, so we don't need to handle slice Literal's
            # or some such everywhere
            case mypy.nodes.SliceExpr(begin_index=begin, end_index=end, stride=stride):
                return base_expr.slice_index(
                    # my kingdom for a ?. operator...
                    begin_index=begin.accept(self) if begin else None,
                    end_index=end.accept(self) if end else None,
                    stride=stride.accept(self) if stride else None,
                    location=expr_location,
                )
            case mypy.nodes.TupleExpr(items=items):
                args = [item.accept(self) for item in items]
                return base_expr.index_multiple(index=args, location=expr_location)

        index_expr_or_literal = expr.index.accept(self)
        return base_expr.index(index=index_expr_or_literal, location=expr_location)

    def visit_conditional_expr(self, expr: mypy.nodes.ConditionalExpr) -> ExpressionBuilder:
        condition = self._eval_condition(expr.cond)
        true_expr = require_expression_builder(expr.if_expr.accept(self)).rvalue()
        false_expr = require_expression_builder(expr.else_expr.accept(self)).rvalue()
        expr_wtype = self.context.mypy_expr_node_type(expr)
        if expr_wtype != true_expr.wtype:
            self._error(
                "Incompatible result type for 'true' expression", true_expr.source_location
            )
        if expr_wtype != false_expr.wtype:
            self._error(
                "Incompatible result type for 'else' expression branch", false_expr.source_location
            )

        cond_expr = ConditionalExpression(
            source_location=self._location(expr),
            condition=condition,
            true_expr=true_expr,
            false_expr=false_expr,
            wtype=expr_wtype,
        )
        return var_expression(cond_expr)

    def visit_comparison_expr(self, expr: mypy.nodes.ComparisonExpr) -> ExpressionBuilder:
        expr_loc = self._location(expr)
        self._precondition(
            len(expr.operands) == (len(expr.operators) + 1),
            "operands don't match with operators",
            expr_loc,
        )
        # we can decompose this into a series of AND operations, but potentially need to generate
        # assignment expressions for everything except first and last operands, e.g.:
        #   a < b < c
        # becomes:
        #   (a < (tmp := b)) AND (tmp < c)
        # TODO: what about comparing different types that can never be equal? according to Python
        #       type signatures that should be possible, and we can always know it's value at
        #       compile time, but it would always result in a constant ...

        expr_wtype = self.context.mypy_expr_node_type(expr)
        if expr_wtype is not wtypes.bool_wtype:
            raise CodeError("Result of comparison must be a boolean type", expr_loc)

        operands = [o.accept(self) for o in expr.operands]
        operands[1:-1] = [temporary_assignment_if_required(operand) for operand in operands[1:-1]]

        comparisons = [
            self._build_compare(operator=operator, lhs=lhs, rhs=rhs)
            for operator, lhs, rhs in zip(expr.operators, operands, operands[1:], strict=False)
        ]

        result = prev = comparisons[0]
        for curr in comparisons[1:]:
            result = BooleanBinaryOperation(
                source_location=prev.source_location + curr.source_location,
                left=result,
                op=BinaryBooleanOperator.and_,
                right=curr,
            )
            prev = curr
        return var_expression(result)

    def _build_compare(
        self,
        operator: str,
        lhs: ExpressionBuilder | Literal,
        rhs: ExpressionBuilder | Literal,
    ) -> Expression:
        cmp_loc = lhs.source_location + rhs.source_location
        if isinstance(lhs, Literal) and isinstance(rhs, Literal):
            return BoolConstant(
                value=bool(fold_binary_expr(cmp_loc, operator, lhs.value, rhs.value)),
                source_location=cmp_loc,
            )

        match operator:
            case "not in":
                is_in_expr = self._build_compare("in", lhs=lhs, rhs=rhs)
                return Not(is_in_expr.source_location, is_in_expr)
            case "in":
                container_builder = require_expression_builder(rhs)
                contains_builder = container_builder.contains(lhs, cmp_loc)
                return contains_builder.rvalue()

        result: ExpressionBuilder = NotImplemented
        if isinstance(lhs, ExpressionBuilder):
            op = BuilderComparisonOp(operator)
            result = lhs.compare(other=rhs, op=op, location=cmp_loc)
        if result is NotImplemented and isinstance(rhs, ExpressionBuilder):
            op = BuilderComparisonOp(invert_ordered_binary_op(operator))
            result = rhs.compare(other=lhs, op=op, location=cmp_loc)
        if result is NotImplemented:
            raise CodeError(f"Unsupported comparison {operator} between types", cmp_loc)
        return result.rvalue()

    def visit_int_expr(self, expr: mypy.nodes.IntExpr) -> Literal:
        return Literal(self._location(expr), value=expr.value)

    def visit_str_expr(self, expr: mypy.nodes.StrExpr) -> Literal:
        return Literal(self._location(expr), value=expr.value)

    def visit_bytes_expr(self, expr: mypy.nodes.BytesExpr) -> Literal:
        bytes_const = extract_bytes_literal_from_mypy(expr)
        return Literal(self._location(expr), value=bytes_const)

    def visit_tuple_expr(self, mypy_expr: mypy.nodes.TupleExpr) -> ExpressionBuilder:
        items = [
            require_expression_builder(
                mypy_item.accept(self),
                msg="Python literals (other than True/False) are not valid as tuple elements",
            ).rvalue()
            for mypy_item in mypy_expr.items
        ]
        wtype = wtypes.WTuple.from_types(i.wtype for i in items)
        tuple_expr = TupleExpression(
            source_location=self._location(mypy_expr),
            wtype=wtype,
            items=items,
        )
        return var_expression(tuple_expr)

    def visit_assignment_expr(self, expr: mypy.nodes.AssignmentExpr) -> ExpressionBuilder:
        expr_loc = self._location(expr)
        self._precondition(
            not isinstance(expr, mypy.nodes.TupleExpr | mypy.nodes.ListExpr),
            "Python doesn't support tuple unpacking in assignment expressions",
            expr_loc,
        )
        with self._leave_bool_context():
            source = require_expression_builder(expr.value.accept(self))
        value = source.build_assignment_source()
        target = self.resolve_lvalue(expr.target)
        result = AssignmentExpression(source_location=expr_loc, value=value, target=target)
        return var_expression(result)

    def visit_super_expr(self, super_expr: mypy.nodes.SuperExpr) -> ExpressionBuilder:
        super_loc = self._location(super_expr)
        if self.contract_method_info is None:
            raise CodeError("super() expression should not occur outside of class", super_loc)
        self._precondition(
            super_expr.info is self.contract_method_info.type_info,
            "expected super type info to be current class",
            super_loc,
        )
        if super_expr.call.args:
            raise CodeError(
                "only the zero-arguments version of super() is supported",
                self._location(super_expr.call),
            )
        for base in iterate_user_bases(self.contract_method_info.type_info):
            if (base_method := base.get_method(super_expr.name)) is not None:
                cref = qualified_class_name(base)
                if not isinstance(base_method.type, mypy.types.CallableType):
                    # this shouldn't be hit unless there's typing.overload of weird
                    # decorators going on, both of which we don't allow
                    raise CodeError(
                        f"Unable to retrieve type of {cref.full_name}.{super_expr.name}",
                        super_loc,
                    )
                return SubroutineInvokerExpressionBuilder(
                    context=self.context,
                    target=BaseClassSubroutineTarget(base_class=cref, name=super_expr.name),
                    location=super_loc,
                    func_type=base_method.type,
                )

        if super_expr.name in self.contract_method_info.app_state:
            raise CodeError(
                "super() is only supported for method calls, not member access", super_loc
            )
        raise CodeError(
            f"Unable to locate method {super_expr.name}"
            f" in bases of {self.contract_method_info.cref.full_name}",
            super_loc,
        )

    # unsupported expressions

    def visit_list_comprehension(self, expr: mypy.nodes.ListComprehension) -> ExpressionBuilder:
        raise CodeError("List comprehensions are not supported", self._location(expr))

    def visit_slice_expr(self, expr: mypy.nodes.SliceExpr) -> ExpressionBuilder:
        raise CodeError("Slices are not supported outside of indexing", self._location(expr))

    def visit_lambda_expr(self, expr: mypy.nodes.LambdaExpr) -> ExpressionBuilder:
        raise CodeError("lambda functions are not supported", self._location(expr))

    def visit_ellipsis(self, expr: mypy.nodes.EllipsisExpr) -> ExpressionBuilder:
        raise CodeError("ellipsis expressions are not supported", self._location(expr))

    def visit_list_expr(self, expr: mypy.nodes.ListExpr) -> ExpressionBuilder:
        raise CodeError("Python lists are not supported", self._location(expr))


@typing.overload
def temporary_assignment_if_required(operand: Literal) -> Literal:
    ...


@typing.overload
def temporary_assignment_if_required(operand: Expression) -> TemporaryAssignmentExpressionBuilder:
    ...


@typing.overload
def temporary_assignment_if_required(
    operand: ExpressionBuilder,
) -> TemporaryAssignmentExpressionBuilder:
    ...


def temporary_assignment_if_required(
    operand: ExpressionBuilder | Expression | Literal,
) -> ExpressionBuilder | Literal:
    if isinstance(operand, Literal):
        return operand

    if isinstance(operand, Expression):
        expr = operand
    else:
        expr = operand.build_assignment_source()
    # TODO: optimise the below checks so we don't create unnecessary temporaries,
    #       ie when Expression has no side effects
    if not isinstance(expr, VarExpression | CompileTimeConstantExpression):
        return TemporaryAssignmentExpressionBuilder(expr)
    if isinstance(operand, Expression):
        return var_expression(operand)
    else:
        return operand


def _maybe_index(
    eb: ExpressionBuilder, indexes: Sequence[ExpressionBuilder | Literal], location: SourceLocation
) -> ExpressionBuilder | Literal:
    if indexes:
        if len(indexes) == 1:
            return eb.index(indexes[0], location)
        else:
            return eb.index_multiple(indexes, location)
    return eb
