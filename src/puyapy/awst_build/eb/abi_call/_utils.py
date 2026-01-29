import typing
from collections.abc import Callable, Mapping, Sequence, Set
from itertools import zip_longest

import attrs

from puya import log
from puya.algo_constants import MAX_UINT64
from puya.avm import OnCompletionAction
from puya.awst.nodes import (
    ARC4MethodConfig,
    Expression,
    IntegerConstant,
    MethodSignature,
    MethodSignatureString,
    UInt64Constant,
)
from puya.awst.txn_fields import TxnField
from puya.errors import CodeError
from puya.parse import SourceLocation
from puya.utils import StableSet
from puyapy import models
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb.arc4_client import ARC4ClientMethodExpressionBuilder
from puyapy.awst_build.eb.interface import (
    InstanceBuilder,
    LiteralBuilder,
    NodeBuilder,
)
from puyapy.awst_build.eb.subroutine import BaseClassSubroutineInvokerExpressionBuilder
from puyapy.awst_build.eb.transaction.itxn_args import PYTHON_ITXN_ARGUMENTS
from puyapy.awst_build.eb.tuple import TupleLiteralBuilder
from puyapy.awst_build.eb.uint64 import UInt64ExpressionBuilder
from puyapy.awst_build.utils import maybe_resolve_literal as base_maybe_resolve_literal

logger = log.get_logger(__name__)

FIELD_TO_ITXN_ARGUMENT = {arg.field: arg for arg in PYTHON_ITXN_ARGUMENTS.values()}


def get_method_abi_args_and_kwargs(
    args: Sequence[NodeBuilder], arg_names: list[str | None], allowed_kwargs: Set[str]
) -> tuple[NodeBuilder | None, Sequence[NodeBuilder], dict[str, NodeBuilder]]:
    method: NodeBuilder | None = None
    abi_args = list[NodeBuilder]()
    kwargs = dict[str, NodeBuilder]()
    for idx, (arg_name, arg) in enumerate(zip(arg_names, args, strict=True)):
        if arg_name is None:
            if idx == 0:
                method = arg
            else:
                abi_args.append(arg)
        elif arg_name in allowed_kwargs:
            kwargs[arg_name] = arg
        else:
            logger.error("unrecognised keyword argument", location=arg.source_location)
    return method, abi_args, kwargs


def get_python_kwargs(fields: Sequence[TxnField]) -> Set[str]:
    return StableSet.from_iter(
        arg for arg, param in PYTHON_ITXN_ARGUMENTS.items() if param.field in fields
    )


def maybe_resolve_literal(
    operand: InstanceBuilder,
    *,
    expected_type: pytypes.PyType | None = None,
    allow_literal: bool = True,
) -> InstanceBuilder:
    if isinstance(operand, TupleLiteralBuilder):
        item_types = list[pytypes.PyType]()
        if expected_type is not None and isinstance(expected_type, pytypes.TupleType):
            item_types.extend(expected_type.items)
        resolved_items = [
            maybe_resolve_literal(elem, expected_type=item_type, allow_literal=allow_literal)
            for elem, item_type in zip_longest(operand.iterate_static(), item_types)
        ]
        return TupleLiteralBuilder(resolved_items, operand.source_location)

    if expected_type is None:
        match operand.pytype:
            case pytypes.StrLiteralType:
                typ: pytypes.PyType = pytypes.StringType
            case pytypes.BytesLiteralType:
                typ = pytypes.BytesType
            case pytypes.IntLiteralType:
                if (
                    (isinstance(operand, LiteralBuilder))
                    and isinstance(operand.value, int)
                    and operand.value > MAX_UINT64
                ):
                    typ = pytypes.BigUIntType
                else:
                    typ = pytypes.UInt64Type
            case pytypes.GroupTransactionType() | pytypes.InnerTransactionResultType():
                raise CodeError(
                    f"cannot use {operand.pytype} as an argument to an ARC-4 method",
                    location=operand.source_location,
                )
            case _:
                typ = operand.pytype
        if (typ != operand.pytype) and not allow_literal:
            logger.warning(
                "type information should be provided when passing a literal value",
                location=operand.source_location,
            )
    else:
        typ = expected_type

    return base_maybe_resolve_literal(operand, typ)


