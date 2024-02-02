import typing as t
from collections.abc import Callable

import attrs
import mypy.nodes
import mypy.types
import mypy.visitor

from puya import log
from puya.algo_constants import MAX_SCRATCH_SLOT_NUMBER
from puya.awst import wtypes
from puya.awst.nodes import (
    ConstantDeclaration,
    ConstantValue,
    LogicSignature,
    Module,
    ModuleStatement,
    StateTotals,
    StructureDefinition,
    StructureField,
)
from puya.awst_build import constants
from puya.awst_build.base_mypy_visitor import BaseMyPyVisitor
from puya.awst_build.context import ASTConversionContext, ASTConversionModuleContext
from puya.awst_build.contract import ContractASTConverter
from puya.awst_build.contract_data import ContractClassOptions
from puya.awst_build.exceptions import UnsupportedASTError
from puya.awst_build.subroutine import FunctionASTConverter
from puya.awst_build.utils import (
    extract_bytes_literal_from_mypy,
    fold_binary_expr,
    fold_unary_expr,
    get_arg_mapping,
    get_decorators_by_fullname,
    get_unaliased_fullname,
)
from puya.awst_build.validation.main import validate_awst
from puya.errors import CodeError, InternalError
from puya.utils import StableSet, coalesce

logger = log.get_logger(__name__)


DeferredModuleStatement: t.TypeAlias = Callable[[ASTConversionModuleContext], ModuleStatement]

StatementResult: t.TypeAlias = list[ModuleStatement | DeferredModuleStatement]


@attrs.frozen(kw_only=True)
class _LogicSigDecoratorInfo:
    name_override: str | None


