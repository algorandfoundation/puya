import typing

import mypy.nodes
import mypy.visitor
from immutabledict import immutabledict

from puya import log
from puya.avm import OnCompletionAction
from puya.awst.nodes import (
    ABIMethodArgConstantDefault,
    ABIMethodArgDefault,
    ABIMethodArgMemberDefault,
    ARC4ABIMethodConfig,
    ARC4BareMethodConfig,
    ARC4CreateOption,
    Expression,
)
from puya.errors import CodeError, InternalError
from puya.parse import SourceLocation
from puyapy.awst_build import pytypes
from puyapy.awst_build.context import ASTConversionModuleContext
from puyapy.awst_build.eb.interface import NodeBuilder
from puyapy.awst_build.subroutine import ExpressionASTConverter, require_instance_builder
from puyapy.awst_build.utils import extract_decorator_args, get_unaliased_fullname
from puyapy.models import ARC4ABIMethodData, ARC4BareMethodData

logger = log.get_logger(__name__)


def get_arc4_baremethod_data(
    context: ASTConversionModuleContext,
    decorator: mypy.nodes.Expression,
    func_def: mypy.nodes.FuncDef,
) -> ARC4BareMethodData:
    dec_loc = context.node_location(decorator, func_def.info)
    pytype, func_types = _get_func_types(context, func_def, dec_loc)
    if func_types != {"output": pytypes.NoneType}:
        logger.error("bare methods should have no arguments or return values", location=dec_loc)

    named_args = _extract_decorator_named_args(context, decorator, dec_loc)
    evaluated_args = {n: _parse_decorator_arg(context, n, a) for n, a in named_args.items()}

    create = _extract_create_option(evaluated_args, dec_loc)
    allowed_completion_types = _extract_allow_actions_option(evaluated_args, dec_loc)
    if evaluated_args:
        logger.error(
            f"unexpected parameters: {', '.join(map(str, evaluated_args))}", location=dec_loc
        )

    return ARC4BareMethodData(
        member_name=func_def.name,
        pytype=pytype,
        config=ARC4BareMethodConfig(
            allowed_completion_types=allowed_completion_types,
            create=create,
            source_location=dec_loc,
        ),
        source_location=dec_loc,
    )


_READONLY = "readonly"
_CLIENT_DEFAULTS = "default_args"
_ALLOWED_ACTIONS = "allow_actions"
_CREATE_OPTIONS = "create"
_NAME_OVERRIDE = "name"


def get_arc4_abimethod_data(
    context: ASTConversionModuleContext,
    decorator: mypy.nodes.Expression,
    func_def: mypy.nodes.FuncDef,
) -> ARC4ABIMethodData:
    dec_loc = context.node_location(decorator, func_def.info)
    pytype, func_types = _get_func_types(context, func_def, dec_loc)

    named_args = _extract_decorator_named_args(context, decorator, dec_loc)
    evaluated_args = {n: _parse_decorator_arg(context, n, a) for n, a in named_args.items()}

    create = _extract_create_option(evaluated_args, dec_loc)
    allowed_completion_types = _extract_allow_actions_option(evaluated_args, dec_loc)
    # map "name" param
    name = func_def.name
    match evaluated_args.pop(_NAME_OVERRIDE, None):
        case None:
            pass
        case str(name):
            pass
        case invalid_name:
            context.error(f"invalid name option: {invalid_name}", dec_loc)

    # map "readonly" param
    default_readonly = False
    match evaluated_args.pop(_READONLY, default_readonly):
        case bool(readonly):
            pass
        case invalid_readonly_option:
            context.error(f"invalid readonly option: {invalid_readonly_option}", dec_loc)
            readonly = default_readonly

    # map "default_args" param
    default_args = dict[str, ABIMethodArgDefault]()
    match evaluated_args.pop(_CLIENT_DEFAULTS, {}):
        case {**options}:
            method_arg_names = func_types.keys() - {"output"}
            for parameter, value in options.items():
                if parameter not in method_arg_names:
                    context.error(
                        f"{parameter!r} is not a parameter of {func_def.fullname}",
                        dec_loc,
                    )
                else:
                    # if it's in method_arg_names, it's a str
                    assert isinstance(parameter, str)
                    if isinstance(value, str):
                        default_args[parameter] = ABIMethodArgMemberDefault(name=value)
                    elif isinstance(value, Expression):
                        default_args[parameter] = ABIMethodArgConstantDefault(value=value)
                    else:
                        context.error(f"invalid default_args value: {value!r}", dec_loc)
        case invalid_default_args_option:
            context.error(f"invalid default_args option: {invalid_default_args_option}", dec_loc)

    config = ARC4ABIMethodConfig(
        source_location=dec_loc,
        allowed_completion_types=allowed_completion_types,
        create=create,
        name=name,
        readonly=readonly,
        default_args=immutabledict(default_args),
    )
    return ARC4ABIMethodData(
        member_name=func_def.name,
        pytype=pytype,
        config=config,
        signature=func_types,
        source_location=dec_loc,
    )


