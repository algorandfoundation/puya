import typing
from collections.abc import Sequence

import attrs
import mypy.nodes
import mypy.types
import mypy.visitor
from immutabledict import immutabledict

import puya.models
from puya.arc4_util import pytype_to_arc4
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.awst_build import constants, intrinsic_factory, pytypes
from puya.awst_build.context import ASTConversionModuleContext
from puya.awst_build.utils import extract_bytes_literal_from_mypy, get_unaliased_fullname
from puya.errors import CodeError, InternalError
from puya.models import ARC4MethodConfig, ARC32StructDef, OnCompletionAction
from puya.parse import SourceLocation

ALLOWABLE_OCA = [oca.name for oca in OnCompletionAction if oca != OnCompletionAction.ClearState]


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
    match decorator:
        case mypy.nodes.RefExpr(fullname=fullname):
            config = ARC4MethodConfig(
                name=func_def.name,
                source_location=dec_loc,
                is_bare=fullname == constants.BAREMETHOD_DECORATOR,
            )
        case mypy.nodes.CallExpr(
            args=args,
            arg_names=arg_names,
            callee=mypy.nodes.RefExpr(fullname=fullname),
        ):
            visitor = _ARC4DecoratorArgEvaluator(context)
            abi_hints = typing.cast(
                _AbiHints,
                {n: a.accept(visitor) for n, a in zip(filter(None, arg_names), args, strict=True)},
            )
            name = abi_hints.get("name", func_def.name)
            allow_actions = abi_hints.get("allow_actions", ["NoOp"])
            if len(set(allow_actions)) != len(allow_actions):
                context.error("Cannot have duplicate allow_actions", dec_loc)
            if not allow_actions:
                context.error("Must have at least one allow_actions", dec_loc)
            invalid_actions = [a for a in allow_actions if a not in ALLOWABLE_OCA]
            if invalid_actions:
                context.error(
                    f"Invalid allowed actions: {invalid_actions}",
                    dec_loc,
                )
            create = abi_hints.get("create", "disallow")
            readonly = abi_hints.get("readonly", False)
            default_args = immutabledict[str, str](abi_hints.get("default_args", {}))
            all_args = [
                a.variable.name for a in (func_def.arguments or []) if not a.variable.is_self
            ]
            for parameter in default_args:
                if parameter not in all_args:
                    context.error(
                        f"'{parameter}' is not a parameter of {func_def.fullname}", dec_loc
                    )

            structs = immutabledict[str, ARC32StructDef](
                {
                    n: _wtype_to_struct_def(pt)
                    for n, pt in func_types.items()
                    if _is_arc4_struct(pt)
                }
            )

            config = ARC4MethodConfig(
                source_location=dec_loc,
                name=name,
                allowed_completion_types=[
                    puya.models.OnCompletionAction[a] for a in allow_actions
                ],
                allow_create=create == "allow",
                require_create=create == "require",
                readonly=readonly,
                is_bare=fullname == constants.BAREMETHOD_DECORATOR,
                default_args=default_args,
                structs=structs,
            )
        case _:
            raise InternalError("Unexpected ARC4 decorator", dec_loc)
    return ARC4MethodData(config=config, signature=func_types)


class _AbiHints(typing.TypedDict, total=False):
    name: str
    allow_actions: list[str]
    create: typing.Literal["allow", "require", "disallow"]
    readonly: bool
    default_args: dict[str, str]


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


def arc4_encode(
    base: awst_nodes.Expression, target_wtype: wtypes.ARC4Type, location: SourceLocation
) -> awst_nodes.Expression:
    match base.wtype:
        case wtypes.bytes_wtype:
            base_temp = awst_nodes.SingleEvaluation(base)

            length = awst_nodes.IntrinsicCall(
                source_location=location,
                op_code="substring",
                immediates=[6, 8],
                wtype=wtypes.bytes_wtype,
                stack_args=[
                    intrinsic_factory.itob(intrinsic_factory.bytes_len(base_temp, loc=location))
                ],
            )
            return awst_nodes.ReinterpretCast(
                source_location=location,
                wtype=wtypes.arc4_dynamic_bytes,
                expr=intrinsic_factory.concat(length, base_temp, location),
            )
        case wtypes.WTuple(types=types):
            base_temp = awst_nodes.SingleEvaluation(base)

            return awst_nodes.ARC4Encode(
                source_location=location,
                value=awst_nodes.TupleExpression.from_items(
                    items=[
                        maybe_arc4_encode(
                            awst_nodes.TupleItemExpression(
                                base=base_temp,
                                index=i,
                                source_location=location,
                            ),
                            t,
                            location,
                        )
                        for i, t in enumerate(types)
                    ],
                    location=location,
                ),
                wtype=target_wtype,
            )

        case _:
            return awst_nodes.ARC4Encode(
                source_location=location,
                value=base,
                wtype=target_wtype,
            )