class ModuleASTConverter(BaseMyPyVisitor[StatementResult, ConstantValue]):
    """This does basic validation, and traversal of valid module scope elements, collecting
    and folding constants."""

    def __init__(self, context: ASTConversionContext, module: mypy.nodes.MypyFile):
        super().__init__(context=context.for_module(module))

        self._mypy_module = module

        # pre-parse
        errors_start = log.get_num_errors()
        pre_parse_result = list[tuple[mypy.nodes.Context, StatementResult]]()
        for node in self._mypy_module.defs:
            with self.context.log_exceptions(fallback_location=node):
                items = node.accept(self)
                pre_parse_result.append((node, items))
        self._pre_parse_result = pre_parse_result
        self._error_count = log.get_num_errors() - errors_start

    @property
    def has_errors(self) -> bool:
        return self._error_count > 0

    def convert(self) -> Module:
        statements = []
        errors_start = log.get_num_errors()
        for node, items in self._pre_parse_result:
            with self.context.log_exceptions(fallback_location=node):
                for stmt_or_deferred in items:
                    if isinstance(stmt_or_deferred, ModuleStatement):
                        statements.append(stmt_or_deferred)
                    else:
                        statements.append(stmt_or_deferred(self.context))
        module = self._mypy_module
        result = Module(
            name=module.name,
            source_file_path=module.path,
            body=statements,
        )
        validate_awst(result)
        self._error_count += log.get_num_errors() - errors_start
        return result

    # Supported Statements

    def empty_statement(self, _stmt: mypy.nodes.Statement) -> StatementResult:
        return []

    def visit_function(
        self, func_def: mypy.nodes.FuncDef, decorator: mypy.nodes.Decorator | None
    ) -> StatementResult:
        self._precondition(
            func_def.abstract_status == mypy.nodes.NOT_ABSTRACT,
            "module level functions should not be classified as abstract by mypy",
            decorator or func_def,
        )
        dec_by_fullname = get_decorators_by_fullname(self.context, decorator) if decorator else {}
        source_location = self._location(decorator or func_def)
        logicsig_dec = dec_by_fullname.pop(constants.LOGICSIG_DECORATOR, None)
        if logicsig_dec:
            for dec_fullname, dec in dec_by_fullname.items():
                self._error(f'Unsupported logicsig decorator "{dec_fullname}"', dec)
            info = self._process_logic_sig_decorator(logicsig_dec)

            def deferred(ctx: ASTConversionModuleContext) -> ModuleStatement:
                program = FunctionASTConverter.convert(
                    ctx,
                    func_def,
                    source_location,
                )
                return LogicSignature(
                    module_name=ctx.module_name,
                    program=program,
                    name=coalesce(info.name_override, program.name),
                    source_location=self._location(logicsig_dec),
                )

            return [deferred]
        subroutine_dec = dec_by_fullname.pop(constants.SUBROUTINE_HINT, None)
        if subroutine_dec is None:
            self._error(
                f"free functions must be annotated with @{constants.SUBROUTINE_HINT_ALIAS}",
                func_def,
            )
        abimethod_dec = dec_by_fullname.pop(constants.ABIMETHOD_DECORATOR, None)
        if abimethod_dec is not None:
            self._error("free functions cannot be ARC4 ABI methods", abimethod_dec)
        # any further decorators are unsupported
        for dec_fullname, dec in dec_by_fullname.items():
            self._error(f'Unsupported function decorator "{dec_fullname}"', dec)

        return [lambda ctx: FunctionASTConverter.convert(ctx, func_def, source_location)]

    def _process_logic_sig_decorator(
        self, decorator: mypy.nodes.Expression
    ) -> _LogicSigDecoratorInfo:
        match decorator:
            case mypy.nodes.NameExpr() | mypy.nodes.CallExpr(args=[]):
                pass
            case mypy.nodes.CallExpr(arg_names=["name"], args=[name_arg]):
                name_const = name_arg.accept(self)
                if isinstance(name_const, str):
                    return _LogicSigDecoratorInfo(name_override=name_const)
                self.context.error(f"Expected a string, got {name_const!r}", name_arg)
            case _:
                self.context.error(
                    f"Invalid {constants.LOGICSIG_DECORATOR_ALIAS} usage", decorator
                )
        return _LogicSigDecoratorInfo(name_override=None)

    def visit_class_def(self, cdef: mypy.nodes.ClassDef) -> StatementResult:
        self.check_fatal_decorators(cdef.decorators)
        match cdef.analyzed:
            case None:
                pass
            case mypy.nodes.TypedDictExpr():
                self._unsupported(cdef, "TypedDict classes are not supported")
            case mypy.nodes.NamedTupleExpr():
                self._unsupported(cdef, "NamedTuple classes are not supported")
            case _ as unrecognised_analysis_expression:
                self.context.warning(
                    "Analyzed class expression of type"
                    f" {type(unrecognised_analysis_expression).__name__},"
                    " please report this issue and check the compilation results carefully",
                    cdef,
                )
        for decorator in cdef.decorators:
            self._error(
                (
                    "Unsupported decorator "
                    "(note: *all* class decorators are currently unsupported)"
                ),
                location=decorator,
            )
        if cdef.info.bad_mro:
            self._error("Bad MRO", location=cdef)
        elif cdef.info.has_base(constants.CLS_ARC4_STRUCT):
            if [ti.fullname for ti in cdef.info.direct_base_classes()] != [
                constants.CLS_ARC4_STRUCT
            ]:
                # TODO: allow inheritance of arc4.Struct?
                self._error(
                    "arc4.Struct classes must only inherit directly from arc4.Struct", cdef
                )
            else:
                return _process_arc4_struct(self.context, cdef)
        elif cdef.info.has_base(constants.STRUCT_BASE):
            if [ti.fullname for ti in cdef.info.direct_base_classes()] != [constants.STRUCT_BASE]:
                # TODO: allow inheritance of Structs?
                self._error("Struct classes must only inherit directly from Struct", cdef)
            else:
                return _process_struct(self.context, cdef)
        elif cdef.info.has_base(constants.CLS_ARC4_CLIENT):
            if [ti.fullname for ti in cdef.info.direct_base_classes()] != [
                constants.CLS_ARC4_CLIENT
            ]:
                self._error("ARC4Client classes must only inherit directly from ARC4Client", cdef)
            else:
                # nothing to do, ARC4Client classes are used for type info only
                pass
        elif cdef.info.has_base(constants.CONTRACT_BASE):
            # TODO: mypyc also checks for typing.TypingMeta and typing.GenericMeta equivalently
            #       in a similar check - I can't find many references to these, should we include
            #       them?
            if (
                cdef.info.metaclass_type
                and cdef.info.metaclass_type.type.fullname != "abc.ABCMeta"
            ):
                self._error(
                    f"Unsupported metaclass: {cdef.info.metaclass_type.type.fullname}",
                    location=cdef,
                )
            # TODO: other checks above?
            else:
                class_options = _process_contract_class_options(self.context, self, cdef)
                return [lambda ctx: ContractASTConverter.convert(ctx, cdef, class_options)]
        else:
            self._error(
                f"Unsupported class declaration."
                f" Contract classes must inherit either directly"
                f" or indirectly from {constants.CONTRACT_BASE_ALIAS}.",
                location=cdef,
            )
        return []

    def visit_operator_assignment_stmt(
        self, stmt: mypy.nodes.OperatorAssignmentStmt
    ) -> StatementResult:
        match stmt.lvalue:
            case mypy.nodes.NameExpr(name="__all__"):
                # TODO: this value is technically usable at runtime in Python,
                #       any references to it in the method bodies should fail
                return self.empty_statement(stmt)
            case _:
                self._unsupported(stmt)

    def visit_if_stmt(self, stmt: mypy.nodes.IfStmt) -> StatementResult:
        for expr, block in zip(stmt.expr, stmt.body, strict=True):
            if self._evaluate_compile_time_constant_condition(expr):
                return block.accept(self)
        # if we didn't return, we end up here, which means the user code
        # should evaluate to the else body (if present)
        if stmt.else_body:
            return stmt.else_body.accept(self)
        else:
            return []

    def visit_assignment_stmt(self, stmt: mypy.nodes.AssignmentStmt) -> StatementResult:
        self._precondition(
            bool(stmt.lvalues), "assignment statements should have at least one lvalue", stmt
        )
        self._precondition(
            not stmt.invalid_recursive_alias,
            "assignment statement with invalid_recursive_alias",
            stmt,
        )
        if stmt.is_alias_def:  # ie is this a typing.TypeAlias
            return []  # skip it
        match stmt.lvalues:
            case [mypy.nodes.NameExpr(name="__all__")]:
                # TODO: this value is technically usable at runtime in Python,
                #       any references to it in the method bodies should fail
                return []  # skip it
            # mypy comments here indicate if this is a special form,
            # it will be a single lvalue of type NameExpr
            # https://github.com/python/mypy/blob/d2022a0007c0eb176ccaf37a9aa54c958be7fb10/mypy/semanal.py#L3508
            case [mypy.nodes.NameExpr(is_special_form=True)]:
                match stmt.rvalue:
                    # is_special_form also includes functional form or Enum or TypedDict
                    # declarations, we don't support those yet so need to exclude them from
                    # being skipped over here, otherwise the reported error later on in compilation
                    # could get real weird
                    case mypy.nodes.CallExpr(
                        analyzed=(mypy.nodes.EnumCallExpr() | mypy.nodes.TypedDictExpr())
                    ):
                        self._unsupported(stmt.rvalue, "unsupported type")
                    case _:
                        return []  # skip it
        const_delcs = StatementResult()

        for lvalue in stmt.lvalues:
            match lvalue, stmt.rvalue:
                case mypy.nodes.NameExpr() as name_expr, rvalue:
                    fullname = ".".join((self.context.module_name, name_expr.name))
                    # fullname might be unset if this is in
                    # a conditional branch that's !TYPE_CHECKING
                    if name_expr.fullname:
                        self._precondition(
                            name_expr.fullname == fullname,
                            f"assignment to module const - expected fullname of {fullname},"
                            f" but mypy had {name_expr.fullname}",
                            lvalue,
                        )
                    constant_value = rvalue.accept(self)
                    self.context.constants[fullname] = constant_value
                    const_delcs.append(
                        ConstantDeclaration(
                            name=name_expr.name,
                            value=constant_value,
                            source_location=self._location(lvalue),
                        )
                    )
                case _:
                    self._unsupported(
                        lvalue,
                        "only straight-forward assignment targets supported at module level",
                    )
        return const_delcs

    def visit_block(self, block: mypy.nodes.Block) -> StatementResult:
        result = StatementResult()
        for stmt in block.body:
            items = stmt.accept(self)
            result.extend(items)
        return result

    # Expressions

    def visit_name_expr(self, expr: mypy.nodes.NameExpr) -> ConstantValue:
        match expr.name:
            case "True":
                return True
            case "False":
                return False
        # TODO: is the GDEF check always valid?
        if not isinstance(expr.node, mypy.nodes.Var) or expr.kind != mypy.nodes.GDEF:
            self._unsupported(
                expr,
                "references to anything other than module-level constants "
                "are not supported at module level",
            )
        value = self.context.constants.get(expr.fullname)
        if value is None:
            raise CodeError(
                f"not a known constant value: {expr.name}"
                f" (qualified source name: {expr.fullname})",
                self._location(expr),
            )
        return value

    def visit_unary_expr(self, expr: mypy.nodes.UnaryExpr) -> ConstantValue:
        value = expr.expr.accept(self)
        return fold_unary_expr(self._location(expr), expr.op, value)

    def visit_op_expr(self, expr: mypy.nodes.OpExpr) -> ConstantValue:
        left_value = expr.left.accept(self)
        right_value = expr.right.accept(self)
        return fold_binary_expr(self._location(expr), expr.op, left_value, right_value)

    def visit_comparison_expr(self, expr: mypy.nodes.ComparisonExpr) -> ConstantValue:
        match (expr.operators, expr.operands):
            case ([op], [expr_left, expr_right]):
                lhs = expr_left.accept(self)
                rhs = expr_right.accept(self)
                return fold_binary_expr(self._location(expr), op, lhs, rhs)
            case _:
                self._unsupported(
                    expr, details="chained comparisons not supported at module level"
                )

    def visit_int_expr(self, expr: mypy.nodes.IntExpr) -> ConstantValue:
        return expr.value

    def visit_str_expr(self, expr: mypy.nodes.StrExpr) -> ConstantValue:
        return expr.value

    def visit_bytes_expr(self, expr: mypy.nodes.BytesExpr) -> ConstantValue:
        return extract_bytes_literal_from_mypy(expr)

    def visit_member_expr(self, expr: mypy.nodes.MemberExpr) -> ConstantValue:
        if (
            isinstance(expr.node, mypy.nodes.Var)
            and expr.kind == mypy.nodes.GDEF
            and expr.fullname
            and isinstance(expr.expr, mypy.nodes.RefExpr)
            and isinstance(expr.expr.node, mypy.nodes.MypyFile)
        ):
            try:
                return self.context.constants[expr.fullname]
            except KeyError as ex:
                self._unsupported(
                    expr, details="could not resolve external module constant", ex=ex
                )
        else:
            self._unsupported(expr)

    def visit_call_expr(self, expr: mypy.nodes.CallExpr) -> ConstantValue:
        # unfortunately, mypy doesn't preserve f-string identification info,
        # they get translated into either a str.join or str.format call at the top level
        # References:
        # https://github.com/python/mypy/blob/cb813259c3b9dff6aaa8686793cf6a0634cf1f69/mypy/fastparse.py#L1528
        # https://github.com/python/mypy/blob/cb813259c3b9dff6aaa8686793cf6a0634cf1f69/mypy/fastparse.py#L1550
        match expr:
            case mypy.nodes.CallExpr(
                callee=mypy.nodes.MemberExpr(expr=mypy.nodes.StrExpr(value=joiner), name="join"),
                args=[mypy.nodes.ListExpr() as args_list],
            ):
                args = [arg.accept(self) for arg in args_list.items]
                assert all(isinstance(x, str) for x in args)
                result = joiner.join(map(str, args))
                return result
            case mypy.nodes.CallExpr(
                callee=mypy.nodes.MemberExpr(
                    expr=mypy.nodes.StrExpr(value=format_str), name="format"
                )
            ):
                args = [arg.accept(self) for arg in expr.args]
                return format_str.format(*args)
            case mypy.nodes.CallExpr(
                callee=mypy.nodes.MemberExpr(
                    expr=mypy.nodes.StrExpr(value=str_value), name="encode"
                ),
                args=[mypy.nodes.StrExpr(value=encoding)],
                arg_names=[("encoding" | None)],
            ):
                return str_value.encode(encoding=encoding)
            case mypy.nodes.CallExpr(
                callee=mypy.nodes.MemberExpr(
                    expr=mypy.nodes.StrExpr(value=str_value), name="encode"
                ),
                args=[],
            ):
                return str_value.encode()
        return self._unsupported(expr)

    def visit_conditional_expr(self, expr: mypy.nodes.ConditionalExpr) -> ConstantValue:
        if self._evaluate_compile_time_constant_condition(expr.cond):
            return expr.if_expr.accept(self)
        else:
            return expr.else_expr.accept(self)

    def _evaluate_compile_time_constant_condition(self, expr: mypy.nodes.Expression) -> bool:
        from mypy import reachability

        kind = reachability.infer_condition_value(expr, self.context.parse_result.manager.options)
        if kind == reachability.TRUTH_VALUE_UNKNOWN:
            try:
                result = expr.accept(self)
            except UnsupportedASTError as ex:
                self._unsupported(
                    expr,
                    details="only constant valued conditions supported at module level",
                    ex=ex,
                )
            kind = reachability.ALWAYS_TRUE if result else reachability.ALWAYS_FALSE
        if kind in (reachability.ALWAYS_TRUE, reachability.MYPY_FALSE):
            return True
        elif kind in (reachability.ALWAYS_FALSE, reachability.MYPY_TRUE):
            return False
        else:
            raise InternalError(
                f"Unexpected reachability value: {kind}", location=self._location(expr)
            )

    def _unsupported(
        self,
        node: mypy.nodes.Node,
        details: str = "not supported at module level",
        ex: Exception | None = None,
    ) -> t.Never:
        raise UnsupportedASTError(node, self._location(node), details=details) from ex

    # Unsupported Statements

    def visit_expression_stmt(self, stmt: mypy.nodes.ExpressionStmt) -> StatementResult:
        if isinstance(stmt.expr, mypy.nodes.StrExpr):
            # ignore any doc-strings at module level
            return []
        else:
            return self._unsupported(stmt)

    def visit_while_stmt(self, stmt: mypy.nodes.WhileStmt) -> StatementResult:
        return self._unsupported(stmt)

    def visit_for_stmt(self, stmt: mypy.nodes.ForStmt) -> StatementResult:
        return self._unsupported(stmt)

    def visit_break_stmt(self, stmt: mypy.nodes.BreakStmt) -> StatementResult:
        return self._unsupported(stmt)

    def visit_continue_stmt(self, stmt: mypy.nodes.ContinueStmt) -> StatementResult:
        return self._unsupported(stmt)

    def visit_assert_stmt(self, stmt: mypy.nodes.AssertStmt) -> StatementResult:
        return self._unsupported(stmt)

    def visit_del_stmt(self, stmt: mypy.nodes.DelStmt) -> StatementResult:
        return self._unsupported(stmt)

    def visit_match_stmt(self, stmt: mypy.nodes.MatchStmt) -> StatementResult:
        return self._unsupported(stmt)

    # the remaining statements (below) are invalid at the module lexical scope,
    # mypy should have caught these errors already
    def visit_return_stmt(self, stmt: mypy.nodes.ReturnStmt) -> StatementResult:
        raise InternalError("encountered return statement at module level", self._location(stmt))

    # Unsupported Expressions

    def visit_super_expr(self, expr: mypy.nodes.SuperExpr) -> ConstantValue:
        return self._unsupported(expr)

    def visit_index_expr(self, expr: mypy.nodes.IndexExpr) -> ConstantValue:
        return self._unsupported(expr)

    def visit_ellipsis(self, expr: mypy.nodes.EllipsisExpr) -> ConstantValue:
        return self._unsupported(expr)

    def visit_list_expr(self, expr: mypy.nodes.ListExpr) -> ConstantValue:
        return self._unsupported(expr)

    def visit_tuple_expr(self, expr: mypy.nodes.TupleExpr) -> ConstantValue:
        return self._unsupported(expr)

    def visit_list_comprehension(self, expr: mypy.nodes.ListComprehension) -> ConstantValue:
        return self._unsupported(expr)

    def visit_slice_expr(self, expr: mypy.nodes.SliceExpr) -> ConstantValue:
        return self._unsupported(expr)

    def visit_assignment_expr(self, o: mypy.nodes.AssignmentExpr) -> ConstantValue:
        return self._unsupported(o)

    def visit_lambda_expr(self, expr: mypy.nodes.LambdaExpr) -> ConstantValue:
        return self._unsupported(expr)


