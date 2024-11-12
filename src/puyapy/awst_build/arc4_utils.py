import re
import typing
from collections.abc import Callable, Iterable

import attrs
import mypy.nodes
import mypy.types
import mypy.visitor
from immutabledict import immutabledict
from puya import log
from puya.awst import wtypes
from puya.errors import CodeError, InternalError
from puya.models import (
    ARC4ABIMethodConfig,
    ARC4BareMethodConfig,
    ARC4CreateOption,
    ARC4Struct,
    ARC4StructField,
    OnCompletionAction,
    TransactionType,
)
from puya.parse import SourceLocation

from puyapy.awst_build import pytypes
from puyapy.awst_build.context import ASTConversionModuleContext
from puyapy.awst_build.utils import extract_bytes_literal_from_mypy, get_unaliased_fullname
from puyapy.models import ARC4ABIMethodData, ARC4BareMethodData

__all__ = [
    "get_arc4_abimethod_data",
    "get_arc4_baremethod_data",
    "arc4_to_pytype",
    "pytype_to_arc4",
    "pytype_to_arc4_pytype",
]

logger = log.get_logger(__name__)


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
    if not (pytypes.ARC4StructBaseType < typ):
        return False
    if not isinstance(typ, pytypes.StructType):
        raise InternalError(
            f"Type inherits from {pytypes.ARC4StructBaseType!r}"
            f" but structure type is {type(typ).__name__!r}"
        )
    return True


@attrs.frozen
class _DecoratorData:
    fullname: str
    args: list[tuple[str | None, mypy.nodes.Expression]]
    source_location: SourceLocation


def _extract_decorator_args(
    decorator: mypy.nodes.Expression, location: SourceLocation
) -> list[tuple[str | None, mypy.nodes.Expression]]:
    match decorator:
        case mypy.nodes.RefExpr():
            return []
        case mypy.nodes.CallExpr(args=args, arg_names=arg_names):
            return list(zip(arg_names, args, strict=True))
        case unexpected_node:
            raise InternalError(f"unexpected decorator node: {unexpected_node}", location)


def _extract_create_option(
    evaluated_args: dict[str | None, object], location: SourceLocation
) -> ARC4CreateOption:
    default_value = ARC4CreateOption.disallow
    option_name = evaluated_args.pop("create", default_value.name)
    try:
        return ARC4CreateOption[option_name]  # type: ignore[misc]
    except KeyError:
        logger.error(  # noqa: TRY400
            f"invalid create option value: {option_name}", location=location
        )
        return default_value


def _extract_allow_actions_option(
    evaluated_args: dict[str | None, object], location: SourceLocation
) -> list[OnCompletionAction]:
    allowed_completion_types = []
    match evaluated_args.pop("allow_actions", None):
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


def get_arc4_baremethod_data(
    context: ASTConversionModuleContext,
    decorator: mypy.nodes.Expression,
    func_def: mypy.nodes.FuncDef,
) -> ARC4BareMethodData:
    dec_loc = context.node_location(decorator, func_def.info)
    pytype, func_types = _get_func_types(context, func_def, dec_loc)
    if func_types != {"output": pytypes.NoneType}:
        logger.error("bare methods should have no arguments or return values", location=dec_loc)

    visitor = _ARC4DecoratorArgEvaluator(context)
    evaluated_args = {n: a.accept(visitor) for n, a in _extract_decorator_args(decorator, dec_loc)}

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


