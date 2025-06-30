import abc
import typing
from collections.abc import Callable, Sequence

import attrs
import docstring_parser
import mypy.nodes
import mypy.patterns
import mypy.types
import mypy.visitor

from puya import log
from puya.awst.nodes import (
    AppStateExpression,
    AppStorageDefinition,
    ARC4MethodConfig,
    AssertExpression,
    AssignmentExpression,
    AssignmentStatement,
    BinaryBooleanOperator,
    Block,
    BooleanBinaryOperation,
    BytesConstant,
    BytesEncoding,
    ConditionalExpression,
    ContractMethod,
    Expression,
    ExpressionStatement,
    ForInLoop,
    Goto,
    IfElse,
    InstanceSuperMethodTarget,
    Label,
    LoopContinue,
    LoopExit,
    Lvalue,
    MethodDocumentation,
    ReturnStatement,
    Statement,
    Subroutine,
    SubroutineArgument,
    SubroutineID,
    Switch,
    VarExpression,
    WhileLoop,
)
from puya.errors import CodeError, InternalError
from puya.parse import SourceLocation
from puya.program_refs import ContractReference, LogicSigReference
from puyapy import models
from puyapy.awst_build import constants, pytypes
from puyapy.awst_build.base_mypy_visitor import BaseMyPyExpressionVisitor, BaseMyPyStatementVisitor
from puyapy.awst_build.context import ASTConversionModuleContext
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb._literals import LiteralBuilderImpl
from puyapy.awst_build.eb.arc4 import ARC4ClientTypeBuilder
from puyapy.awst_build.eb.conditional_literal import ConditionalLiteralBuilder
from puyapy.awst_build.eb.contracts import (
    ContractSelfExpressionBuilder,
    ContractTypeExpressionBuilder,
)
from puyapy.awst_build.eb.dict_ import DictLiteralBuilder
from puyapy.awst_build.eb.factories import (
    builder_for_instance,
    builder_for_type,
    try_get_builder_for_func,
)
from puyapy.awst_build.eb.interface import (
    BuilderBinaryOp,
    BuilderComparisonOp,
    BuilderUnaryOp,
    CallableBuilder,
    InstanceBuilder,
    LiteralBuilder,
    NodeBuilder,
    StorageProxyConstructorResult,
)
from puyapy.awst_build.eb.logicsig import LogicSigExpressionBuilder
from puyapy.awst_build.eb.subroutine import SubroutineInvokerExpressionBuilder
from puyapy.awst_build.utils import (
    extract_bytes_literal_from_mypy,
    get_decorators_by_fullname,
    get_unaliased_fullname,
    maybe_resolve_literal,
    require_callable_type,
)
from puyapy.models import ContractFragmentBase

logger = log.get_logger(__name__)


@attrs.frozen
class ContractMethodInfo:
    fragment: ContractFragmentBase
    contract_type: pytypes.ContractType
    is_abstract: bool
    arc4_method_config: ARC4MethodConfig | None