def _get_func_types(
    context: ASTConversionModuleContext, func_def: mypy.nodes.FuncDef, location: SourceLocation
) -> tuple[pytypes.FuncType, dict[str, pytypes.PyType]]:
    if func_def.type is None:
        raise CodeError("typing error", location)
    func_type = context.type_to_pytype(
        func_def.type, source_location=context.node_location(func_def, module_src=func_def.info)
    )
    if not isinstance(func_type, pytypes.FuncType):
        raise InternalError(
            f"unexpected type result for ABI function definition type: {type(func_type).__name__}",
            location,
        )

    def require_arg_name(arg: pytypes.FuncArg) -> str:
        if arg.name is None:
            raise CodeError(
                "positional only arguments are not supported with ARC-4 methods", location
            )
        return arg.name

    result = {require_arg_name(arg): arg.type for arg in func_type.args}
    if "output" in result:
        # https://github.com/algorandfoundation/ARCs/blob/main/assets/arc-0032/application.schema.json
        raise CodeError(
            "for compatibility with ARC-32, ARC-4 methods cannot have an argument named output",
            location,
        )
    result["output"] = func_type.ret_type
    return func_type, result


def _extract_decorator_named_args(
    context: ASTConversionModuleContext, decorator: mypy.nodes.Expression, location: SourceLocation
) -> dict[str, mypy.nodes.Expression]:
    result = {}
    for name, value in extract_decorator_args(decorator, location):
        if name is None:
            logger.error("unexpected positional argument", location=context.node_location(value))
        elif name in result:
            logger.error("duplicate named argument", location=context.node_location(value))
        else:
            result[name] = value
    return result


def _parse_decorator_arg(
    context: ASTConversionModuleContext, name: str, value: mypy.nodes.Expression
) -> object:
    visitor = _ARC4DecoratorArgEvaluator(context, name)
    return value.accept(visitor)


class _ARC4DecoratorArgEvaluator(mypy.visitor.NodeVisitor[object]):
    def __init__(self, context: ASTConversionModuleContext, arg_name: str):
        self.context = context
        self.arg_name = arg_name

    def __getattribute__(self, name: str) -> object:
        attr = super().__getattribute__(name)
        if name.startswith("visit_") and not attr.__module__.startswith("puyapy."):
            return self._not_supported
        return attr

    def _not_supported(self, o: mypy.nodes.Context) -> typing.Never:
        raise CodeError("unexpected argument type", self.context.node_location(o))

    def _resolve_constant_reference(self, expr: mypy.nodes.RefExpr) -> object:
        try:
            return self.context.constants[expr.fullname]
        except KeyError:
            raise CodeError(
                f"Unresolved module constant: {expr.fullname}", self.context.node_location(expr)
            ) from None

    @typing.override
    def visit_call_expr(self, o: mypy.nodes.CallExpr) -> Expression:
        return _parse_expression(self.context, o)

    @typing.override
    def visit_str_expr(self, o: mypy.nodes.StrExpr) -> str:
        return o.value

    @typing.override
    def visit_name_expr(self, o: mypy.nodes.NameExpr) -> object:
        if self.arg_name == _READONLY:
            if o.fullname == "builtins.True":
                return True
            if o.fullname == "builtins.False":
                return False
        elif self.arg_name == _CLIENT_DEFAULTS:
            if isinstance(o.node, mypy.nodes.Decorator):
                return o.name  # assume abimethod
            if o.fullname in ("builtins.True", "builtins.False"):
                return _parse_expression(self.context, o)
        return self._resolve_constant_reference(o)

    @typing.override
    def visit_member_expr(self, o: mypy.nodes.MemberExpr) -> object:
        if self.arg_name == _ALLOWED_ACTIONS and isinstance(o.expr, mypy.nodes.RefExpr):
            unaliased_base_fullname = get_unaliased_fullname(o.expr)
            if unaliased_base_fullname == pytypes.OnCompleteActionType.name:
                try:
                    OnCompletionAction[o.name]
                except KeyError:
                    raise CodeError(
                        f"unable to resolve constant value for {unaliased_base_fullname}.{o.name}",
                        self.context.node_location(o),
                    ) from None
                else:
                    return o.name

        return self._resolve_constant_reference(o)

    @typing.override
    def visit_unary_expr(self, o: mypy.nodes.UnaryExpr) -> object:
        if self.arg_name == _READONLY:
            operand = o.expr.accept(self)
            if o.op == "not":
                return not operand
        elif self.arg_name == _CLIENT_DEFAULTS:
            return _parse_expression(self.context, o)
        self._not_supported(o)

    @typing.override
    def visit_list_expr(self, o: mypy.nodes.ListExpr) -> object:
        if self.arg_name == _ALLOWED_ACTIONS:
            return [item.accept(self) for item in o.items]
        self._not_supported(o)

    @typing.override
    def visit_tuple_expr(self, o: mypy.nodes.TupleExpr) -> object:
        if self.arg_name == _ALLOWED_ACTIONS:
            return tuple(item.accept(self) for item in o.items)
        elif self.arg_name == _CLIENT_DEFAULTS:
            return _parse_expression(self.context, o)
        self._not_supported(o)

    @typing.override
    def visit_dict_expr(self, o: mypy.nodes.DictExpr) -> dict[object, object]:
        return {key.accept(self) if key else None: value.accept(self) for key, value in o.items}