def _process_contract_class_options(
    context: ASTConversionModuleContext,
    expr_visitor: mypy.visitor.ExpressionVisitor[ConstantValue],
    cdef: mypy.nodes.ClassDef,
) -> ContractClassOptions:
    name_override: str | None = None
    scratch_slot_reservations = StableSet[int]()
    state_totals = None
    for kw_name, kw_expr in cdef.keywords.items():
        with context.log_exceptions(kw_expr):
            match kw_name:
                case "name":
                    name_value = kw_expr.accept(expr_visitor)
                    if isinstance(name_value, str):
                        name_override = name_value
                    else:
                        context.error("Invalid type for name=", kw_expr)
                case "scratch_slots":
                    if isinstance(kw_expr, mypy.nodes.TupleExpr | mypy.nodes.ListExpr):
                        slot_items = kw_expr.items
                    else:
                        slot_items = [kw_expr]
                    for item_expr in slot_items:
                        slots = _map_scratch_space_reservation(context, expr_visitor, item_expr)
                        if not slots:
                            context.error("Slot range is empty", item_expr)
                        elif (min(slots) < 0) or (max(slots) > MAX_SCRATCH_SLOT_NUMBER):
                            context.error(
                                f"Invalid scratch slot reservation."
                                f" Reserved range must fall entirely between 0"
                                f" and {MAX_SCRATCH_SLOT_NUMBER}",
                                item_expr,
                            )
                        else:
                            scratch_slot_reservations |= slots
                case "state_totals":
                    if not isinstance(kw_expr, mypy.nodes.CallExpr):
                        context.error("Invalid value for state_totals", kw_expr)
                    else:
                        int_args = list[int]()
                        for arg in kw_expr.args:
                            arg_value = arg.accept(expr_visitor)
                            if not isinstance(arg_value, int):
                                context.error("Invalid argument type, expected int literal", arg)
                            else:
                                int_args.append(arg_value)
                        arg_map = get_arg_mapping(
                            positional_arg_names=[],
                            args=zip(kw_expr.arg_names, int_args, strict=True),
                            location=context.node_location(kw_expr),
                        )
                        state_totals = StateTotals(**arg_map)
                case "metaclass":
                    context.error("metaclass option is unsupported", kw_expr)
                case _:
                    context.error("Unrecognised class keyword", kw_expr)
    for base in cdef.info.bases:
        base_cdef = base.type.defn
        if not base_cdef.info.has_base(constants.CONTRACT_BASE):
            continue
        base_options = _process_contract_class_options(context, expr_visitor, base_cdef)
        for reservation in base_options.scratch_slot_reservations:
            scratch_slot_reservations.add(reservation)
    return ContractClassOptions(
        name_override=name_override,
        scratch_slot_reservations=scratch_slot_reservations,
        state_totals=state_totals,
    )