def maybe_arc4_encode(
    item: awst_nodes.Expression, wtype: wtypes.WType, location: SourceLocation
) -> awst_nodes.Expression:
    """Encode as arc4 if wtype is not already an arc4 encoded type"""
    if wtypes.is_arc4_encoded_type(wtype):
        return item
    return arc4_encode(
        item,
        wtypes.avm_to_arc4_equivalent_type(wtype),
        location,
    )


def maybe_arc4_decode(
    item: awst_nodes.Expression,
    *,
    current_wtype: wtypes.WType,
    target_wtype: wtypes.WType,
    location: SourceLocation,
) -> awst_nodes.Expression:
    if current_wtype == target_wtype:
        return item
    assert target_wtype == wtypes.arc4_to_avm_equivalent_wtype(
        current_wtype,
        location,
    ), "target type must be avm equivalent of current type"
    return arc4_decode(
        item,
        target_wtype,
        location,
    )


def arc4_decode(
    bytes_arg: awst_nodes.Expression,
    target_wtype: wtypes.WType,
    location: SourceLocation,
) -> awst_nodes.Expression:
    match bytes_arg.wtype:
        case wtypes.ARC4DynamicArray(
            element_type=wtypes.ARC4UIntN(n=8)
        ) if target_wtype == wtypes.bytes_wtype:
            return intrinsic_factory.extract(bytes_arg, start=2, loc=location)
        case wtypes.ARC4Tuple(types=tuple_types):
            decode_expression = awst_nodes.ARC4Decode(
                source_location=location,
                wtype=wtypes.WTuple(tuple_types, location),
                value=bytes_arg,
            )
            assert isinstance(
                target_wtype, wtypes.WTuple
            ), "Target wtype must be a WTuple when decoding ARC4Tuple"
            if all(
                target == current
                for target, current in zip(target_wtype.types, tuple_types, strict=True)
            ):
                return decode_expression
            decoded = awst_nodes.SingleEvaluation(decode_expression)
            return awst_nodes.TupleExpression.from_items(
                items=[
                    maybe_arc4_decode(
                        awst_nodes.TupleItemExpression(
                            base=decoded,
                            index=i,
                            source_location=location,
                        ),
                        target_wtype=t_t,
                        current_wtype=t_c,
                        location=location,
                    )
                    for i, (t_c, t_t) in enumerate(
                        zip(tuple_types, target_wtype.types, strict=True)
                    )
                ],
                location=location,
            )

        case _:
            return awst_nodes.ARC4Decode(
                source_location=location,
                wtype=target_wtype,
                value=bytes_arg,
            )


def _get_func_types(
    context: ASTConversionModuleContext, func_def: mypy.nodes.FuncDef, location: SourceLocation
) -> dict[str, pytypes.PyType]:
    if not (func_def.arguments and func_def.arguments[0].variable.is_self):
        raise InternalError(
            "arc4_utils.get_func_types called with non class method,"
            " which means it can't be an ABI method",
            location,
        )
    func_type = func_def.type
    if not isinstance(func_type, mypy.types.CallableType):
        raise InternalError(f"Unexpected FuncDef type: {type(func_def.type).__name__}", location)
    if "output" in (arg.variable.name for arg in func_def.arguments):
        # https://github.com/algorandfoundation/ARCs/blob/main/assets/arc-0032/application.schema.json
        raise CodeError(
            "For compatibility with ARC-32, ARC-4 methods cannot have an argument named output",
            location,
        )
    return {
        **{
            arg.variable.name: context.type_to_pytype(
                t, source_location=context.node_location(arg, module_src=func_def.info)
            )
            for t, arg in zip(func_type.arg_types, func_def.arguments, strict=True)
            if not arg.variable.is_self
        },
        "output": context.type_to_pytype(func_type.ret_type, source_location=location),
    }
