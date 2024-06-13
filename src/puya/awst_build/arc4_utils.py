import typing
from collections.abc import Sequence

import attrs
import mypy.nodes
import mypy.types
import mypy.visitor
from immutabledict import immutabledict

import puya.models
from puya.arc4_util import pytype_to_arc4
from puya.awst_build import constants, pytypes
from puya.awst_build.context import ASTConversionModuleContext
from puya.awst_build.utils import extract_bytes_literal_from_mypy, get_unaliased_fullname
from puya.errors import CodeError, InternalError
from puya.models import (
    ARC4ABIMethodConfig,
    ARC4BareMethodConfig,
    ARC4MethodConfig,
    ARC32StructDef,
    OnCompletionAction,
)
from puya.parse import SourceLocation

__all__ = [
    "ARC4MethodData",
    "get_arc4_method_data",
]


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


def _is_arc4_struct(typ: pytypes.PyType) -> typing.TypeGuard[pytypes.StructType]:
    if pytypes.ARC4StructBaseType not in typ.mro:
        return False
    if not isinstance(typ, pytypes.StructType):
        raise InternalError(
            f"Type inherits from {pytypes.ARC4StructBaseType!r}"
            f" but structure type is {type(typ).__name__!r}"
        )
    return True


@attrs.frozen
class ARC4MethodData:
    config: ARC4MethodConfig
    _signature: dict[str, pytypes.PyType]

    @property
    def return_type(self) -> pytypes.PyType:
        return self._signature["output"]

    @property
    def argument_types(self) -> Sequence[pytypes.PyType]:
        names, types = zip(*self._signature.items(), strict=True)
        assert names[-1] == "output"
        return types[:-1]


def get_arc4_method_data(
    context: ASTConversionModuleContext,
    decorator: mypy.nodes.Expression,
    func_def: mypy.nodes.FuncDef,
) -> ARC4MethodData:
    dec_loc = context.node_location(decorator, func_def.info)
    func_types = _get_func_types(context, func_def, dec_loc)
    config: ARC4MethodConfig
    match decorator:
        case mypy.nodes.RefExpr(fullname=fullname):
            if fullname == constants.BAREMETHOD_DECORATOR:
                config = ARC4BareMethodConfig(source_location=dec_loc)
            else:
                config = ARC4ABIMethodConfig(
                    name=func_def.name,
                    source_location=dec_loc,
                )
        case mypy.nodes.CallExpr(
            args=args,
            arg_names=arg_names,
            callee=mypy.nodes.RefExpr(fullname=fullname),
        ):
            visitor = _ARC4DecoratorArgEvaluator(context)
            abi_hints = {n: a.accept(visitor) for n, a in zip(arg_names, args, strict=True)}

            # map "create" param
            allow_create = False
            require_create = False
            match abi_hints.pop("create", None):
                case "allow":
                    allow_create = True
                case "require":
                    require_create = True
                case "disallow" | None:
                    pass
                case invalid_create_option:
                    context.error(f"invalid create option: {invalid_create_option}", dec_loc)

            # map "allow_actions" param
            allowed_completion_types = []
            match abi_hints.pop("allow_actions", None):
                case None:
                    allowed_completion_types = [puya.models.OnCompletionAction.NoOp]
                case []:
                    context.error("must have at least one allow_actions", dec_loc)
                case [*allow_actions]:
                    for a in allow_actions:
                        oca = _allowed_oca(a)
                        if oca is None:
                            context.error(f"invalid allow action: {a}", dec_loc)
                        elif oca in allowed_completion_types:
                            context.error(f"duplicate value in allow_actions: {a}", dec_loc)
                        else:
                            allowed_completion_types.append(oca)
                case invalid_allow_actions_option:
                    context.error(
                        f"invalid allow_actions option: {invalid_allow_actions_option}", dec_loc
                    )

            if fullname == constants.BAREMETHOD_DECORATOR:
                config = ARC4BareMethodConfig(
                    source_location=dec_loc,
                    allowed_completion_types=allowed_completion_types,
                    allow_create=allow_create,
                    require_create=require_create,
                )
            else:
                # map "name" param
                name = func_def.name
                match abi_hints.pop("name", None):
                    case None:
                        pass
                    case str(name):
                        pass
                    case invalid_name:
                        context.error(f"invalid name option: {invalid_name}", dec_loc)

                # map "readonly" param
                readonly = False
                match abi_hints.pop("readonly", None):
                    case None:
                        pass
                    case bool(readonly):
                        pass
                    case invalid_readonly_option:
                        context.error(
                            f"invalid readonly option: {invalid_readonly_option}", dec_loc
                        )

                # map "default_args" param
                default_args = dict[str, str]()
                match abi_hints.pop("default_args", {}):
                    case {**options}:
                        method_arg_names = func_types.keys() - {"output"}
                        for parameter, value in options.items():
                            if parameter not in method_arg_names:
                                context.error(
                                    f"{parameter!r} is not a parameter of {func_def.fullname}",
                                    dec_loc,
                                )
                            elif not isinstance(value, str):
                                context.error(f"invalid default_args value: {value!r}", dec_loc)
                            else:
                                # if it's in method_arg_names, it's a str
                                assert isinstance(parameter, str)
                                default_args[parameter] = value
                    case invalid_default_args_option:
                        context.error(
                            f"invalid default_args option: {invalid_default_args_option}", dec_loc
                        )

                structs = immutabledict[str, ARC32StructDef](
                    {
                        n: _wtype_to_struct_def(pt)
                        for n, pt in func_types.items()
                        if _is_arc4_struct(pt)
                    }
                )
                config = ARC4ABIMethodConfig(
                    source_location=dec_loc,
                    allowed_completion_types=allowed_completion_types,
                    allow_create=allow_create,
                    require_create=require_create,
                    name=name,
                    readonly=readonly,
                    default_args=immutabledict(default_args),
                    structs=structs,
                )

            if abi_hints:
                context.error(f"unexpected parameters: {', '.join(map(str, abi_hints))}", dec_loc)

        case unexpected_node:
            raise CodeError(f"unexpected ARC4 decorator node: {unexpected_node}", dec_loc)
    return ARC4MethodData(config=config, signature=func_types)