def _process_struct(
    context: ASTConversionModuleContext, cdef: mypy.nodes.ClassDef
) -> StatementResult:
    field_types = dict[str, wtypes.WType]()
    field_decls = list[StructureField]()
    docstring = cdef.docstring
    has_error = False
    for stmt in cdef.defs.body:
        match stmt:
            case mypy.nodes.ExpressionStmt(expr=mypy.nodes.StrExpr()):
                # ignore class docstring, already extracted
                # TODO: should we capture field "docstrings"?
                pass
            case mypy.nodes.AssignmentStmt(
                lvalues=[mypy.nodes.NameExpr(name=field_name)],
                rvalue=mypy.nodes.TempNode(),
                type=mypy.types.Type() as mypy_type,
            ):
                wtype = context.type_to_wtype(mypy_type, source_location=stmt)
                field_types[field_name] = wtype
                field_decls.append(
                    StructureField(
                        source_location=context.node_location(stmt),
                        name=field_name,
                        wtype=wtype,
                    )
                )
            case mypy.nodes.SymbolNode(name=symbol_name) if (
                cdef.info.names[symbol_name].plugin_generated
            ):
                pass
            case _:
                context.error("Unsupported Struct declaration", stmt)
                has_error = True
    if has_error:
        return []
    struct_wtype = wtypes.WStructType.from_name_and_fields(cdef.fullname, field_types)
    context.type_map[cdef.info.fullname] = struct_wtype
    return [
        StructureDefinition(
            name=cdef.name,
            source_location=context.node_location(cdef),
            fields=field_decls,
            wtype=struct_wtype,
            docstring=docstring,
        )
    ]


