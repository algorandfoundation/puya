import typing as t

import mypy.nodes
import mypy.types
import mypy.visitor
import structlog

from puya.awst import wtypes
from puya.awst.nodes import (
    ConstantDeclaration,
    ConstantValue,
    Module,
    ModuleStatement,
    StructureDefinition,
    StructureField,
)
from puya.awst_build import constants
from puya.awst_build.base_mypy_visitor import BaseMyPyVisitor
from puya.awst_build.context import ASTConversionContext
from puya.awst_build.contract import ContractASTConverter
from puya.awst_build.exceptions import UnsupportedASTError
from puya.awst_build.subroutine import FunctionASTConverter
from puya.awst_build.utils import (
    extract_bytes_literal_from_mypy,
    extract_docstring,
    fold_binary_expr,
    get_decorators_by_fullname,
)
from puya.errors import CodeError, InternalError

logger = structlog.get_logger()


class ModuleASTConverter(BaseMyPyVisitor[None, ConstantValue]):
    """This does basic validation, and traversal of valid module scope elements, collecting
    and folding constants.

    Note that constants must appear before usage, unlike in regular Python.

    TODO: maybe collect constants in a pre-processing step?
    """

    def __init__(self, context: ASTConversionContext, module: mypy.nodes.MypyFile):
        super().__init__(context=context.for_module(module))

        docstring = extract_docstring(module)

        self._statements = list[ModuleStatement]()
        for node in module.defs:
            with self.context.log_exceptions(fallback_location=node):
                node.accept(self)
        self.result = Module(
            name=module.name,
            source_file_path=module.path,
            docstring=docstring,
            body=self._statements,
        )

    @classmethod
    def convert(cls, context: ASTConversionContext, module: mypy.nodes.MypyFile) -> Module:
        return cls(context=context, module=module).result

    # Supported Statements

    def empty_statement(self, _stmt: mypy.nodes.Statement) -> None:
        return None

    def visit_function(
        self, func_def: mypy.nodes.FuncDef, decorator: mypy.nodes.Decorator | None
    ) -> None:
        self._precondition(
            func_def.abstract_status == mypy.nodes.NOT_ABSTRACT,
            "module level functions should not be classified as abstract by mypy",
            decorator or func_def,
        )
        dec_by_fullname = get_decorators_by_fullname(self.context, decorator) if decorator else {}
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

        sub = FunctionASTConverter.convert(self.context, func_def)
        self._statements.append(sub)

    def visit_class_def(self, cdef: mypy.nodes.ClassDef) -> None:
        self.check_fatal_decorators(cdef.decorators)
        match cdef.analyzed:
            case None:
                pass
            case mypy.nodes.TypedDictExpr():
                raise UnsupportedASTError(
                    self._location(cdef), details="TypedDict classes are not supported"
                )
            case mypy.nodes.NamedTupleExpr():
                raise UnsupportedASTError(
                    self._location(cdef), details="NamedTuple classes are not supported"
                )
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
                self._process_arc4_struct(cdef)
        elif cdef.info.has_base(constants.STRUCT_BASE):
            if [ti.fullname for ti in cdef.info.direct_base_classes()] != [constants.STRUCT_BASE]:
                # TODO: allow inheritance of Structs?
                self._error("Struct classes must only inherit directly from Struct", cdef)
            else:
                self._process_struct(cdef)
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
                name_override: str | None = None
                for kw_name, kw_expr in cdef.keywords.items():
                    with self.context.log_exceptions(kw_expr):
                        kw_value = kw_expr.accept(self)
                        match kw_name, kw_value:
                            case "name", str(name_value):
                                name_override = name_value
                            case "name", _:
                                self._error("Invalid type for name=", kw_expr)
                            case _, _:
                                self._error("Unrecognised class keyword", kw_expr)

                self._statements.append(
                    ContractASTConverter.convert(self.context, cdef, name_override)
                )
        else:
            self._error(
                f"not a subclass of {constants.CONTRACT_BASE_ALIAS}"
                f" or a direct subclass of {constants.STRUCT_BASE_ALIAS}",
                location=cdef,
            )

    def _process_arc4_struct(self, cdef: mypy.nodes.ClassDef) -> None:
        field_types = dict[str, wtypes.WType]()
        field_decls = list[StructureField]()
        docstring = extract_docstring(cdef)

        for stmt in cdef.defs.body:
            match stmt:
                case mypy.nodes.AssignmentStmt(
                    lvalues=[mypy.nodes.NameExpr(name=field_name)],
                    rvalue=mypy.nodes.TempNode(),
                    type=mypy.types.Type() as mypy_type,
                ):
                    wtype = self.context.type_to_wtype(mypy_type, source_location=stmt)
                    if not wtypes.is_arc4_encoded_type(wtype):
                        raise CodeError(
                            f"Invalid field type for arc4.Struct: {wtype}", self._location(stmt)
                        )
                    field_types[field_name] = wtype
                    field_decls.append(
                        StructureField(
                            source_location=self._location(stmt),
                            name=field_name,
                            wtype=wtype,
                        )
                    )
                case mypy.nodes.SymbolNode(name=symbol_name) if (
                    cdef.info.names[symbol_name].plugin_generated
                ):
                    pass
                case _:
                    self._error("Unsupported Struct declaration", stmt)
        if not field_types:
            raise CodeError("arc4.Struct requires at least one field", self._location(cdef))
        tuple_wtype = wtypes.ARC4Struct.from_name_and_fields(
            python_name=cdef.fullname, fields=field_types
        )
        self._statements.append(
            StructureDefinition(
                name=cdef.name,
                source_location=self._location(cdef),
                fields=field_decls,
                wtype=tuple_wtype,
                docstring=docstring,
            )
        )
        self.context.type_map[cdef.info.fullname] = tuple_wtype

    def _process_struct(self, cdef: mypy.nodes.ClassDef) -> None:
        field_types = dict[str, wtypes.WType]()
        field_decls = list[StructureField]()
        docstring = extract_docstring(cdef)
        for stmt in cdef.defs.body:
            match stmt:
                case mypy.nodes.AssignmentStmt(
                    lvalues=[mypy.nodes.NameExpr(name=field_name)],
                    rvalue=mypy.nodes.TempNode(),
                    type=mypy.types.Type() as mypy_type,
                ):
                    wtype = self.context.type_to_wtype(mypy_type, source_location=stmt)
                    field_decls.append(
                        StructureField(
                            source_location=self._location(stmt),
                            name=field_name,
                            wtype=wtype,
                        )
                    )
                    field_types[field_name] = wtype
                case mypy.nodes.SymbolNode(name=symbol_name) if (
                    cdef.info.names[symbol_name].plugin_generated
                ):
                    pass
                case _:
                    self._error("Unsupported Struct declaration", stmt)
        struct_wtype = wtypes.WStructType.from_name_and_fields(cdef.fullname, field_types)
        self._statements.append(
            StructureDefinition(
                name=cdef.name,
                source_location=self._location(cdef),
                fields=field_decls,
                wtype=struct_wtype,
                docstring=docstring,
            )
        )
        self.context.type_map[cdef.info.fullname] = struct_wtype

    def visit_operator_assignment_stmt(self, stmt: mypy.nodes.OperatorAssignmentStmt) -> None:
        match stmt.lvalue:
            case mypy.nodes.NameExpr(name="__all__"):
                # TODO: this value is technically usable at runtime in Python,
                #       any references to it in the method bodies should fail
                pass  # skip it
            case _:
                self._unsupported(stmt)

    def visit_if_stmt(self, stmt: mypy.nodes.IfStmt) -> None:
        for expr, block in zip(stmt.expr, stmt.body, strict=True):
            if self._evaluate_compile_time_constant_condition(expr):
                block.accept(self)
                break
        else:
            # if we didn't "break", we end up here, which means the user code
            # should evaluate to the else body (if present)
            if stmt.else_body:
                stmt.else_body.accept(self)

    def visit_assignment_stmt(self, stmt: mypy.nodes.AssignmentStmt) -> None:
        self._precondition(
            bool(stmt.lvalues), "assignment statements should have at least one lvalue", stmt
        )
        self._precondition(
            not stmt.invalid_recursive_alias,
            "assignment statement with invalid_recursive_alias",
            stmt,
        )
        if stmt.is_alias_def:  # ie is this a typing.TypeAlias
            return  # skip it
        match stmt.lvalues:
            case [mypy.nodes.NameExpr(name="__all__")]:
                # TODO: this value is technically usable at runtime in Python,
                #       any references to it in the method bodies should fail
                return  # skip it
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
                        return  # skip it
        rvalue = stmt.rvalue.accept(self)
        for lvalue in stmt.lvalues:
            match lvalue:
                case mypy.nodes.NameExpr() as name_expr:
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
                    self.context.constants[fullname] = rvalue
                    self._statements.append(
                        ConstantDeclaration(
                            name=name_expr.name,
                            value=rvalue,
                            source_location=self._location(lvalue),
                        )
                    )
                case _:
                    self._unsupported(
                        lvalue,
                        "only straight-forward assignment targets supported at module level",
                    )

    def visit_block(self, block: mypy.nodes.Block) -> None:
        for stmt in block.body:
            stmt.accept(self)

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
        try:
            result = eval(  # noqa: PGH001
                f"{expr.op} value",
                {"value": value},
            )
        except Exception as ex:
            self._unsupported(expr, details=str(ex), ex=ex)
        if not isinstance(
            result,
            int | str | bytes | bool,  # TODO: why can't we use ConstantValue here?
        ):
            self._unsupported(expr, details=f"unsupported result type of {type(result).__name__}")
        return result

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
        raise UnsupportedASTError(self._location(node), details=details) from ex

    # Unsupported Statements

    def visit_expression_stmt(self, stmt: mypy.nodes.ExpressionStmt) -> None:
        self._unsupported(stmt)

    def visit_while_stmt(self, stmt: mypy.nodes.WhileStmt) -> None:
        self._unsupported(stmt)

    def visit_for_stmt(self, stmt: mypy.nodes.ForStmt) -> None:
        self._unsupported(stmt)

    def visit_break_stmt(self, stmt: mypy.nodes.BreakStmt) -> None:
        self._unsupported(stmt)

    def visit_continue_stmt(self, stmt: mypy.nodes.ContinueStmt) -> None:
        self._unsupported(stmt)

    def visit_assert_stmt(self, stmt: mypy.nodes.AssertStmt) -> None:
        self._unsupported(stmt)

    def visit_del_stmt(self, stmt: mypy.nodes.DelStmt) -> None:
        self._unsupported(stmt)

    def visit_match_stmt(self, stmt: mypy.nodes.MatchStmt) -> None:
        self._unsupported(stmt)

    # the remaining statements (below) are invalid at the module lexical scope,
    # mypy should have caught these errors already
    def visit_return_stmt(self, stmt: mypy.nodes.ReturnStmt) -> None:
        raise InternalError("encountered return statement at module level", self._location(stmt))

    def visit_nonlocal_decl(self, stmt: mypy.nodes.NonlocalDecl) -> None:
        raise InternalError(
            "encountered nonlocal declaration at module level", self._location(stmt)
        )

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