class _ARC4DecoratorArgEvaluator(mypy.visitor.NodeVisitor[object]):
    def __init__(self, context: ASTConversionModuleContext):
        self.context = context

    def __getattribute__(self, name: str) -> object:
        attr = super().__getattribute__(name)
        if name.startswith("visit_") and not attr.__module__.startswith("puya."):
            return self._not_supported
        return attr

    def _not_supported(self, o: mypy.nodes.Context) -> typing.Never:
        raise CodeError("Unsupported expression in ARC4 decorator", self.context.node_location(o))

    @typing.override
    def visit_int_expr(self, o: mypy.nodes.IntExpr) -> int:
        return o.value

    @typing.override
    def visit_str_expr(self, o: mypy.nodes.StrExpr) -> str:
        return o.value

    @typing.override
    def visit_bytes_expr(self, o: mypy.nodes.BytesExpr) -> bytes:
        return extract_bytes_literal_from_mypy(o)

    @typing.override
    def visit_name_expr(self, o: mypy.nodes.NameExpr) -> object:
        if o.fullname == "builtins.True":
            return True
        elif o.fullname == "builtins.False":
            return False
        elif o.fullname == "builtins.None":
            return None
        elif isinstance(o.node, mypy.nodes.Decorator):
            return o.name  # assume abimethod
        else:
            return self._resolve_constant_reference(o)

    @typing.override
    def visit_member_expr(self, o: mypy.nodes.MemberExpr) -> object:
        expr_loc = self.context.node_location(o)
        if isinstance(o.expr, mypy.nodes.RefExpr):
            unaliased_base_fullname = get_unaliased_fullname(o.expr)
            if unaliased_base_fullname == constants.ENUM_CLS_ON_COMPLETE_ACTION:
                if (
                    o.name
                    in constants.NAMED_INT_CONST_ENUM_DATA[constants.ENUM_CLS_ON_COMPLETE_ACTION]
                ):
                    return o.name
                raise CodeError(
                    f"Unable to resolve constant value for {unaliased_base_fullname}.{o.name}",
                    expr_loc,
                )
        return self._resolve_constant_reference(o)

    def _resolve_constant_reference(self, expr: mypy.nodes.RefExpr) -> object:

        try:
            return self.context.constants[expr.fullname]
        except KeyError:
            raise CodeError(
                f"Unresolved module constant: {expr.fullname}", self.context.node_location(expr)
            ) from None

    @typing.override
    def visit_unary_expr(self, o: mypy.nodes.UnaryExpr) -> object:
        operand = o.expr.accept(self)
        if o.op == "not":
            return not operand
        self._not_supported(o)

    @typing.override
    def visit_list_expr(self, o: mypy.nodes.ListExpr) -> list[object]:
        return [item.accept(self) for item in o.items]

    @typing.override
    def visit_tuple_expr(self, o: mypy.nodes.TupleExpr) -> tuple[object, ...]:
        return tuple(item.accept(self) for item in o.items)

    @typing.override
    def visit_dict_expr(self, o: mypy.nodes.DictExpr) -> dict[object, object]:
        return {key.accept(self) if key else None: value.accept(self) for key, value in o.items}


def _wtype_to_struct_def(typ: pytypes.StructType) -> ARC32StructDef:
    return ARC32StructDef(
        name=typ.name.rsplit(".", maxsplit=1)[-1],
        elements=[(n, pytype_to_arc4(t)) for n, t in typ.fields.items()],
    )


def _get_func_types(
    context: ASTConversionModuleContext, func_def: mypy.nodes.FuncDef, location: SourceLocation
) -> dict[str, pytypes.PyType]:
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

    def require_single_type(arg: pytypes.FuncArg) -> pytypes.PyType:
        try:
            (typ,) = arg.types
        except ValueError:
            raise CodeError(
                "union types are not supported as method arguments", location
            ) from None
        else:
            return typ

    if not (
        func_type.args
        and set(require_single_type(func_type.args[0]).mro).intersection(
            (pytypes.ARC4ContractBaseType, pytypes.ARC4ClientBaseType)
        )
    ):
        raise CodeError(
            f"ARC-4 method decorators can only be applied to"
            f" instance methods of classes derived from {pytypes.ARC4ContractBaseType}",
            location,
        )
    result = {require_arg_name(arg): require_single_type(arg) for arg in func_type.args[1:]}
    if "output" in result:
        # https://github.com/algorandfoundation/ARCs/blob/main/assets/arc-0032/application.schema.json
        raise CodeError(
            "for compatibility with ARC-32, ARC-4 methods cannot have an argument named output",
            location,
        )
    result["output"] = func_type.ret_type
    return result