def _process_arc4_struct(
    context: ASTConversionModuleContext, cdef: mypy.nodes.ClassDef
) -> StatementResult:
    field_types = dict[str, wtypes.ARC4Type]()
    field_decls = list[StructureField]()
    docstring = cdef.docstring

    has_error = False
    for stmt in cdef.defs.body:
        match stmt:
            case mypy.nodes.ExpressionStmt(expr=mypy.nodes.StrExpr()):
                # ignore class docstring, already extracted
                # TODO: should we capture field "docstrings"?
                pass
            case mypy.nodes.AssignmentStmt(
                lvalues=[mypy.nodes.NameExpr(name=field_name)],
                rvalue=mypy.nodes.TempNode(),
                type=mypy.types.Type() as mypy_type,
            ):
                wtype = context.type_to_wtype(mypy_type, source_location=stmt)
                if not wtypes.is_arc4_encoded_type(wtype):
                    context.error(f"Invalid field type for arc4.Struct: {wtype}", stmt)
                    has_error = True
                else:
                    field_types[field_name] = wtype
                    field_decls.append(
                        StructureField(
                            source_location=context.node_location(stmt),
                            name=field_name,
                            wtype=wtype,
                        )
                    )
            case mypy.nodes.SymbolNode(name=symbol_name) if (
                cdef.info.names[symbol_name].plugin_generated
            ):
                pass
            case _:
                context.error("Unsupported arc4.Struct declaration", stmt)
                has_error = True
    if has_error:
        return []
    if not field_types:
        context.error("arc4.Struct requires at least one field", cdef)
        return []
    tuple_wtype = wtypes.ARC4Struct.from_name_and_fields(
        python_name=cdef.fullname, fields=field_types
    )
    context.type_map[cdef.info.fullname] = tuple_wtype
    return [
        StructureDefinition(
            name=cdef.name,
            source_location=context.node_location(cdef),
            fields=field_decls,
            wtype=tuple_wtype,
            docstring=docstring,
        )
    ]