def is_creating(field_nodes: Mapping[TxnField, NodeBuilder]) -> bool | None:
    """
    Returns app_id == 0 if app_id is statically known, otherwise returns None
    """
    match field_nodes.get(TxnField.ApplicationID):
        case None:
            return True
        case LiteralBuilder(value=int(app_id)):
            return app_id == 0
    return None


def get_on_completion(
    field_nodes: Mapping[TxnField, NodeBuilder], arc4_config: ARC4MethodConfig | None = None
) -> OnCompletionAction | None:
    """
    Returns OnCompletionAction if it is statically known, otherwise returns None
    """
    match field_nodes.get(TxnField.OnCompletion):
        case None:
            if arc4_config:
                return arc4_config.allowed_completion_types[0]
            return OnCompletionAction.NoOp
        case InstanceBuilder(pytype=pytypes.OnCompleteActionType) as eb:
            value = eb.resolve()
            if isinstance(value, IntegerConstant):
                return OnCompletionAction(value.value)
    return None


def get_singular_on_complete(config: ARC4MethodConfig | None) -> OnCompletionAction | None:
    if config:
        try:
            (on_complete,) = config.allowed_completion_types
        except ValueError:
            pass
        else:
            return on_complete
    return None


def add_on_completion(
    field_nodes: dict[TxnField, NodeBuilder],
    on_complete: OnCompletionAction,
    location: SourceLocation,
) -> None:
    # if NoOp can just omit
    if on_complete == OnCompletionAction.NoOp:
        return
    field_nodes[TxnField.OnCompletion] = UInt64ExpressionBuilder(
        UInt64Constant(
            source_location=location, value=on_complete.value, teal_alias=on_complete.name
        ),
        enum_type=pytypes.OnCompleteActionType,
    )


@attrs.frozen
class ParsedMethod:
    target: MethodSignature | MethodSignatureString | None
    arg_types: Sequence[pytypes.PyType]
    return_type: pytypes.PyType
    declared_return_type: pytypes.PyType | None
    abi_config: ARC4MethodConfig | None
    allow_literal_args: bool


def parse_method(
    method: NodeBuilder | None,
    location: SourceLocation,
    *,
    return_type_annotation: pytypes.PyType | None,
) -> ParsedMethod:
    """
    parse method argument to a MethodSignature and associated type information.

    Handles both ARC4 method references (from client or base class) and string signatures.
    """

    match method:
        case None:
            raise CodeError("missing required positional argument 'method'", location)
        case (
            ARC4ClientMethodExpressionBuilder(method=fmethod)
            | BaseClassSubroutineInvokerExpressionBuilder(method=fmethod)
        ):
            return parse_contract_fragment_method(
                fmethod, return_type_annotation, method.source_location
            )
        case _:
            return parse_signature_string(method, return_type_annotation)


@attrs.frozen
class ParsedABICallArgs:
    """Result of parsing ABI call arguments."""

    target: MethodSignature | MethodSignatureString | None
    abi_call_args: Sequence[Expression]
    return_type: pytypes.PyType
    declared_return_type: pytypes.PyType
    fields: dict[TxnField, Expression]


