import contextlib
import typing
from collections.abc import Iterator, Sequence
from functools import partialmethod

import attrs
import mypy.nodes
import mypy.patterns
import mypy.types

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    AppStateExpression,
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
    Lvalue,
    Not,
    ReturnStatement,
    SingleEvaluation,
    Statement,
    Subroutine,
    SubroutineArgument,
    Switch,
    TupleExpression,
    UInt64Constant,
    VarExpression,
    WhileLoop,
)
from puya.awst_build import constants, pytypes
from puya.awst_build.base_mypy_visitor import BaseMyPyVisitor
from puya.awst_build.context import ASTConversionModuleContext
from puya.awst_build.eb._literals import LiteralBuilderImpl
from puya.awst_build.eb.arc4 import (
    ARC4BoolClassExpressionBuilder,
    ARC4ClientClassExpressionBuilder,
)
from puya.awst_build.eb.bool import BoolClassExpressionBuilder
from puya.awst_build.eb.contracts import (
    ContractSelfExpressionBuilder,
    ContractTypeExpressionBuilder,
)
from puya.awst_build.eb.factories import (
    builder_for_instance,
    builder_for_type,
    try_get_builder_for_func,
)
from puya.awst_build.eb.interface import (
    BuilderBinaryOp,
    BuilderComparisonOp,
    BuilderUnaryOp,
    CallableBuilder,
    InstanceBuilder,
    LiteralBuilder,
    NodeBuilder,
    StorageProxyConstructorResult,
)
from puya.awst_build.eb.subroutine import SubroutineInvokerExpressionBuilder
from puya.awst_build.eb.uint64 import UInt64ExpressionBuilder
from puya.awst_build.exceptions import TypeUnionError
from puya.awst_build.utils import (
    bool_eval,
    expect_operand_type,
    extract_bytes_literal_from_mypy,
    fold_binary_expr,
    fold_unary_expr,
    get_unaliased_fullname,
    iterate_user_bases,
    qualified_class_name,
    require_expression_builder,
    require_instance_builder,
    require_instance_builder_or_literal,
    resolve_method_from_type_info,
)
from puya.errors import CodeError, InternalError
from puya.models import ARC4MethodConfig
from puya.parse import SourceLocation
from puya.utils import invert_ordered_binary_op, lazy_setdefault

logger = log.get_logger(__name__)


@attrs.frozen
class ContractMethodInfo:
    type_info: mypy.nodes.TypeInfo
    cref: ContractReference
    arc4_method_config: ARC4MethodConfig | None