def get_arc4_abimethod_data(
    context: ASTConversionModuleContext,
    decorator: mypy.nodes.Expression,
    func_def: mypy.nodes.FuncDef,
) -> ARC4ABIMethodData:
    dec_loc = context.node_location(decorator, func_def.info)
    pytype, func_types = _get_func_types(context, func_def, dec_loc)
    visitor = _ARC4DecoratorArgEvaluator(context)
    evaluated_args = {n: a.accept(visitor) for n, a in _extract_decorator_args(decorator, dec_loc)}

    create = _extract_create_option(evaluated_args, dec_loc)
    allowed_completion_types = _extract_allow_actions_option(evaluated_args, dec_loc)
    # map "name" param
    name = func_def.name
    match evaluated_args.pop("name", None):
        case None:
            pass
        case str(name):
            pass
        case invalid_name:
            context.error(f"invalid name option: {invalid_name}", dec_loc)

    # map "readonly" param
    default_readonly = False
    match evaluated_args.pop("readonly", default_readonly):
        case bool(readonly):
            pass
        case invalid_readonly_option:
            context.error(f"invalid readonly option: {invalid_readonly_option}", dec_loc)
            readonly = default_readonly

    # map "default_args" param
    default_args = dict[str, str]()
    match evaluated_args.pop("default_args", {}):
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


class _ARC4DecoratorArgEvaluator(mypy.visitor.NodeVisitor[object]):
    def __init__(self, context: ASTConversionModuleContext):
        self.context = context

    def __getattribute__(self, name: str) -> object:
        attr = super().__getattribute__(name)
        if name.startswith("visit_") and not attr.__module__.startswith("puyapy."):
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
            if unaliased_base_fullname == pytypes.OnCompleteActionType.name:
                try:
                    OnCompletionAction[o.name]
                except KeyError:
                    pass
                else:
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