def parse_abi_call_args(
    args: Sequence[NodeBuilder],
    arg_names: list[str | None],
    allowed_fields: Sequence[TxnField],
    return_type_annotation: pytypes.PyType | None,
    validate_transaction_kwargs: Callable[
        [
            dict[TxnField, NodeBuilder],
            ARC4MethodConfig | None,
            SourceLocation | None,
            SourceLocation,
        ],
        None,
    ],
    location: SourceLocation,
) -> ParsedABICallArgs:
    """
    Parse and validate ABI call arguments.

    This function handles common logic for both arc4.abi_call and itxn.abi_call:
    - Validates the return type annotation
    - Parses args into method, positional args, and kwargs
    - Resolves the method signature
    - Builds field nodes and converts them to expressions
    - Adds on_completion if inferrable from method config
    """
    if return_type_annotation == pytypes.NeverType:
        raise CodeError(
            f"invalid return type for an ARC-4 method: {return_type_annotation}",
            location=location,
        )

    method, pos_args, kwargs = get_method_abi_args_and_kwargs(
        args, arg_names, get_python_kwargs(allowed_fields)
    )

    abi_args = [expect.instance_builder(arg, default=expect.default_raise) for arg in pos_args]

    parsed_method = parse_method(method, location, return_type_annotation=return_type_annotation)

    field_nodes = {PYTHON_ITXN_ARGUMENTS[kwarg].field: node for kwarg, node in kwargs.items()}
    # set on_completion if it can be inferred from config
    if (
        TxnField.OnCompletion not in field_nodes
        and (on_completion := get_singular_on_complete(parsed_method.abi_config)) is not None
    ):
        add_on_completion(field_nodes, on_completion, location)

    fields = dict[TxnField, Expression]()
    for field, field_node in field_nodes.items():
        params = FIELD_TO_ITXN_ARGUMENT[field]
        fields[field] = params.validate_and_convert(field_node).resolve()

    declared_return_type = parsed_method.declared_return_type
    if declared_return_type is None:
        declared_return_type = parsed_method.return_type or pytypes.NoneType

    abi_call_args = [
        maybe_resolve_literal(
            arg, expected_type=arg_type, allow_literal=parsed_method.allow_literal_args
        ).resolve()
        for arg, arg_type in zip_longest(abi_args, parsed_method.arg_types)
    ]
    if parsed_method.target:
        method_location: SourceLocation | None = parsed_method.target.source_location
    else:
        method_location = None

    validate_transaction_kwargs(
        field_nodes,
        parsed_method.abi_config,
        method_location,
        location,
    )

    return ParsedABICallArgs(
        target=parsed_method.target,
        abi_call_args=abi_call_args,
        return_type=parsed_method.return_type,
        declared_return_type=declared_return_type,
        fields=fields,
    )


def parse_contract_fragment_method(
    fmethod: models.ContractFragmentMethod,
    return_type_annotation: pytypes.PyType | None,
    location: SourceLocation,
) -> ParsedMethod:
    if fmethod.metadata is None:
        raise CodeError("method is not an ARC-4 method", location=location)

    abi_method_data = fmethod.metadata
    abi_config = abi_method_data.config
    if isinstance(abi_method_data, models.ARC4ABIMethodData):
        name = abi_method_data.config.name
        arg_types = list(abi_method_data.argument_types)
        return_type = abi_method_data.return_type
        resource_encoding = abi_method_data.config.resource_encoding
    else:
        name = fmethod.member_name
        arg_types = []
        return_type = pytypes.NoneType
        resource_encoding = "value"

    target = MethodSignature(
        name=name,
        arg_types=[t.checked_wtype(location) for t in arg_types],
        return_type=return_type.checked_wtype(location),
        resource_encoding=resource_encoding,
        source_location=location,
    )

    if return_type_annotation == pytypes.NoneType:
        return_type_annotation = return_type

    return ParsedMethod(
        target=target,
        arg_types=arg_types,
        return_type=return_type,
        declared_return_type=return_type_annotation,
        abi_config=abi_config,
        allow_literal_args=True,
    )


def parse_signature_string(
    method: NodeBuilder,
    return_type_annotation: pytypes.PyType | None,
) -> ParsedMethod:
    method_str = expect.simple_string_literal(method, default=expect.default_raise)
    target = MethodSignatureString(value=method_str, source_location=method.source_location)
    allow_literal_args = "(" in method_str

    return ParsedMethod(
        target=target,
        arg_types=[],
        return_type=return_type_annotation or pytypes.NoneType,
        declared_return_type=return_type_annotation,
        abi_config=None,
        allow_literal_args=allow_literal_args,
    )


def parse_abi_method_data(data: models.ARC4MethodData, location: SourceLocation) -> ParsedMethod:
    match data:
        case models.ARC4ABIMethodData() as abi_method_data:
            name = abi_method_data.config.name
            arg_types = list(abi_method_data.argument_types)
            return_type = abi_method_data.return_type
            resource_encoding = abi_method_data.config.resource_encoding
            config: ARC4MethodConfig = abi_method_data.config
            target: MethodSignature | None = MethodSignature(
                name=name,
                arg_types=[t.checked_wtype(location) for t in arg_types],
                return_type=return_type.checked_wtype(location),
                source_location=location,
                resource_encoding=resource_encoding,
            )
        case models.ARC4BareMethodData() as bare_method_data:
            target = None
            arg_types = []
            return_type = pytypes.NoneType
            config = bare_method_data.config

        case other:
            typing.assert_never(other)

    return ParsedMethod(
        target=target,
        arg_types=arg_types,
        return_type=return_type,
        declared_return_type=pytypes.NoneType,
        abi_config=config,
        allow_literal_args=True,
    )