def _map_scratch_space_reservation(
    context: ASTConversionModuleContext,
    expr_visitor: mypy.visitor.ExpressionVisitor[ConstantValue],
    expr: mypy.nodes.Expression,
) -> list[int]:
    def get_int_arg(arg_expr: mypy.nodes.Expression, *, error_msg: str) -> int:
        const_value = arg_expr.accept(expr_visitor)
        if isinstance(const_value, int):
            return const_value
        raise CodeError(error_msg, context.node_location(arg_expr))

    expr_loc = context.node_location(expr)
    match expr:
        case mypy.nodes.CallExpr(
            callee=mypy.nodes.RefExpr() as callee, args=args
        ) if get_unaliased_fullname(callee) == constants.URANGE:
            if not args:
                raise CodeError("Expected at least one argument to urange", expr_loc)
            if len(args) > 3:
                raise CodeError("Expected at most three arguments to urange", expr_loc)
            int_args = [
                get_int_arg(
                    arg_expr,
                    error_msg=(
                        "Unexpected argument for urange:"
                        " expected an in integer literal or module constant reference"
                    ),
                )
                for arg_expr in args
            ]
            if len(int_args) == 3 and int_args[-1] == 0:
                raise CodeError("urange arg 3 must not be zero", context.node_location(args[-1]))
            return list(range(*int_args))
        case _:
            return [
                get_int_arg(
                    expr,
                    error_msg=(
                        "Unexpected value:"
                        " Expected int literal, module constant reference, or urange expression"
                    ),
                )
            ]