def _pytype_to_struct_def(typ: pytypes.StructType) -> ARC4Struct:
    return ARC4Struct(
        fullname=typ.name,
        fields=[
            ARC4StructField(
                name=n,
                type=pytype_to_arc4(t),
                struct=t.name if pytypes.ARC4StructBaseType in t.mro else None,
            )
            for n, t in typ.fields.items()
        ],
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


def pytype_to_arc4_pytype(
    pytype: pytypes.PyType,
    on_error: Callable[[pytypes.PyType], pytypes.PyType],
) -> pytypes.PyType:
    match pytype:
        case pytypes.BoolType:
            return pytypes.ARC4BoolType
        case pytypes.NamedTupleType():
            return pytypes.StructType(
                base=pytypes.ARC4StructBaseType,
                desc=pytype.desc,
                name=pytype.name,
                fields={
                    name: pytype_to_arc4_pytype(t, on_error) for name, t in pytype.fields.items()
                },
                frozen=True,
                source_location=pytype.source_location,
            )
        case pytypes.TupleType():
            return pytypes.GenericARC4TupleType.parameterise(
                [pytype_to_arc4_pytype(t, on_error) for t in pytype.items], pytype.source_location
            )
        case pytypes.NoneType | pytypes.GroupTransactionType():
            return pytype

    if pytypes.UInt64Type <= pytype:
        return pytypes.ARC4UIntN_Aliases[64]
    elif pytypes.BigUIntType <= pytype:
        return pytypes.ARC4UIntN_Aliases[512]
    elif pytypes.BytesType <= pytype:
        return pytypes.ARC4DynamicBytesType
    elif pytypes.StringType <= pytype:
        return pytypes.ARC4StringType
    elif pytype.is_type_or_subtype(
        pytypes.ApplicationType, pytypes.AssetType, pytypes.AccountType
    ) or isinstance(pytype.wtype, wtypes.ARC4Type):
        return pytype
    else:
        return on_error(pytype)


_UINT_REGEX = re.compile(r"^uint(?P<n>[0-9]+)$")
_UFIXED_REGEX = re.compile(r"^ufixed(?P<n>[0-9]+)x(?P<m>[0-9]+)$")
_FIXED_ARRAY_REGEX = re.compile(r"^(?P<type>.+)\[(?P<size>[0-9]+)]$")
_DYNAMIC_ARRAY_REGEX = re.compile(r"^(?P<type>.+)\[]$")
_TUPLE_REGEX = re.compile(r"^\((?P<types>.+)\)$")
_ARC4_PYTYPE_MAPPING = {
    "bool": pytypes.ARC4BoolType,
    "string": pytypes.ARC4StringType,
    "account": pytypes.AccountType,
    "application": pytypes.ApplicationType,
    "asset": pytypes.AssetType,
    "void": pytypes.NoneType,
    "txn": pytypes.GroupTransactionTypes[None],
    **{t.name: pytypes.GroupTransactionTypes[t] for t in TransactionType},
    "address": pytypes.ARC4AddressType,
    "byte": pytypes.ARC4ByteType,
    "byte[]": pytypes.ARC4DynamicBytesType,
}


def arc4_to_pytype(typ: str, location: SourceLocation | None = None) -> pytypes.PyType:
    if known_typ := _ARC4_PYTYPE_MAPPING.get(typ):
        return known_typ
    if uint := _UINT_REGEX.match(typ):
        n = int(uint.group("n"))
        n_typ = pytypes.TypingLiteralType(value=n, source_location=None)
        if n <= 64:
            return pytypes.GenericARC4UIntNType.parameterise([n_typ], location)
        else:
            return pytypes.GenericARC4BigUIntNType.parameterise([n_typ], location)
    if ufixed := _UFIXED_REGEX.match(typ):
        n, m = map(int, ufixed.group("n", "m"))
        n_typ = pytypes.TypingLiteralType(value=n, source_location=None)
        m_typ = pytypes.TypingLiteralType(value=m, source_location=None)
        if n <= 64:
            return pytypes.GenericARC4UFixedNxMType.parameterise([n_typ, m_typ], location)
        else:
            return pytypes.GenericARC4BigUFixedNxMType.parameterise([n_typ, m_typ], location)
    if fixed_array := _FIXED_ARRAY_REGEX.match(typ):
        arr_type, size_str = fixed_array.group("type", "size")
        size = int(size_str)
        size_typ = pytypes.TypingLiteralType(value=size, source_location=None)
        element_type = arc4_to_pytype(arr_type, location)
        return pytypes.GenericARC4StaticArrayType.parameterise([element_type, size_typ], location)
    if dynamic_array := _DYNAMIC_ARRAY_REGEX.match(typ):
        arr_type = dynamic_array.group("type")
        element_type = arc4_to_pytype(arr_type, location)
        return pytypes.GenericARC4DynamicArrayType.parameterise([element_type], location)
    if tuple_match := _TUPLE_REGEX.match(typ):
        tuple_types = [
            arc4_to_pytype(x, location) for x in split_tuple_types(tuple_match.group("types"))
        ]
        return pytypes.GenericARC4TupleType.parameterise(tuple_types, location)
    raise CodeError(f"unknown ARC4 type '{typ}'", location)


def pytype_to_arc4(typ: pytypes.PyType, loc: SourceLocation | None = None) -> str:
    def on_error(bad_type: pytypes.PyType) -> typing.Never:
        raise CodeError(
            f"not an ARC4 type or native equivalent: {bad_type}",
            loc or getattr(bad_type, "source_location", None),
        )

    arc4_pytype = pytype_to_arc4_pytype(typ, on_error)
    match arc4_pytype:
        case pytypes.NoneType:
            return "void"
        case pytypes.AssetType:
            return "asset"
        case pytypes.AccountType:
            return "account"
        case pytypes.ApplicationType:
            return "application"
        case pytypes.TransactionRelatedType(transaction_type=transaction_type):
            return transaction_type.name if transaction_type else "txn"
    wtype = arc4_pytype.wtype
    if not isinstance(wtype, wtypes.ARC4Type):
        raise CodeError(f"not an ARC4 type or native equivalent: {wtype}", loc)
    return wtype.arc4_name


def split_tuple_types(types: str) -> Iterable[str]:
    """Splits inner tuple types into individual elements.

    e.g. "uint64,(uint8,string),bool" becomes ["uint64", "(uint8,string)", "bool"]
    """
    tuple_level = 0
    last_idx = 0
    for idx, tok in enumerate(types):
        if tok == "(":
            tuple_level += 1
        elif tok == ")":
            tuple_level -= 1
        if tok == "," and tuple_level == 0:
            yield types[last_idx:idx]
            last_idx = idx + 1
    yield types[last_idx:]