class ExpressionASTConverter(BaseMyPyExpressionVisitor[NodeBuilder], abc.ABC):
    @abc.abstractmethod
    def resolve_local_type(
        self, var_name: str, expr_loc: SourceLocation
    ) -> pytypes.PyType | None: ...

    @abc.abstractmethod
    def builder_for_self(self, expr_loc: SourceLocation) -> NodeBuilder: ...

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
        # we can side step complex constructs in the stubs that we don't support in user code,
        # such as overloads.
        if py_typ := self.context.lookup_pytype(expr.fullname):
            if isinstance(py_typ, pytypes.ContractType):
                if fragment := self.context.contract_fragments.get(py_typ.name):
                    return ContractTypeExpressionBuilder(py_typ, fragment, expr_loc)
            elif pytypes.ARC4ClientBaseType < py_typ:  # provides type info only
                if fragment := self.context.contract_fragments.get(ContractReference(py_typ.name)):
                    return ARC4ClientTypeBuilder(py_typ, expr_loc, fragment)
            elif py_typ == pytypes.LogicSigType:
                ref = LogicSigReference(get_unaliased_fullname(expr))
                return LogicSigExpressionBuilder(ref, expr_loc)
            else:
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
            case mypy.nodes.NameExpr(node=mypy.nodes.Var(is_self=True)):
                return self.builder_for_self(expr_loc)
            case mypy.nodes.RefExpr(
                node=mypy.nodes.Decorator() as dec
            ) if constants.SUBROUTINE_HINT in get_decorators_by_fullname(self.context, dec):
                self._precondition(
                    expr.fullname != expr.name,
                    "unqualified name found in call to function",
                    expr_loc,
                )
                mypy_func_type = require_callable_type(dec, expr_loc)
                func_type = self.context.type_to_pytype(mypy_func_type, source_location=expr_loc)
                if not isinstance(func_type, pytypes.FuncType):
                    raise CodeError("decorated function has non-function type", expr_loc)
                return SubroutineInvokerExpressionBuilder(
                    target=SubroutineID(expr.fullname),
                    func_type=func_type,
                    location=expr_loc,
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
                local_type = self.resolve_local_type(var_name, expr_loc)
                if local_type is None:
                    raise CodeError(
                        "local variable type is unknown - possible use before definition?",
                        expr_loc,
                    )
                var_expr = VarExpression(
                    name=var_name,
                    wtype=local_type.checked_wtype(expr_loc),
                    source_location=expr_loc,
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

    @typing.override
    def visit_name_expr(self, expr: mypy.nodes.NameExpr) -> NodeBuilder:
        return self._visit_ref_expr(expr)

    @typing.override
    def visit_member_expr(self, expr: mypy.nodes.MemberExpr) -> NodeBuilder:
        expr_loc = self._location(expr)
        if isinstance(expr.expr, mypy.nodes.RefExpr) and isinstance(
            expr.expr.node, mypy.nodes.MypyFile
        ):
            # special case for module attribute access
            return self._visit_ref_expr(expr)

        base = expr.expr.accept(self)
        return base.member_access(expr.name, expr_loc)

    @typing.override
    def visit_call_expr(self, call: mypy.nodes.CallExpr) -> NodeBuilder:
        if call.analyzed is not None:
            return self._visit_special_call_expr(call, analyzed=call.analyzed)

        callee = call.callee.accept(self)
        if not isinstance(callee, CallableBuilder):
            raise CodeError("not a callable expression", self._location(call.callee))

        args = [arg.accept(self) for arg in call.args]
        return callee.call(
            args=args,
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

    @typing.override
    def visit_unary_expr(self, node: mypy.nodes.UnaryExpr) -> NodeBuilder:
        expr_loc = self._location(node)
        builder_or_literal = node.expr.accept(self)
        match node.op:
            case "not":
                return builder_or_literal.bool_eval(expr_loc, negate=True)
            case op_str if op_str in BuilderUnaryOp:
                builder_op = BuilderUnaryOp(op_str)
                return require_instance_builder(builder_or_literal).unary_op(builder_op, expr_loc)
            case _:
                # guard against future python unary operators
                raise InternalError(f"Unable to interpret unary operator '{node.op}'", expr_loc)

    @typing.override
    def visit_op_expr(self, node: mypy.nodes.OpExpr) -> NodeBuilder:
        node_loc = self._location(node)
        lhs = require_instance_builder(node.left.accept(self))
        rhs = require_instance_builder(node.right.accept(self))

        # mypy combines ast.BoolOp and ast.BinOp, but they're kinda different...
        if node.op in BinaryBooleanOperator:
            bool_op = BinaryBooleanOperator(node.op)
            return lhs.bool_binary_op(rhs, bool_op, node_loc)

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
            raise CodeError(f"unsupported operation {op.value} between types", node_loc)
        return result

    @typing.override
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
            case mypy.nodes.TypeApplication(types=type_args):
                # TODO: resolve expr to generic type builder instead
                assert isinstance(
                    expr.base, mypy.nodes.RefExpr
                ), "expect base of type application to be RefExpr"
                pytyp = self.context.lookup_pytype(expr.base.fullname)
                if pytyp is None:
                    raise CodeError("unknown base type", expr_location)
                param_typ = pytyp.parameterise(
                    [
                        self.context.type_to_pytype(
                            t, in_type_args=True, source_location=expr_location
                        )
                        for t in type_args
                    ],
                    expr_location,
                )
                return builder_for_type(param_typ, expr_location)
            case _:
                typing.assert_never(expr.analyzed)

        base_builder = require_instance_builder(expr.base.accept(self))
        match expr.index:
            # special case handling of SliceExpr, so we don't need to handle slice Literal's
            # or some such everywhere
            # TODO: SliceBuilder?
            case mypy.nodes.SliceExpr(begin_index=begin, end_index=end, stride=stride):
                return base_builder.slice_index(
                    begin_index=(require_instance_builder(begin.accept(self)) if begin else None),
                    end_index=(require_instance_builder(end.accept(self)) if end else None),
                    stride=(require_instance_builder(stride.accept(self)) if stride else None),
                    location=expr_location,
                )

        index_builder = require_instance_builder(expr.index.accept(self))
        return base_builder.index(index=index_builder, location=expr_location)

    @typing.override
    def visit_conditional_expr(self, expr: mypy.nodes.ConditionalExpr) -> NodeBuilder:
        expr_loc = self._location(expr)
        condition = expr.cond.accept(self).bool_eval(self._location(expr.cond))
        true_b = require_instance_builder(expr.if_expr.accept(self))
        false_b = require_instance_builder(expr.else_expr.accept(self))
        if true_b.pytype <= false_b.pytype:
            expr_pytype = true_b.pytype
        elif false_b.pytype < true_b.pytype:
            expr_pytype = false_b.pytype
        else:
            raise CodeError(
                "incompatible result types for 'true' and 'false' expressions", expr_loc
            )

        if (
            isinstance(expr_pytype, pytypes.LiteralOnlyType)
            and isinstance(true_b, LiteralBuilder)
            and isinstance(false_b, LiteralBuilder)
        ):
            return ConditionalLiteralBuilder(
                true_literal=true_b,
                false_literal=false_b,
                condition=condition,
                location=expr_loc,
            )
        else:
            cond_expr = ConditionalExpression(
                condition=condition.resolve(),
                true_expr=true_b.resolve(),
                false_expr=false_b.resolve(),
                source_location=expr_loc,
            )
            return builder_for_instance(expr_pytype, cond_expr)

    @typing.override
    def visit_comparison_expr(self, expr: mypy.nodes.ComparisonExpr) -> NodeBuilder:
        from puyapy.awst_build.eb.bool import BoolExpressionBuilder

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

        operands = [require_instance_builder(o.accept(self)) for o in expr.operands]
        operands[1:-1] = [operand.single_eval() for operand in list(operands)[1:-1]]

        comparisons = [
            self._build_compare(operator=operator, lhs=lhs, rhs=rhs).resolve()
            for operator, lhs, rhs in zip(expr.operators, operands, operands[1:], strict=False)
        ]

        result = prev = comparisons[0]
        for curr in comparisons[1:]:
            result = BooleanBinaryOperation(
                left=result,
                op=BinaryBooleanOperator.and_,
                right=curr,
                source_location=prev.source_location.try_merge(curr.source_location),
            )
            prev = curr
        return BoolExpressionBuilder(result)

    @staticmethod
    def _build_compare(
        operator: str, lhs: InstanceBuilder, rhs: InstanceBuilder
    ) -> InstanceBuilder:
        cmp_loc = lhs.source_location.try_merge(rhs.source_location)
        match operator:
            case "not in":
                return rhs.contains(lhs, cmp_loc).bool_eval(cmp_loc, negate=True)
            case "in":
                return rhs.contains(lhs, cmp_loc)

        result: InstanceBuilder = NotImplemented
        op = BuilderComparisonOp(operator)
        if isinstance(lhs, NodeBuilder):
            result = lhs.compare(other=rhs, op=op, location=cmp_loc)
        if result is NotImplemented and isinstance(rhs, NodeBuilder):
            result = rhs.compare(other=lhs, op=op.reversed(), location=cmp_loc)
        if result is NotImplemented:
            raise CodeError(f"unsupported comparison {operator!r} between types", cmp_loc)
        return result

    @typing.override
    def visit_int_expr(self, expr: mypy.nodes.IntExpr) -> LiteralBuilder:
        return LiteralBuilderImpl(value=expr.value, source_location=self._location(expr))

    @typing.override
    def visit_str_expr(self, expr: mypy.nodes.StrExpr) -> LiteralBuilder:
        return LiteralBuilderImpl(value=expr.value, source_location=self._location(expr))

    @typing.override
    def visit_bytes_expr(self, expr: mypy.nodes.BytesExpr) -> LiteralBuilder:
        bytes_const = extract_bytes_literal_from_mypy(expr)
        return LiteralBuilderImpl(value=bytes_const, source_location=self._location(expr))

    @typing.override
    def visit_tuple_expr(self, mypy_expr: mypy.nodes.TupleExpr) -> NodeBuilder:
        from puyapy.awst_build.eb.tuple import TupleLiteralBuilder

        location = self._location(mypy_expr)
        item_builders = [
            require_instance_builder(mypy_item.accept(self)) for mypy_item in mypy_expr.items
        ]
        return TupleLiteralBuilder(item_builders, location)

    @typing.override
    def visit_dict_expr(self, expr: mypy.nodes.DictExpr) -> NodeBuilder:
        location = self._location(expr)
        mappings = dict[str, InstanceBuilder]()
        for mypy_name, mypy_value in expr.items:
            if mypy_name is None:
                logger.error("None is not usable as a value", location=location)
                continue
            key_node = mypy_name.accept(self)
            value_node = mypy_value.accept(self)
            key = expect.simple_string_literal(key_node, default=expect.default_none)
            value = require_instance_builder(value_node)
            if key is not None:
                mappings[key] = value
        return DictLiteralBuilder(mappings, location)

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


class FunctionASTConverter(
    BaseMyPyStatementVisitor[Statement | Sequence[Statement] | None],
    ExpressionASTConverter,
):
    def __init__(
        self,
        context: ASTConversionModuleContext,
        func_def: mypy.nodes.FuncDef,
        contract_method_info: ContractMethodInfo | None,
        source_location: SourceLocation,
        *,
        inline: bool | None,
    ):
        super().__init__(context=context)
        func_loc = context.node_location(func_def)  # TODO: why not source_location ??
        self.contract_method_info = contract_method_info
        self.func_def = func_def
        self._precondition(
            not func_def.is_trivial_body,
            "trivial functions should be skipped at a higher level",
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
        self._break_label_stack = list[Label | None]()
        # convert the return type
        self._return_type = context.type_to_pytype(type_info.ret_type, source_location=func_loc)
        return_wtype = self._return_type.checked_wtype(func_loc)
        # check & convert the arguments
        mypy_args = func_def.arguments
        mypy_arg_types = type_info.arg_types
        if type_info.def_extras.get("first_arg"):
            # function is a method
            if not mypy_args:
                logger.error("method declaration is missing 'self' argument", location=func_loc)
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
        self._symtable = dict[str, pytypes.PyType]()
        args = list[SubroutineArgument]()
        for arg, arg_type in zip(mypy_args, mypy_arg_types, strict=True):
            arg_loc = context.node_location(arg)
            if arg.kind.is_star():
                raise CodeError("variadic functions are not supported", arg_loc)
            if arg.initializer is not None:
                context.error(
                    "default function argument values are not supported yet", arg.initializer
                )
            pytyp = context.type_to_pytype(arg_type, source_location=arg_loc)
            wtype = pytyp.checked_wtype(arg_loc)
            arg_name = arg.variable.name
            args.append(SubroutineArgument(name=arg_name, wtype=wtype, source_location=arg_loc))
            self._symtable[arg_name] = pytyp
        # translate body
        translated_body = self.visit_block(func_def.body)
        # build result
        self.result: Subroutine | ContractMethod
        documentation = _parse_docstring(func_def.docstring)
        if contract_method_info is None:
            self.result = Subroutine(
                id=func_def.fullname,
                name=func_def.name,
                source_location=source_location,
                args=args,
                return_type=return_wtype,
                body=translated_body,
                documentation=documentation,
                inline=inline,
            )
        else:
            self.result = ContractMethod(
                cref=contract_method_info.fragment.id,
                member_name=func_def.name,
                source_location=source_location,
                args=args,
                return_type=return_wtype,
                body=translated_body,
                documentation=documentation,
                arc4_method_config=contract_method_info.arc4_method_config,
                inline=inline,
            )

    @classmethod
    @typing.overload
    def convert(
        cls,
        context: ASTConversionModuleContext,
        func_def: mypy.nodes.FuncDef,
        source_location: SourceLocation,
        *,
        inline: bool | None,
    ) -> Subroutine: ...

    @classmethod
    @typing.overload
    def convert(
        cls,
        context: ASTConversionModuleContext,
        func_def: mypy.nodes.FuncDef,
        source_location: SourceLocation,
        contract_method_info: ContractMethodInfo,
        *,
        inline: bool | None,
    ) -> ContractMethod: ...

    @classmethod
    def convert(
        cls,
        context: ASTConversionModuleContext,
        func_def: mypy.nodes.FuncDef,
        source_location: SourceLocation,
        contract_method_info: ContractMethodInfo | None = None,
        *,
        inline: bool | None,
    ) -> Subroutine | ContractMethod:
        return cls(
            context=context,
            func_def=func_def,
            contract_method_info=contract_method_info,
            inline=inline,
            source_location=source_location,
        ).result

    @typing.override
    def builder_for_self(self, expr_loc: SourceLocation) -> NodeBuilder:
        if self.contract_method_info is None:
            raise InternalError("variable is inferred as self outside of contract scope", expr_loc)
        return ContractSelfExpressionBuilder(
            fragment=self.contract_method_info.fragment,
            pytype=self.contract_method_info.contract_type,
            location=expr_loc,
        )

    @typing.override
    def resolve_local_type(self, var_name: str, expr_loc: SourceLocation) -> pytypes.PyType | None:
        return self._symtable.get(var_name)

    # expressions

    @typing.override
    def visit_assignment_expr(self, expr: mypy.nodes.AssignmentExpr) -> NodeBuilder:
        expr_loc = self._location(expr)
        self._precondition(
            not isinstance(expr, mypy.nodes.TupleExpr | mypy.nodes.ListExpr),
            "Python doesn't support tuple unpacking in assignment expressions",
            expr_loc,
        )
        # TODO: test if self. assignment?
        source = require_instance_builder(expr.value.accept(self))
        if not self._assign_type(expr.target, source.pytype):
            # typing error, just return the source to continue with
            return source
        value = source.resolve()
        target = self.resolve_lvalue(expr.target)
        result = AssignmentExpression(source_location=expr_loc, value=value, target=target)
        result_typ = source.pytype
        return builder_for_instance(result_typ, result)

    @typing.override
    def visit_super_expr(self, super_expr: mypy.nodes.SuperExpr) -> NodeBuilder:
        super_loc = self._location(super_expr)
        if self.contract_method_info is None:
            raise CodeError("super() expression should not occur outside of class", super_loc)
        if super_expr.call.args:
            raise CodeError(
                "only the zero-arguments version of super() is supported",
                self._location(super_expr.call),
            )
        if (
            super_expr.name.startswith("__")
            and super_expr.name.endswith("__")
            and super_expr.name != "__init__"
        ):
            raise CodeError("the only dunder method supported for calling is init", super_loc)
        for base in self.contract_method_info.fragment.mro:
            try:
                base_sym_typ = base.symbols[super_expr.name]
            except KeyError:
                pass
            else:
                if not isinstance(base_sym_typ, pytypes.FuncType):
                    raise CodeError("super() is only supported for calling functions", super_loc)
                func_type = base_sym_typ
                base_method = base.resolve_method(super_expr.name, include_inherited=False)
                # the check for class abstractness is because in theory the next method in the MRO
                # when compiling a derived class could still be non-trivial
                if (
                    base_method is not None
                    and base_method.is_trivial
                    and not self.contract_method_info.is_abstract
                ):
                    raise CodeError("call to trivial method via super()", super_loc)
                break
        else:
            raise CodeError(
                f"unable to locate method {super_expr.name}"
                f" in bases of {self.contract_method_info.fragment.id}",
                super_loc,
            )

        super_target = InstanceSuperMethodTarget(member_name=super_expr.name)
        return SubroutineInvokerExpressionBuilder(
            target=super_target, func_type=func_type, location=super_loc
        )

    # statements

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
        expr_builder = require_instance_builder(stmt.expr.accept(self))
        if expr_builder.pytype != pytypes.NoneType:
            if isinstance(stmt.expr, mypy.nodes.CallExpr) and isinstance(
                stmt.expr.analyzed, mypy.nodes.RevealExpr | mypy.nodes.AssertTypeExpr
            ):
                # special case to ignore ignoring the result of typing.reveal_type/assert_type
                pass
            elif isinstance(expr_builder.pytype, pytypes.InnerTransactionResultType) or (
                isinstance(expr_builder.pytype, pytypes.TupleLikeType)
                and any(
                    isinstance(i, pytypes.InnerTransactionResultType)
                    for i in expr_builder.pytype.items
                )
            ):
                # special case to ignore inner transaction result types
                # could maybe expand this check to consider whether an expression has known
                # side-effects
                pass
            else:
                self.context.warning("expression result is ignored", stmt_loc)
        return ExpressionStatement(expr=expr_builder.resolve())

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
                assert (
                    len(stmt.lvalues) == 1
                ), "mypy should guarantee that an annotation assigment has only a single lvalue"
                (lvalue,) = stmt.lvalues
                assert (
                    stmt.type is not None
                ), "mypy should guarantee that an annotation assignment has a type set"
                annotated_type = self.context.type_to_pytype(stmt.type, source_location=stmt_loc)
                self._assign_type(lvalue, annotated_type)
                # forward type-declaration only, no-op
                return []
        rvalue = require_instance_builder(stmt.rvalue.accept(self))
        if not all(self._assign_type(lvalue, rvalue.pytype) for lvalue in stmt.lvalues):
            # already a typing error, don't need a second one
            return []

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
            elif rvalue.args.initial_value is not None:
                raise CodeError(
                    "providing an initial value is only allowed"
                    " when assigning to a member variable",
                    stmt_loc,
                )
        elif isinstance(
            rvalue.pytype, pytypes.StorageProxyType | pytypes.StorageMapProxyType
        ) and any(is_self_member(lvalue) for lvalue in stmt.lvalues):
            raise CodeError("unsupported usage of storage type", stmt_loc)
        elif len(stmt.lvalues) > 1:
            rvalue = rvalue.single_eval()

        return [
            AssignmentStatement(
                value=rvalue.resolve(),
                target=self.resolve_lvalue(lvalue),
                source_location=stmt_loc,
            )
            for lvalue in reversed(stmt.lvalues)
        ]

    def _assign_type(
        self,
        lvalue: mypy.nodes.Expression,
        typ: pytypes.PyType,
    ) -> bool:
        match lvalue:
            case mypy.nodes.NameExpr(name=var_name):
                if var_name == "_":
                    raise CodeError(
                        "_ is not currently supported as a variable name", self._location(lvalue)
                    )
                lvalue_loc = self._location(lvalue)
                symbol_type = self._symtable.setdefault(var_name, typ)
                if not (symbol_type <= typ):
                    logger.error(
                        f"{var_name!r} already has type {symbol_type}"
                        f" which is not compatible with {typ}",
                        location=lvalue_loc,
                    )
                    return False
                return True
            case mypy.nodes.TupleExpr(items=lval_items) | mypy.nodes.ListExpr(items=lval_items):
                if star_expr := next(
                    (
                        lval_item
                        for lval_item in lval_items
                        if isinstance(lval_item, mypy.nodes.StarExpr)
                    ),
                    None,
                ):
                    raise CodeError(
                        "star expressions are not supported", self._location(star_expr)
                    )
                match typ:
                    case pytypes.SequenceType(items=homogenous_type):
                        tuple_item_types = (homogenous_type,) * len(lval_items)
                    case pytypes.TupleLikeType(items=tuple_item_types):
                        if len(tuple_item_types) != len(lval_items):
                            raise CodeError(
                                f"length mismatch source size of {len(tuple_item_types)}"
                                f" and target size of {len(lval_items)}",
                                self._location(lvalue),
                            )
                    case _:
                        raise CodeError(
                            "source type not supported for unpacking", self._location(lvalue)
                        )
                return all(
                    self._assign_type(lval_item, inner_typ)
                    for lval_item, inner_typ in zip(lval_items, tuple_item_types, strict=True)
                )
            case _:
                return True

    def _handle_proxy_assignment(
        self,
        lvalue: mypy.nodes.MemberExpr,
        rvalue: StorageProxyConstructorResult,
        stmt_loc: SourceLocation,
    ) -> Sequence[Statement]:
        if self.contract_method_info is None:
            raise InternalError("Assignment to self outside of a contract class", stmt_loc)
        pytype = rvalue.pytype
        if self.func_def.name != "__init__":
            raise CodeError(
                f"{pytype.generic or pytype}"
                " can only be assigned to a member variable in the __init__ method",
                stmt_loc,
            )
        member_loc = self._location(lvalue)
        member_name = lvalue.name
        storage = self.contract_method_info.fragment.resolve_storage(member_name)
        if storage is None:
            raise CodeError("unable to resolve class storage member", member_loc)
        if storage.definition is not None:
            logger.info(
                f"previous definition of {member_name} was here",
                location=storage.definition.source_location,
            )
            logger.error(
                f"redefinition of {member_name}",
                location=stmt_loc,
            )

        key = rvalue.args.key
        if key is None:
            key = BytesConstant(
                value=member_name.encode("utf8"),
                wtype=pytype.wtype,
                encoding=BytesEncoding.utf8,
                source_location=member_loc,
            )
        elif not isinstance(key, BytesConstant):
            logger.error(
                f"assigning {pytype} to a member variable"
                f" requires a constant value for {rvalue.args.key_arg_name}",
                location=stmt_loc,
            )
            key = BytesConstant(
                value=b"0",
                wtype=key.wtype,
                encoding=BytesEncoding.unknown,
                source_location=key.source_location,
            )
        storage.definition = AppStorageDefinition(
            source_location=member_loc,
            member_name=member_name,
            kind=storage.kind,
            storage_wtype=pytype.content_wtype,
            key_wtype=(
                pytype.key_wtype if isinstance(pytype, pytypes.StorageMapProxyType) else None
            ),
            key=key,
            description=rvalue.args.description,
        )

        if rvalue.args.initial_value is None:
            return []
        match pytype:
            case pytypes.StorageProxyType(
                generic=pytypes.GenericGlobalStateType, content_wtype=content_wtype
            ):
                global_state_target = AppStateExpression(
                    key=key,
                    exists_assertion_message=None,  # this is a write, not a read
                    wtype=content_wtype,
                    source_location=member_loc,
                )
                return [
                    AssignmentStatement(
                        target=global_state_target,
                        value=rvalue.args.initial_value.resolve(),
                        source_location=stmt_loc,
                    )
                ]
            case unhandled:
                raise InternalError(
                    f"Don't know how to do initialise-on-declaration for {unhandled}", stmt_loc
                )

    def resolve_lvalue(self, lvalue: mypy.nodes.Expression) -> Lvalue:
        builder_or_literal = lvalue.accept(self)
        builder = require_instance_builder(builder_or_literal)
        return builder.resolve_lvalue()

    @typing.override
    def empty_statement(self, stmt: mypy.nodes.Statement) -> None:
        return None

    def visit_operator_assignment_stmt(self, stmt: mypy.nodes.OperatorAssignmentStmt) -> Statement:
        stmt_loc = self._location(stmt)
        builder = require_instance_builder(stmt.lvalue.accept(self))
        rhs = require_instance_builder(stmt.rvalue.accept(self))
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
        condition = expr.accept(self).bool_eval(self._location(expr))
        if_branch = self.visit_block(if_body)
        else_branch = self.visit_block(stmt.else_body) if stmt.else_body else None
        return IfElse(
            source_location=self._location(stmt),
            condition=condition.resolve(),
            if_branch=if_branch,
            else_branch=else_branch,
        )

    @typing.overload
    def _build_loop(
        self,
        stmt: mypy.nodes.WhileStmt,
        ctor: Callable[[Block, SourceLocation], WhileLoop],
    ) -> WhileLoop | Block: ...

    @typing.overload
    def _build_loop(
        self,
        stmt: mypy.nodes.ForStmt,
        ctor: Callable[[Block, SourceLocation], ForInLoop],
    ) -> ForInLoop | Block: ...

    def _build_loop(
        self,
        stmt: mypy.nodes.WhileStmt | mypy.nodes.ForStmt,
        ctor: Callable[[Block, SourceLocation], WhileLoop | ForInLoop],
    ) -> WhileLoop | ForInLoop | Block:
        loop_loc = self._location(stmt)
        if stmt.else_body is None:
            break_label = None
        else:
            break_label = Label(f"after_loop_L{loop_loc.line}")

        self._break_label_stack.append(break_label)
        try:
            block = self.visit_block(stmt.body)
        finally:
            self._break_label_stack.pop()
        loop = ctor(block, loop_loc)
        if stmt.else_body is None:
            return loop
        else_body = self.visit_block(stmt.else_body)
        # empty block, exists so we have a goto target that skips the else body
        after_block = Block(label=break_label, body=[], source_location=loop_loc)
        return Block(
            body=[loop, else_body, after_block],
            comment=f"loop_with_else_L{loop_loc.line}",
            source_location=loop_loc,
        )

    def visit_while_stmt(self, stmt: mypy.nodes.WhileStmt) -> WhileLoop | Block:
        condition = stmt.expr.accept(self).bool_eval(self._location(stmt.expr))
        return self._build_loop(
            stmt,
            lambda loop_body, loop_loc: WhileLoop(
                condition=condition.resolve(),
                loop_body=loop_body,
                source_location=loop_loc,
            ),
        )

    def visit_for_stmt(self, stmt: mypy.nodes.ForStmt) -> ForInLoop | Block:
        sequence_builder = require_instance_builder(stmt.expr.accept(self))
        sequence = sequence_builder.iterate()
        iter_item_type = sequence_builder.iterable_item_type()
        self._assign_type(stmt.index, iter_item_type)
        items = self.resolve_lvalue(stmt.index)
        return self._build_loop(
            stmt,
            lambda loop_body, loop_loc: ForInLoop(
                items=items,
                sequence=sequence,
                loop_body=loop_body,
                source_location=loop_loc,
            ),
        )

    def visit_break_stmt(self, stmt: mypy.nodes.BreakStmt) -> LoopExit | Goto:
        stmt_loc = self._location(stmt)
        break_label = self._break_label_stack[-1]
        if break_label is None:
            return LoopExit(stmt_loc)
        else:
            return Goto(target=break_label, source_location=stmt_loc)

    def visit_continue_stmt(self, stmt: mypy.nodes.ContinueStmt) -> LoopContinue:
        return LoopContinue(self._location(stmt))

    def visit_assert_stmt(self, stmt: mypy.nodes.AssertStmt) -> ExpressionStatement:
        error_message: str | None = None
        if stmt.msg is not None:
            msg = stmt.msg.accept(self)
            match msg:
                case LiteralBuilder(value=str(error_message)):
                    pass
                case _:
                    self._error("only literal strings are supported as assertion messages", stmt)
        condition = stmt.expr.accept(self).bool_eval(self._location(stmt.expr))
        return ExpressionStatement(
            AssertExpression(
                condition=condition.resolve(),
                error_message=error_message,
                source_location=self._location(stmt),
            )
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
        if not (self._return_type <= returning_builder.pytype):
            self._error(
                f"invalid return type of {returning_builder.pytype}, expected {self._return_type}",
                loc,
            )
        return ReturnStatement(source_location=loc, value=returning_builder.resolve())

    def visit_match_stmt(self, stmt: mypy.nodes.MatchStmt) -> Switch | None:
        loc = self._location(stmt)
        subject = require_instance_builder(stmt.subject.accept(self))
        case_block_map = dict[Expression, Block]()
        default_block: Block | None = None
        for pattern, guard, block in zip(stmt.patterns, stmt.guards, stmt.bodies, strict=True):
            if guard is not None:
                self._error("guard clauses are not supported", guard)
            if default_block is not None:
                self._error("default case already encountered", pattern)
                continue
            case_block = self.visit_block(block)
            pattern_loc = self._location(pattern)
            case_value_builder: InstanceBuilder | None = None
            match pattern:
                case mypy.patterns.AsPattern(name=None, pattern=None):
                    default_block = case_block
                case mypy.patterns.ValuePattern(expr=case_expr):
                    case_value_builder = require_instance_builder(case_expr.accept(self))
                    case_value_builder = maybe_resolve_literal(case_value_builder, subject.pytype)
                case mypy.patterns.SingletonPattern(value=bool(bool_literal)):
                    case_value_builder = LiteralBuilderImpl(
                        value=bool_literal, source_location=pattern_loc
                    )
                    case_value_builder = maybe_resolve_literal(case_value_builder, subject.pytype)
                case mypy.patterns.ClassPattern() as cls_pattern:
                    class_builder = cls_pattern.class_ref.accept(self)
                    if not isinstance(class_builder, CallableBuilder):
                        logger.error("expected a type", location=class_builder.source_location)
                    elif cls_pattern.keyword_values:
                        self._error(
                            "attribute matching is not supported", cls_pattern.keyword_values[0]
                        )
                    else:
                        cls_args = []
                        has_error = False
                        for pos_case in cls_pattern.positionals:
                            if isinstance(pos_case, mypy.patterns.ValuePattern):
                                cls_args.append(pos_case.expr.accept(self))
                            else:
                                has_error = True
                                self._error("expected a value pattern", pos_case)
                        if not has_error:
                            case_value_builder = class_builder.call(
                                args=cls_args,
                                arg_kinds=[models.ArgKind.ARG_POS] * len(cls_args),
                                arg_names=[None] * len(cls_args),
                                location=pattern_loc,
                            )

                case _:
                    logger.error("unsupported case pattern", location=pattern_loc)
            if case_value_builder is not None:
                if case_value_builder.pytype != subject.pytype:
                    # TODO: what about other comparable types, or subtypes?
                    logger.error(
                        "type mismatch,"
                        " case values must be the exact same type as the subject type",
                        location=pattern_loc,
                    )
                else:
                    case_block_map[case_value_builder.resolve()] = case_block

        return Switch(
            source_location=loc,
            value=subject.resolve(),
            cases=case_block_map,
            default_case=default_block,
        )

    # Unsupported statements
    @typing.override
    def visit_function(self, fdef: mypy.nodes.FuncDef, _: mypy.nodes.Decorator | None) -> None:
        self._error("nested functions are not supported", fdef)

    @typing.override
    def visit_class_def(self, cdef: mypy.nodes.ClassDef) -> None:
        self._error("classes nested inside functions are not supported", cdef)

    @typing.override
    def visit_type_alias_stmt(self, o: mypy.nodes.TypeAliasStmt) -> None:
        self._error("type alias statements are not supported", o)


def is_self_member(
    expr: mypy.nodes.Expression,
) -> typing.TypeGuard[mypy.nodes.MemberExpr]:
    match expr:
        case mypy.nodes.MemberExpr(expr=mypy.nodes.NameExpr(node=mypy.nodes.Var(is_self=True))):
            return True
    return False


def require_instance_builder(builder_or_literal: NodeBuilder) -> InstanceBuilder:
    return expect.instance_builder(builder_or_literal, default=expect.default_raise)


def _parse_docstring(docstring_raw: str | None) -> MethodDocumentation:
    if docstring_raw is None:
        return MethodDocumentation()
    docstring = docstring_parser.parse(docstring_raw)
    method_desc = "\n".join(
        _join_single_new_line(line)
        for lines in filter(None, (docstring.short_description, docstring.long_description))
        for line in lines.split("\n\n")
    )
    return MethodDocumentation(
        description=method_desc if method_desc else None,
        args={
            p.arg_name: _join_single_new_line(p.description)
            for p in docstring.params
            if p.description
        },
        returns=(
            _join_single_new_line(docstring.returns.description)
            if docstring.returns and docstring.returns.description
            else None
        ),
    )


def _join_single_new_line(doc: str) -> str:
    return doc.strip().replace("\n", " ")