def _parse_expression(
    context: ASTConversionModuleContext, node: mypy.nodes.Expression
) -> Expression:
    converter = _ConstantExpressionASTConverter(context)
    node_builder = node.accept(converter)
    instance_builder = require_instance_builder(node_builder)
    return instance_builder.resolve()


class _ConstantExpressionASTConverter(ExpressionASTConverter):
    @typing.override
    def resolve_local_type(self, var_name: str, expr_loc: SourceLocation) -> pytypes.PyType | None:
        raise CodeError("local variables not supported in decorators", expr_loc)

    @typing.override
    def builder_for_self(self, expr_loc: SourceLocation) -> NodeBuilder:
        raise InternalError("self variable outside of method", expr_loc)

    @typing.override
    def visit_super_expr(self, o: mypy.nodes.SuperExpr) -> typing.Never:
        raise CodeError("super expressions not supported in decorators", self._location(o))

    @typing.override
    def visit_assignment_expr(self, o: mypy.nodes.AssignmentExpr) -> typing.Never:
        raise CodeError("assignment expressions not supported in decorators", self._location(o))


def _extract_create_option(
    evaluated_args: dict[str, object], location: SourceLocation
) -> ARC4CreateOption:
    default_value = ARC4CreateOption.disallow
    option_name = evaluated_args.pop(_CREATE_OPTIONS, default_value.name)
    try:
        return ARC4CreateOption[option_name]  # type: ignore[misc]
    except KeyError:
        logger.error(  # noqa: TRY400
            f"invalid create option value: {option_name}", location=location
        )
        return default_value


def _extract_allow_actions_option(
    evaluated_args: dict[str, object], location: SourceLocation
) -> list[OnCompletionAction]:
    allowed_completion_types = []
    match evaluated_args.pop(_ALLOWED_ACTIONS, None):
        case None:
            pass
        case []:
            logger.error("empty allow_actions", location=location)
        case [*allow_actions]:
            for a in allow_actions:
                oca = _allowed_oca(a)
                if oca is None:
                    logger.error(f"invalid allow action: {a}", location=location)
                elif oca in allowed_completion_types:
                    logger.error(f"duplicate value in allow_actions: {a}", location=location)
                else:
                    allowed_completion_types.append(oca)
        case invalid_allow_actions_option:
            logger.error(
                f"invalid allow_actions option: {invalid_allow_actions_option}", location=location
            )
    # defaults set last in case of one or more errors above
    return allowed_completion_types or [OnCompletionAction.NoOp]


def _allowed_oca(name: object) -> OnCompletionAction | None:
    if not isinstance(name, str):
        return None
    try:
        result = OnCompletionAction[name]
    except KeyError:
        return None
    if result is OnCompletionAction.ClearState:
        return None
    return result