class FunctionASTConverter(BaseMyPyVisitor[Statement | Sequence[Statement] | None, NodeBuilder]):
    def __init__(
        self,
        context: ASTConversionModuleContext,
        func_def: mypy.nodes.FuncDef,
        contract_method_info: ContractMethodInfo | None,
        source_location: SourceLocation,
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
        self._return_type = self.context.type_to_pytype(
            type_info.ret_type, source_location=func_loc
        )
        # check & convert the arguments
        mypy_args = func_def.arguments
        mypy_arg_types = type_info.arg_types
        if func_def.info is not mypy.nodes.FUNC_NO_INFO:  # why god why
            # function is a method
            if not mypy_args:
                context.error("Method declaration is missing 'self' argument", func_loc)
            else:
                self._precondition(
                    mypy_args[0].variable.is_self,
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
        self._symtable = dict[str, pytypes.PyType]()
        args = list[SubroutineArgument]()
        for arg, arg_type in zip(mypy_args, mypy_arg_types, strict=True):
            arg_loc = self._location(arg)
            if arg.kind.is_star():
                raise CodeError("variadic functions are not supported", arg_loc)
            if arg.initializer is not None:
                self._error(
                    "default function argument values are not supported yet", arg.initializer
                )
            pytyp = self.context.type_to_pytype(arg_type, source_location=arg_loc)
            arg_name = arg.variable.name
            args.append(SubroutineArgument(arg_loc, arg_name, pytyp.wtype))
            self._symtable[arg_name] = pytyp
        # translate body
        translated_body = self.visit_block(func_def.body)
        # build result
        self.result: Subroutine | ContractMethod
        if self.contract_method_info is None:
            self.result = Subroutine(
                module_name=self.context.module_name,
                name=func_def.name,
                source_location=source_location,
                args=args,
                return_type=self._return_type.wtype,
                body=translated_body,
                docstring=func_def.docstring,
            )
        else:
            self.result = ContractMethod(
                module_name=self.contract_method_info.cref.module_name,
                class_name=self.contract_method_info.cref.class_name,
                name=func_def.name,
                source_location=source_location,
                args=args,
                return_type=self._return_type.wtype,
                body=translated_body,
                docstring=func_def.docstring,
                abimethod_config=self.contract_method_info.arc4_method_config,
            )

    @classmethod
    @typing.overload
    def convert(
        cls,
        context: ASTConversionModuleContext,
        func_def: mypy.nodes.FuncDef,
        source_location: SourceLocation,
    ) -> Subroutine: ...

    @classmethod
    @typing.overload
    def convert(
        cls,
        context: ASTConversionModuleContext,
        func_def: mypy.nodes.FuncDef,
        source_location: SourceLocation,
        contract_method_info: ContractMethodInfo,
    ) -> ContractMethod: ...

    @classmethod
    def convert(
        cls,
        context: ASTConversionModuleContext,
        func_def: mypy.nodes.FuncDef,
        source_location: SourceLocation,
        contract_method_info: ContractMethodInfo | None = None,
    ) -> Subroutine | ContractMethod:
        return cls(
            context=context,
            func_def=func_def,
            contract_method_info=contract_method_info,
            source_location=source_location,
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

    def visit_expression_stmt(self, stmt: mypy.nodes.ExpressionStmt) -> ExpressionStatement | None:
        stmt_loc = self._location(stmt)
        if isinstance(stmt.expr, mypy.nodes.StrExpr):
            if stmt.expr.value != self.func_def.docstring:
                logger.warning(
                    "String literal is not assigned and is not part of docstring",
                    location=stmt_loc,
                )
            return None
        if isinstance(stmt.expr, mypy.nodes.TupleExpr) and len(stmt.expr.items) == 1:
            raise CodeError(
                "Tuple being constructed without assignment,"
                " check for a stray comma at the end of the statement",
                stmt_loc,
            )
        expr = require_instance_builder(stmt.expr.accept(self)).rvalue()
        if expr.wtype is not wtypes.void_wtype:
            if (
                # special case to ignore ignoring the result of typing.reveal_type
                not (
                    isinstance(stmt.expr, mypy.nodes.CallExpr)
                    and isinstance(stmt.expr.analyzed, mypy.nodes.RevealExpr)
                )
                # special case to ignore inner transaction result types
                # could maybe expand this check to consider whether an expression has known
                # side-effects
                and not wtypes.is_inner_transaction_type(expr.wtype)
                and not wtypes.is_inner_transaction_tuple_type(expr.wtype)
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
                match stmt.lvalues:
                    case [mypy.nodes.NameExpr(name=var_name)]:
                        if stmt.type is not None:  # should always be the case, but ...
                            self._symtable[var_name] = self.context.type_to_pytype(
                                stmt.type, source_location=stmt_loc
                            )
                        # forward type-declaration only, no-op
                        return []
                    case _:
                        raise InternalError(
                            "Forward type declarations should only have one target,"
                            " and it should be a NameExpr",
                            stmt_loc,
                        )
        rvalue = require_instance_builder(stmt.rvalue.accept(self))
        if isinstance(rvalue, StorageProxyConstructorResult):
            try:
                (lvalue,) = stmt.lvalues
            except ValueError:
                # this is true regardless of whether it's a self assignment or not,
                # these are objects so aliasing is an issue in terms of semantic compatibility
                raise CodeError(
                    f"{rvalue.pytype} can only be assigned to a single variable", stmt_loc
                ) from None
            if is_self_member(lvalue):
                return self._handle_proxy_assignment(lvalue, rvalue, stmt_loc)
            elif rvalue.initial_value is not None:
                raise CodeError(
                    "providing an initial value is only allowed"
                    " when assigning to a member variable",
                    stmt_loc,
                )
        elif len(stmt.lvalues) > 1:
            rvalue = temporary_assignment_if_required(rvalue)

        return [
            AssignmentStatement(
                value=rvalue.rvalue(),
                target=self.resolve_lvalue(lvalue),
                source_location=stmt_loc,
            )
            for lvalue in reversed(stmt.lvalues)
        ]

    def _handle_proxy_assignment(
        self,
        lvalue: mypy.nodes.MemberExpr,
        rvalue: StorageProxyConstructorResult,
        stmt_loc: SourceLocation,
    ) -> Sequence[Statement]:
        if self.contract_method_info is None:
            raise InternalError("Assignment to self outside of a contract class", stmt_loc)
        if self.func_def.name != "__init__":
            raise CodeError(
                f"{rvalue.pytype.generic or rvalue.pytype}"
                " can only be assigned to a member variable in the __init__ method",
                stmt_loc,
            )
        cref = self.contract_method_info.cref
        member_name = lvalue.name
        member_loc = self._location(lvalue)
        defn = rvalue.build_definition(member_name, cref, rvalue.pytype, member_loc)
        self.context.add_state_def(cref, defn)
        if rvalue.initial_value is None:
            return []
        elif rvalue.pytype.generic != pytypes.GenericGlobalStateType:
            raise InternalError(
                f"Don't know how to do initialise-on-declaration for {rvalue.pytype}", stmt_loc
            )
        else:
            global_state_target = AppStateExpression(
                key=defn.key,
                member_name=defn.member_name,
                wtype=defn.definition.storage_wtype,
                source_location=defn.source_location,
            )
            return [
                AssignmentStatement(
                    target=global_state_target,
                    value=rvalue.initial_value,
                    source_location=stmt_loc,
                )
            ]

    def resolve_lvalue(self, lvalue: mypy.nodes.Expression) -> Lvalue:
        builder_or_literal = lvalue.accept(self)
        builder = require_instance_builder(builder_or_literal)
        return builder.lvalue()

    def empty_statement(self, _tmt: mypy.nodes.Statement) -> None:
        return None

    def visit_operator_assignment_stmt(self, stmt: mypy.nodes.OperatorAssignmentStmt) -> Statement:
        stmt_loc = self._location(stmt)
        builder = require_instance_builder(stmt.lvalue.accept(self))
        rhs = require_instance_builder_or_literal(stmt.rvalue.accept(self))
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
        sequence_builder = require_instance_builder(stmt.expr.accept(self))
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
        comment: str | None = None
        if stmt.msg is not None:
            msg = stmt.msg.accept(self)
            match msg:
                case LiteralBuilder(value=str(comment)):
                    pass
                case _:
                    self._error("only literal strings are supported as assertion messages", stmt)
        condition = self._eval_condition(stmt.expr)
        return AssertStatement(
            source_location=self._location(stmt),
            condition=condition,
            comment=comment,
        )

    def visit_del_stmt(self, stmt: mypy.nodes.DelStmt) -> Statement:
        stmt_expr = stmt.expr.accept(self)
        del_item = require_instance_builder(stmt_expr)
        return del_item.delete(self._location(stmt))

    def visit_return_stmt(self, stmt: mypy.nodes.ReturnStmt) -> ReturnStatement | None:
        loc = self._location(stmt)
        return_expr = stmt.expr
        if return_expr is None:
            if self._return_type is not pytypes.NoneType:
                self._error(
                    "function is typed as returning a value, so a value must be returned", loc
                )
            return ReturnStatement(source_location=loc, value=None)

        returning_builder = require_instance_builder(return_expr.accept(self))
        if returning_builder.pytype != self._return_type:
            self._error(
                f"invalid return type of {returning_builder.pytype}, expected {self._return_type}",
                loc,
            )
        return ReturnStatement(source_location=loc, value=returning_builder.rvalue())

    def visit_match_stmt(self, stmt: mypy.nodes.MatchStmt) -> Switch | None:
        loc = self._location(stmt)
        subject_eb = require_instance_builder(stmt.subject.accept(self))
        subject_typ = subject_eb.pytype
        subject = temporary_assignment_if_required(subject_eb).rvalue()
        case_block_map = dict[Expression, Block]()
        default_block: Block | None = None
        for pattern, guard, block in zip(stmt.patterns, stmt.guards, stmt.bodies, strict=True):
            match pattern, guard:
                case mypy.patterns.ValuePattern(expr=case_expr), None:
                    case_value_builder_or_literal = case_expr.accept(self)
                    case_value = require_instance_builder(case_value_builder_or_literal).rvalue()
                    case_block = self.visit_block(block)
                    case_block_map[case_value] = case_block
                case mypy.patterns.SingletonPattern(value=bool() as bool_literal), None:
                    case_value = BoolConstant(
                        value=bool_literal, source_location=self._location(pattern)
                    )
                    case_block = self.visit_block(block)
                    case_block_map[case_value] = case_block
                case (
                    mypy.patterns.ClassPattern(
                        positionals=[mypy.patterns.ValuePattern(expr=inner_literal_expr)],
                        class_ref=mypy.nodes.RefExpr(fullname=fullname),
                    ),
                    None,
                ) if fullname in (
                    constants.CLS_UINT64,
                    constants.CLS_BIGUINT,
                    constants.CLS_BYTES,
                    constants.CLS_STRING,
                    constants.CLS_ACCOUNT,
                ):
                    case_value_builder_or_literal = require_instance_builder_or_literal(
                        inner_literal_expr.accept(self)
                    )
                    case_value = expect_operand_type(
                        case_value_builder_or_literal, subject_typ
                    ).rvalue()
                    case_block = self.visit_block(block)
                    case_block_map[case_value] = case_block
                case mypy.patterns.AsPattern(name=None, pattern=None), None:
                    default_block = self.visit_block(block)
                case _:
                    supported_types = ", ".join(
                        (
                            constants.CLS_UINT64_ALIAS,
                            constants.CLS_BIGUINT_ALIAS,
                            constants.CLS_BYTES_ALIAS,
                            constants.CLS_STRING_ALIAS,
                            constants.CLS_ACCOUNT_ALIAS,
                        )
                    )
                    self._error(
                        f"match statements only support class patterns for {supported_types}"
                        ", value patterns or bool literals",
                        pattern,
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

    def visit_class_def(self, cdef: mypy.nodes.ClassDef) -> None:
        self._error("classes nested inside functions are not supported", cdef)

    # Expressions
    def _visit_ref_expr(self, expr: mypy.nodes.MemberExpr | mypy.nodes.NameExpr) -> NodeBuilder:
        expr_loc = self._location(expr)
        # Do a straight forward lookup at the RefExpr level handle the cases of:
        #  - type aliases
        #  - simple (non-generic) types
        #  - generic type that has not been parameterised
        #    (e.g. when calling a constructor which can infer the type from its arguments)
        # For parameterised generics, these are resolved at the IndexExpr level, without
        # descending into IndexExpr.base.
        # By doing a simple lookup instead of resolving the PyType of expr,
        # we can side step complex construsts in the stubs that we don't support in user code,
        # such as overloads.
        if py_typ := self.context.lookup_pytype(expr.fullname):  # noqa: SIM102
            # side step these ones for now
            if (
                pytypes.ContractBaseType not in py_typ.mro
                and pytypes.ARC4ClientBaseType not in py_typ.bases
            ):
                return builder_for_type(py_typ, expr_loc)

        if expr.name == "__all__":
            # special case here, we allow __all__ at the module level for it's "public vs private"
            # control implications w.r.t linting etc, but we do so by ignoring it.
            # so this is here just in case someone tries to reference __all__ inside a function,
            # to give a more useful error message.
            raise CodeError("__all__ cannot be referenced inside functions", expr_loc)

        fullname = get_unaliased_fullname(expr)
        if fullname.startswith("builtins."):
            return self._visit_ref_expr_of_builtins(fullname, expr_loc)
        if func_builder := try_get_builder_for_func(fullname, expr_loc):
            return func_builder
        match expr:
            case mypy.nodes.RefExpr(node=mypy.nodes.TypeInfo() as typ) if py_typ:
                if pytypes.ContractBaseType in py_typ.mro:
                    return ContractTypeExpressionBuilder(
                        self.context, py_typ, typ.defn.info, expr_loc
                    )
                if pytypes.ARC4ClientBaseType in py_typ.bases:  # provides type info only
                    return ARC4ClientClassExpressionBuilder(
                        self.context, py_typ, expr_loc, typ.defn.info
                    )
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
                    type_info=self.contract_method_info.type_info,
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
                    raise CodeError(
                        "Unable to resolve global constant reference", expr_loc
                    ) from ex
                else:
                    return LiteralBuilderImpl(source_location=expr_loc, value=constant_value)
            case mypy.nodes.NameExpr(
                kind=mypy.nodes.LDEF, node=mypy.nodes.Var(), name=var_name
            ) as name_expr:
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
                    name=var_name, wtype=local_type.wtype, source_location=expr_loc
                )
                return builder_for_instance(local_type, var_expr)
        scope = {
            mypy.nodes.LDEF: "local",
            mypy.nodes.MDEF: "member",
            mypy.nodes.GDEF: "global",
            None: "unknown",
        }.get(expr.kind)
        # this can happen in otherwise well-formed code that is just missing a reference
        raise CodeError(
            f"Unable to resolve reference to {expr.fullname or expr.name!r}, {scope=}",
            expr_loc,
        )

    @staticmethod
    def _visit_ref_expr_of_builtins(fullname: str, location: SourceLocation) -> NodeBuilder:
        assert fullname.startswith("builtins.")
        rest_of_name = fullname.removeprefix("builtins.")
        match rest_of_name:
            case "True":
                return LiteralBuilderImpl(source_location=location, value=True)
            case "False":
                return LiteralBuilderImpl(source_location=location, value=False)
            case "None":
                raise CodeError("None is not supported as a value, only a return type", location)
            case "len":
                raise CodeError(
                    "len() is not supported -"
                    " types with a length will have a .length property instead",
                    location,
                )
            case "range":
                raise CodeError("range() is not supported - use algopy.urange() instead", location)
            case "enumerate":
                raise CodeError(
                    "enumerate() is not supported - use algopy.uenumerate() instead", location
                )
            case _:
                raise CodeError(f"Unsupported builtin: {rest_of_name}", location)

    def visit_name_expr(self, expr: mypy.nodes.NameExpr) -> NodeBuilder:
        return self._visit_ref_expr(expr)

    def visit_member_expr(self, expr: mypy.nodes.MemberExpr) -> NodeBuilder:
        expr_loc = self._location(expr)
        if isinstance(expr.expr, mypy.nodes.RefExpr):
            if isinstance(expr.expr.node, mypy.nodes.MypyFile):
                # special case for module attribute access
                return self._visit_ref_expr(expr)
            unaliased_base_fullname = get_unaliased_fullname(expr.expr)
            # TODO: allow UInt64Constant values in context.constants, and then put these there
            if enum_cls_data := constants.NAMED_INT_CONST_ENUM_DATA.get(unaliased_base_fullname):
                try:
                    int_enum = enum_cls_data[expr.name]
                except KeyError as ex:
                    raise CodeError(
                        "Unable to resolve constant value for"
                        f" {unaliased_base_fullname}.{expr.name}",
                        expr_loc,
                    ) from ex
                return UInt64ExpressionBuilder(
                    UInt64Constant(
                        value=int_enum.value, source_location=expr_loc, teal_alias=int_enum.name
                    )
                )

        base = expr.expr.accept(self)
        base_builder = require_expression_builder(base)
        return base_builder.member_access(name=expr.name, location=expr_loc)

    def visit_call_expr(self, call: mypy.nodes.CallExpr) -> NodeBuilder:
        if call.analyzed is not None:
            return self._visit_special_call_expr(call, analyzed=call.analyzed)

        callee = call.callee.accept(self)
        if not isinstance(callee, CallableBuilder):
            raise CodeError("not a callable expression", self._location(call.callee))

        if isinstance(callee, BoolClassExpressionBuilder | ARC4BoolClassExpressionBuilder):
            args_context: typing.Any = self._enter_bool_context
        else:
            args_context = contextlib.nullcontext
        with args_context():
            args = [arg.accept(self) for arg in call.args]
            arg_types = [self.context.mypy_expr_node_type(arg) for arg in call.args]
        return callee.call(
            args=args,
            arg_typs=arg_types,
            arg_kinds=call.arg_kinds,
            arg_names=call.arg_names,
            location=self._location(call),
        )

    def _visit_special_call_expr(
        self, call: mypy.nodes.CallExpr, *, analyzed: mypy.nodes.Expression
    ) -> NodeBuilder:
        match analyzed:
            case mypy.nodes.CastExpr(expr=inner_expr):
                self.context.warning(
                    "use of typing.cast, output may be invalid or insecure TEAL", call
                )
            case mypy.nodes.AssertTypeExpr(expr=inner_expr):
                # just FYI... in case the user thinks this has a runtime effect
                # (it doesn't, not even in Python)
                self.context.warning(
                    "use of typing.assert_type has no effect on compilation", call
                )
            case mypy.nodes.RevealExpr(expr=mypy.nodes.Expression() as inner_expr):
                pass
            case _:
                raise CodeError(
                    f"Unsupported special function call"
                    f" of analyzed type {type(analyzed).__name__}",
                    self._location(call),
                )

        return inner_expr.accept(self)

    def visit_unary_expr(self, node: mypy.nodes.UnaryExpr) -> NodeBuilder:
        expr_loc = self._location(node)
        builder_or_literal = node.expr.accept(self)
        if isinstance(builder_or_literal, LiteralBuilder):
            folded_result = fold_unary_expr(expr_loc, node.op, builder_or_literal.value)
            return LiteralBuilderImpl(value=folded_result, source_location=expr_loc)
        match node.op:
            case "not":
                return builder_or_literal.bool_eval(expr_loc, negate=True)
            case op_str if op_str in BuilderUnaryOp:
                builder_op = BuilderUnaryOp(op_str)
                return require_instance_builder(builder_or_literal).unary_op(builder_op, expr_loc)
            case _:
                # guard against future python unary operators
                raise InternalError(f"Unable to interpret unary operator '{node.op}'", expr_loc)

    def visit_op_expr(self, node: mypy.nodes.OpExpr) -> NodeBuilder:
        node_loc = self._location(node)
        lhs = require_instance_builder_or_literal(node.left.accept(self))
        rhs = require_instance_builder_or_literal(node.right.accept(self))

        # constant fold if both literals
        if isinstance(lhs, LiteralBuilder) and isinstance(rhs, LiteralBuilder):
            folded_result = fold_binary_expr(
                location=node_loc, op=node.op, lhs=lhs.value, rhs=rhs.value
            )
            return LiteralBuilderImpl(value=folded_result, source_location=node_loc)

        # mypy combines ast.BoolOp and ast.BinOp, but they're kinda different...
        if node.op in ("and", "or"):
            bool_op = BinaryBooleanOperator(node.op)
            try:
                result_pytype = self.context.mypy_expr_node_type(node)
            except TypeUnionError as union_ex:
                result_pytypes = union_ex.types
            else:
                result_pytypes = [result_pytype]
            return self._visit_bool_op_expr(
                bool_op, result_pytypes, lhs=lhs, rhs=rhs, location=node_loc
            )

        try:
            op = BuilderBinaryOp(node.op)
        except ValueError as ex:
            raise InternalError(f"Unknown binary operator: {node.op}") from ex

        result: NodeBuilder = NotImplemented
        if isinstance(lhs, NodeBuilder):
            result = lhs.binary_op(other=rhs, op=op, location=node_loc, reverse=False)
        if result is NotImplemented and isinstance(rhs, NodeBuilder):
            result = rhs.binary_op(other=lhs, op=op, location=node_loc, reverse=True)
        if result is NotImplemented:
            raise CodeError(f"Unsupported operation {op.value} between types", node_loc)
        return result

    def _visit_bool_op_expr(
        self,
        op: BinaryBooleanOperator,
        result_pytypes: Sequence[pytypes.PyType],
        lhs: InstanceBuilder,
        rhs: InstanceBuilder,
        location: SourceLocation,
    ) -> InstanceBuilder:
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
        if len(result_pytypes) > 1:
            if not self._is_bool_context:
                raise CodeError(
                    "expression would produce a union type,"
                    " which isn't supported unless evaluating a boolean condition",
                    location,
                )
            target_pytyp = pytypes.BoolType
            lhs = bool_eval(lhs, location)
            rhs = bool_eval(rhs, location)
        else:
            (target_pytyp,) = result_pytypes
            lhs = expect_operand_type(lhs, target_pytyp)
            rhs = expect_operand_type(rhs, target_pytyp)

        if target_pytyp == pytypes.BoolType:
            expr_result: Expression = BooleanBinaryOperation(
                source_location=location, left=lhs.rvalue(), op=op, right=rhs.rvalue()
            )
        else:
            lhs = temporary_assignment_if_required(lhs)
            # (lhs:uint64 and rhs:uint64) => lhs_tmp_var if not bool(lhs_tmp_var := lhs) else rhs
            # (lhs:uint64 or rhs:uint64) => lhs_tmp_var if bool(lhs_tmp_var := lhs) else rhs
            # TODO: this is a bit convoluted in terms of NodeBuilder <-> Expression
            condition = lhs.bool_eval(location, negate=op is BinaryBooleanOperator.and_).rvalue()
            expr_result = ConditionalExpression(
                source_location=location,
                condition=condition,
                true_expr=lhs.rvalue(),
                false_expr=rhs.rvalue(),
                wtype=target_pytyp.wtype,
            )
        return builder_for_instance(target_pytyp, expr_result)

    def visit_index_expr(self, expr: mypy.nodes.IndexExpr) -> NodeBuilder:
        expr_location = self._location(expr)
        if isinstance(expr.method_type, mypy.types.CallableType):
            result_pytyp = self.context.type_to_pytype(
                expr.method_type.ret_type, source_location=expr_location
            )
            if isinstance(result_pytyp, pytypes.PseudoGenericFunctionType):
                return builder_for_type(result_pytyp, expr_location)
        match expr.analyzed:
            case None:
                pass
            case mypy.nodes.TypeAliasExpr():
                raise CodeError("type aliases are not supported inside subroutines", expr_location)
            case mypy.nodes.TypeApplication():
                type_type = self.context.mypy_expr_node_type(expr)
                if not isinstance(type_type, pytypes.TypeType):
                    raise InternalError(
                        "expected resolved PyType of and IndexExpr where analyzed"
                        " is a TypeApplication to be a TypeType",
                        expr_location,
                    )
                return builder_for_type(type_type.typ, expr_location)
            case _:
                typing.assert_never(expr.analyzed)

        base_expr = require_instance_builder_or_literal(expr.base.accept(self))
        if isinstance(base_expr, LiteralBuilder):
            raise CodeError(  # TODO: yeet me
                "Python literals cannot be indexed or sliced", base_expr.source_location
            )

        match expr.index:
            # special case handling of SliceExpr, so we don't need to handle slice Literal's
            # or some such everywhere
            case mypy.nodes.SliceExpr(begin_index=begin, end_index=end, stride=stride):
                return base_expr.slice_index(
                    begin_index=(
                        require_instance_builder_or_literal(begin.accept(self)) if begin else None
                    ),
                    end_index=(
                        require_instance_builder_or_literal(end.accept(self)) if end else None
                    ),
                    stride=(
                        require_instance_builder_or_literal(stride.accept(self))
                        if stride
                        else None
                    ),
                    location=expr_location,
                )

        index_expr_or_literal = require_instance_builder_or_literal(expr.index.accept(self))
        return base_expr.index(index=index_expr_or_literal, location=expr_location)

    def visit_conditional_expr(self, expr: mypy.nodes.ConditionalExpr) -> NodeBuilder:
        expr_loc = self._location(expr)
        condition = self._eval_condition(expr.cond)
        # TODO: conditional literals as literal builders
        true_b = require_instance_builder(expr.if_expr.accept(self))
        false_b = require_instance_builder(expr.else_expr.accept(self))
        if true_b.pytype != false_b.pytype:
            self._error("Incompatible result types for 'true' and 'false' expressions", expr_loc)
        expr_pytype = true_b.pytype

        cond_expr = ConditionalExpression(
            condition=condition,
            true_expr=true_b.rvalue(),
            false_expr=false_b.rvalue(),
            wtype=expr_pytype.wtype,
            source_location=expr_loc,
        )
        return builder_for_instance(expr_pytype, cond_expr)

    def visit_comparison_expr(self, expr: mypy.nodes.ComparisonExpr) -> NodeBuilder:
        from puya.awst_build.eb.bool import BoolExpressionBuilder

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

        operands = [require_instance_builder_or_literal(o.accept(self)) for o in expr.operands]
        operands[1:-1] = [
            temporary_assignment_if_required(operand) for operand in list(operands)[1:-1]
        ]

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
        # TODO: PyType known as bool (at least with our current stubs)
        return BoolExpressionBuilder(result)

    def _build_compare(
        self,
        operator: str,
        lhs: InstanceBuilder,
        rhs: InstanceBuilder,
    ) -> Expression:
        cmp_loc = lhs.source_location + rhs.source_location
        if isinstance(lhs, LiteralBuilder) and isinstance(rhs, LiteralBuilder):
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

        result: InstanceBuilder = NotImplemented
        if isinstance(lhs, NodeBuilder):
            op = BuilderComparisonOp(operator)
            result = lhs.compare(other=rhs, op=op, location=cmp_loc)
        if result is NotImplemented and isinstance(rhs, NodeBuilder):
            op = BuilderComparisonOp(invert_ordered_binary_op(operator))
            result = rhs.compare(other=lhs, op=op, location=cmp_loc)
        if result is NotImplemented:
            raise CodeError(f"Unsupported comparison {operator!r} between types", cmp_loc)
        return result.rvalue()

    def visit_int_expr(self, expr: mypy.nodes.IntExpr) -> LiteralBuilder:
        return LiteralBuilderImpl(value=expr.value, source_location=self._location(expr))

    def visit_str_expr(self, expr: mypy.nodes.StrExpr) -> LiteralBuilder:
        return LiteralBuilderImpl(value=expr.value, source_location=self._location(expr))

    def visit_bytes_expr(self, expr: mypy.nodes.BytesExpr) -> LiteralBuilder:
        bytes_const = extract_bytes_literal_from_mypy(expr)
        return LiteralBuilderImpl(value=bytes_const, source_location=self._location(expr))

    def visit_tuple_expr(self, mypy_expr: mypy.nodes.TupleExpr) -> NodeBuilder:
        from puya.awst_build.eb.tuple import TupleExpressionBuilder

        items = [
            require_instance_builder(
                mypy_item.accept(self),
                literal_msg="Python literals (other than True/False)"
                " are not valid as tuple elements",
            ).rvalue()
            for mypy_item in mypy_expr.items
        ]
        # TODO: grab item types from EB items?
        typ = self.context.mypy_expr_node_type(mypy_expr)
        location = self._location(mypy_expr)
        if not items:
            raise CodeError("Empty tuples are not supported", location)
        wtype = typ.wtype
        assert isinstance(wtype, wtypes.WTuple)
        tuple_expr = TupleExpression(
            source_location=location,
            wtype=wtype,
            items=items,
        )

        return TupleExpressionBuilder(tuple_expr, typ)

    def visit_assignment_expr(self, expr: mypy.nodes.AssignmentExpr) -> NodeBuilder:
        expr_loc = self._location(expr)
        self._precondition(
            not isinstance(expr, mypy.nodes.TupleExpr | mypy.nodes.ListExpr),
            "Python doesn't support tuple unpacking in assignment expressions",
            expr_loc,
        )
        # TODO: test if self. assignment?
        with self._leave_bool_context():
            source = require_instance_builder(expr.value.accept(self))
        value = source.rvalue()
        target = self.resolve_lvalue(expr.target)
        result = AssignmentExpression(source_location=expr_loc, value=value, target=target)
        # TODO: take PyType from source NodeBuilder
        result_typ = self.context.mypy_expr_node_type(expr)
        return builder_for_instance(result_typ, result)

    def visit_super_expr(self, super_expr: mypy.nodes.SuperExpr) -> NodeBuilder:
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
            base_method = resolve_method_from_type_info(base, super_expr.name, super_loc)
            if base_method is None:
                continue
            if not isinstance(base_method.type, mypy.types.CallableType):
                # this shouldn't be hit unless there's typing.overload or weird
                # decorators going on, both of which we don't allow
                raise CodeError(f"Unable to retrieve type of {base_method.fullname!r}", super_loc)
            super_target = BaseClassSubroutineTarget(
                base_class=qualified_class_name(base), name=super_expr.name
            )
            return SubroutineInvokerExpressionBuilder(
                context=self.context,
                target=super_target,
                func_type=base_method.type,
                location=super_loc,
            )
        raise CodeError(
            f"Unable to locate method {super_expr.name}"
            f" in bases of {self.contract_method_info.cref.full_name}",
            super_loc,
        )

    # unsupported expressions

    def visit_list_comprehension(self, expr: mypy.nodes.ListComprehension) -> NodeBuilder:
        raise CodeError("List comprehensions are not supported", self._location(expr))

    def visit_slice_expr(self, expr: mypy.nodes.SliceExpr) -> NodeBuilder:
        raise CodeError("Slices are not supported outside of indexing", self._location(expr))

    def visit_lambda_expr(self, expr: mypy.nodes.LambdaExpr) -> NodeBuilder:
        raise CodeError("lambda functions are not supported", self._location(expr))

    def visit_ellipsis(self, expr: mypy.nodes.EllipsisExpr) -> NodeBuilder:
        raise CodeError("ellipsis expressions are not supported", self._location(expr))

    def visit_list_expr(self, expr: mypy.nodes.ListExpr) -> NodeBuilder:
        raise CodeError("Python lists are not supported", self._location(expr))


def is_self_member(
    expr: mypy.nodes.Expression,
) -> typing.TypeGuard[mypy.nodes.MemberExpr]:
    match expr:
        case mypy.nodes.MemberExpr(expr=mypy.nodes.NameExpr(node=mypy.nodes.Var(is_self=True))):
            return True
    return False


def temporary_assignment_if_required(operand: InstanceBuilder) -> InstanceBuilder:
    if isinstance(operand, LiteralBuilder):
        return operand

    expr = operand.rvalue()
    # TODO: optimise the below checks so we don't create unnecessary temporaries,
    #       ie when Expression has no side effects
    if not isinstance(expr, VarExpression | CompileTimeConstantExpression):
        return builder_for_instance(operand.pytype, SingleEvaluation(expr))
    else:
        return operand
