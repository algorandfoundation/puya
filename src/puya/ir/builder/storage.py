import abc
import typing
from collections.abc import Callable, Sequence
from functools import cached_property

from puya import log
from puya.avm import AVMType
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.errors import InternalError
from puya.ir.arc4 import get_arc4_static_bit_size, is_arc4_static_size
from puya.ir.arc4_types import effective_array_encoding, maybe_wtype_to_arc4_wtype
from puya.ir.avm_ops import AVMOp
from puya.ir.builder import arc4
from puya.ir.builder._tuple_util import build_tuple_registers
from puya.ir.builder._utils import (
    OpFactory,
    assert_value,
    assign_targets,
    new_register_version,
    undefined_value,
)
from puya.ir.context import IRFunctionBuildContext
from puya.ir.models import (
    ConditionalBranch,
    Intrinsic,
    UInt64Constant,
    Value,
    ValueProvider,
    ValueTuple,
)
from puya.ir.types_ import (
    IRType,
    PrimitiveIRType,
    SizedBytesType,
    get_wtype_arity,
    wtype_to_ir_type,
)
from puya.parse import SourceLocation
from puya.utils import bits_to_bytes

logger = log.get_logger(__name__)


def visit_app_state_expression(
    context: IRFunctionBuildContext, expr: awst_nodes.AppStateExpression
) -> ValueProvider:
    key = context.visitor.visit_and_materialise_single(expr.key)
    result = _fetch_and_decode_from_storage_with_assert(
        context,
        expr,
        key,
        default_error_message="state exists",
    )
    return result


def visit_app_account_state_expression(
    context: IRFunctionBuildContext, expr: awst_nodes.AppAccountStateExpression
) -> ValueProvider:
    key = context.visitor.visit_and_materialise_single(expr.key)
    result = _fetch_and_decode_from_storage_with_assert(
        context,
        expr,
        key,
        default_error_message="state exists for account",
    )
    return result


def visit_box_value(
    context: IRFunctionBuildContext, expr: awst_nodes.BoxValueExpression
) -> ValueProvider:
    key = context.visitor.visit_and_materialise_single(expr.key)
    result = _fetch_and_decode_from_storage_with_assert(
        context,
        expr,
        key,
        default_error_message="box exists",
    )
    return result


def _fetch_and_decode_from_storage_with_assert(
    context: IRFunctionBuildContext,
    expr: awst_nodes.StorageExpression,
    key: Value,
    *,
    default_error_message: str,
) -> ValueProvider:
    storage_codec = _get_storage_codec_for_node(expr)
    get_ex_op = _build_get_ex_op(context, storage_codec.encoded_avm_type, expr, key)
    storage_value, did_exist = context.visitor.materialise_value_provider(
        get_ex_op, ("maybe_value", "maybe_exists")
    )
    assert_value(
        context,
        value=did_exist,
        error_message=expr.exists_assertion_message or default_error_message,
        source_location=expr.source_location,
    )
    decoded_value = storage_codec.decode(context, storage_value, expr.source_location)
    return decoded_value


class _GetExResult(typing.NamedTuple):
    encoded_value: Value
    did_exist: Value


def _build_get_ex_op(
    context: IRFunctionBuildContext,
    encoded_avm_type: typing.Literal[AVMType.uint64, AVMType.bytes],
    expr: awst_nodes.StorageExpression,
    key: Value,
) -> ValueProvider:
    # note: result_type is intentionally using PrimitiveIRType rather than
    # the IRType of the storage expression. As it is not safe to assume what is in storage
    # is actually the type described by the expression, for example the box may have been
    # created larger than the static type implies
    match encoded_avm_type:
        case AVMType.uint64:
            result_type = PrimitiveIRType.uint64
        case AVMType.bytes:
            result_type = PrimitiveIRType.bytes
        case unexpected:
            typing.assert_never(unexpected)

    if isinstance(expr, awst_nodes.AppStateExpression):
        current_app_offset = UInt64Constant(value=0, source_location=expr.source_location)
        get_storage_value = Intrinsic(
            op=AVMOp.app_global_get_ex,
            args=[current_app_offset, key],
            types=[result_type, PrimitiveIRType.bool],
            source_location=expr.source_location,
        )
    elif isinstance(expr, awst_nodes.AppAccountStateExpression):
        current_app_offset = UInt64Constant(value=0, source_location=expr.source_location)
        account = context.visitor.visit_and_materialise_single(expr.account)
        get_storage_value = Intrinsic(
            op=AVMOp.app_local_get_ex,
            args=[account, current_app_offset, key],
            types=[result_type, PrimitiveIRType.bool],
            source_location=expr.source_location,
        )
    else:
        typing.assert_type(expr, awst_nodes.BoxValueExpression)
        get_storage_value = Intrinsic(
            op=AVMOp.box_get,
            args=[key],
            # specifying types should be redundant, but this acts as an internal consistency check
            types=[result_type, PrimitiveIRType.bool],
            source_location=expr.source_location,
        )
    return get_storage_value


def visit_state_exists(
    context: IRFunctionBuildContext, field: awst_nodes.StorageExpression, loc: SourceLocation
) -> ValueProvider:
    key = context.visitor.visit_and_materialise_single(field.key)
    result_type = _get_storage_codec_for_node(field).encoded_ir_type
    if isinstance(field, awst_nodes.AppStateExpression):
        op = AVMOp.app_global_get_ex
        args = [UInt64Constant(value=0, source_location=loc), key]
    elif isinstance(field, awst_nodes.AppAccountStateExpression):
        op = AVMOp.app_local_get_ex
        account = context.visitor.visit_and_materialise_single(field.account)
        args = [account, UInt64Constant(value=0, source_location=loc), key]
    else:
        typing.assert_type(field, awst_nodes.BoxValueExpression)
        # use box_len for existence check, in case len(value) is > 4096
        result_type = PrimitiveIRType.uint64
        op = AVMOp.box_len
        args = [key]

    ir_types = [result_type, PrimitiveIRType.bool]
    get_ex = Intrinsic(op=op, args=args, types=ir_types, source_location=loc)
    _, maybe_exists = context.visitor.materialise_value_provider(get_ex, ("_", "maybe_exists"))
    return maybe_exists


def visit_state_get(context: IRFunctionBuildContext, expr: awst_nodes.StateGet) -> ValueProvider:
    # ensure we materialize key before default value
    key = context.visitor.visit_and_materialise_single(expr.field.key)
    storage_codec = _get_storage_codec_for_node(expr.field)
    get_ex_op = _build_get_ex_op(context, storage_codec.encoded_avm_type, expr.field, key)
    # default should always be materialized, and should be after account for local-state,
    # but before the result is materialized
    default_decoded_values = context.visitor.visit_and_materialise(expr.default)
    assert default_decoded_values, "void type should not be storable"
    storage_value, did_exist = context.visitor.materialise_value_provider(
        get_ex_op, ("maybe_value", "maybe_exists")
    )
    if len(default_decoded_values) == 1:
        decoded_maybe_vp = storage_codec.decode(context, storage_value, expr.source_location)
        (decoded_maybe_value,) = context.visitor.materialise_value_provider(
            decoded_maybe_vp, "decoded_value"
        )
        (default_decoded_value,) = default_decoded_values
        factory = OpFactory(context, expr.source_location)
        return factory.select(
            condition=did_exist,
            true=decoded_maybe_value,
            false=default_decoded_value,
            temp_desc="state_get",
            ir_type=decoded_maybe_value.ir_type,
        )
    else:
        default_decoded_vp = ValueTuple(
            values=default_decoded_values, source_location=expr.default.source_location
        )
        return _conditional_value_provider(
            context,
            condition=did_exist,
            wtype=expr.field.wtype,
            true_factory=lambda: storage_codec.decode(
                context, storage_value, expr.source_location
            ),
            false_factory=lambda: default_decoded_vp,
            loc=expr.source_location,
        )


def visit_state_get_ex(
    context: IRFunctionBuildContext, expr: awst_nodes.StateGetEx
) -> ValueProvider:
    key = context.visitor.visit_and_materialise_single(expr.field.key)
    storage_codec = _get_storage_codec_for_node(expr.field)
    get_ex_op = _build_get_ex_op(context, storage_codec.encoded_avm_type, expr.field, key)
    storage_value, did_exist = context.visitor.materialise_value_provider(
        get_ex_op, ("maybe_value", "maybe_exists")
    )
    if get_wtype_arity(expr.field.wtype) == 1:
        decoded_vp = storage_codec.decode(context, storage_value, expr.source_location)
    else:
        default_decoded = undefined_value(expr.field.wtype, expr.source_location)
        decoded_vp = _conditional_value_provider(
            context,
            condition=did_exist,
            wtype=expr.field.wtype,
            true_factory=lambda: storage_codec.decode(
                context, storage_value, expr.source_location
            ),
            false_factory=lambda: default_decoded,
            loc=expr.source_location,
        )

    maybe_values = context.visitor.materialise_value_provider(decoded_vp, "maybe_value")
    return ValueTuple(
        values=[*maybe_values, did_exist],
        source_location=expr.source_location,
    )


def _conditional_value_provider(
    context: IRFunctionBuildContext,
    *,
    condition: Value,
    wtype: wtypes.WType,
    true_factory: Callable[[], ValueProvider],
    false_factory: Callable[[], ValueProvider],
    loc: SourceLocation,
) -> ValueProvider:
    """
    Builds a conditional that returns one of two ValueProviders

    true and false values are provided via factories so IR construction emits them at the correct
    time
    """
    true_block, false_block, merge_block = context.block_builder.mkblocks(
        "ternary_true", "ternary_false", "ternary_merge", source_location=loc
    )
    context.block_builder.terminate(
        ConditionalBranch(
            condition=condition,
            non_zero=true_block,
            zero=false_block,
            source_location=loc,
        )
    )
    tmp_var_name = context.next_tmp_name("ternary_result")
    true_registers = build_tuple_registers(context, tmp_var_name, wtype, loc)
    context.block_builder.activate_block(true_block)
    true = true_factory()
    assign_targets(
        context,
        source=true,
        targets=true_registers,
        assignment_location=true.source_location,
    )
    context.block_builder.goto(merge_block)

    context.block_builder.activate_block(false_block)
    false = false_factory()
    assign_targets(
        context,
        source=false,
        targets=[new_register_version(context, reg) for reg in true_registers],
        assignment_location=false.source_location,
    )
    context.block_builder.goto(merge_block)

    context.block_builder.activate_block(merge_block)
    result = [
        context.ssa.read_variable(variable=r.name, ir_type=r.ir_type, block=merge_block)
        for r in true_registers
    ]
    return ValueTuple(values=result, source_location=loc)


def visit_state_delete(
    context: IRFunctionBuildContext, statement: awst_nodes.StateDelete
) -> ValueProvider | None:
    match statement:
        case awst_nodes.StateDelete(
            field=awst_nodes.BoxValueExpression(key=awst_key),
            wtype=wtypes.bool_wtype
            | wtypes.void_wtype,
        ):
            op = AVMOp.box_del
            awst_account = None
        case awst_nodes.StateDelete(
            field=awst_nodes.AppStateExpression(key=awst_key), wtype=wtypes.void_wtype
        ):
            op = AVMOp.app_global_del
            awst_account = None
        case awst_nodes.StateDelete(
            field=awst_nodes.AppAccountStateExpression(key=awst_key, account=awst_account),
            wtype=wtypes.void_wtype,
        ):
            op = AVMOp.app_local_del
        case awst_nodes.StateDelete():
            raise ValueError(
                f"Unexpected StateDelete field type: {statement.field}, wtype: {statement.wtype}"
            )
        case _:
            typing.assert_never(statement)

    args = []
    if awst_account is not None:
        account_value = context.visitor.visit_and_materialise_single(awst_account)
        args.append(account_value)
    key_value = context.visitor.visit_and_materialise_single(awst_key)
    args.append(key_value)

    state_delete = Intrinsic(op=op, args=args, source_location=statement.source_location)
    if statement.wtype == wtypes.bool_wtype:
        return state_delete

    context.block_builder.add(state_delete)
    return None


class StorageCodec(abc.ABC):
    @abc.abstractmethod
    def encode(
        self, context: IRFunctionBuildContext, values: Sequence[Value], loc: SourceLocation
    ) -> Value: ...

    @abc.abstractmethod
    def decode(
        self, context: IRFunctionBuildContext, value: Value, loc: SourceLocation
    ) -> ValueProvider: ...

    @property
    @abc.abstractmethod
    def encoded_ir_type(self) -> IRType: ...

    @property
    def encoded_avm_type(self) -> typing.Literal[AVMType.uint64, AVMType.bytes]:
        storage_type = self.encoded_ir_type.avm_type
        assert (
            storage_type is not AVMType.any
        ), "storage encoding should not have AVM type of 'any'"
        return storage_type


def _get_storage_codec_for_node(node: awst_nodes.StorageExpression) -> StorageCodec:
    return get_storage_codec(node.wtype, node.storage_kind, node.source_location)


def get_storage_codec(
    declared_type: wtypes.WType, storage_kind: awst_nodes.AppStorageKind, loc: SourceLocation
) -> StorageCodec:
    if not declared_type.persistable:
        raise InternalError(f"non-persistable storage type: {declared_type!r}", loc)

    if (
        declared_type.scalar_type is AVMType.uint64
        and storage_kind is awst_nodes.AppStorageKind.box
    ):
        return _UInt64AsBytesStorageCodec()

    if isinstance(declared_type, wtypes.StackArray):
        # this case could just be handled by `.scalar_type` case,
        # but by adding this type here we encode the pass-through assumption
        effective_type = effective_array_encoding(declared_type, loc)
        typing.assert_type(effective_type, wtypes.ARC4DynamicArray)
        ir_type = wtype_to_ir_type(declared_type, loc)
        return _PassthroughStorageCodec(ir_type)

    if isinstance(declared_type, wtypes.WTuple):
        arc4_wtype = maybe_wtype_to_arc4_wtype(declared_type)
        if arc4_wtype is None:
            raise InternalError("expected persistable tuple type to be ARC-4 encodable", loc)
        return _ARC4StorageCodec(declared_type=declared_type, arc4_type=arc4_wtype)

    if declared_type.scalar_type is None:
        raise InternalError(f"unable to construct storage codec for type: {declared_type!r}", loc)
    ir_type = wtype_to_ir_type(declared_type, loc)
    return _PassthroughStorageCodec(ir_type)


class _UInt64AsBytesStorageCodec(StorageCodec):
    @typing.override
    def encode(
        self, context: IRFunctionBuildContext, values: Sequence[Value], loc: SourceLocation
    ) -> Value:
        assert len(values) == 1, f"{type(self).__name__}.encode(..) expects single value"
        (value,) = values
        factory = OpFactory(context, loc)
        return factory.itob(value=value, temp_desc="encoded_value")

    @typing.override
    def decode(
        self, context: IRFunctionBuildContext, value: Value, loc: SourceLocation
    ) -> ValueProvider:
        factory = OpFactory(context, loc)
        return factory.btoi(value=value, temp_desc="maybe_value_converted")

    @property
    @typing.override
    def encoded_ir_type(self) -> IRType:
        return SizedBytesType(num_bytes=8)


class _PassthroughStorageCodec(StorageCodec):
    def __init__(self, encoded_ir_type: IRType) -> None:
        self._encoded_ir_type = encoded_ir_type

    @typing.override
    def encode(
        self, context: IRFunctionBuildContext, values: Sequence[Value], loc: SourceLocation
    ) -> Value:
        assert len(values) == 1, f"{type(self).__name__}.encode(..) expects single value"
        (value,) = values
        return value

    @typing.override
    def decode(
        self, context: IRFunctionBuildContext, value: Value, loc: SourceLocation
    ) -> ValueProvider:
        return value

    @property
    @typing.override
    def encoded_ir_type(self) -> IRType:
        return self._encoded_ir_type


class _ARC4StorageCodec(StorageCodec):
    """For when user / high-level types must be converted to ARC-4 for storage"""

    def __init__(self, *, declared_type: wtypes.WType, arc4_type: wtypes.ARC4Type) -> None:
        self._declared_type = declared_type
        self._arc4_type = arc4_type

    @typing.override
    def encode(
        self, context: IRFunctionBuildContext, values: Sequence[Value], loc: SourceLocation
    ) -> Value:
        value_tuple = ValueTuple(values=values, source_location=loc)
        encoded_vp = arc4.encode_value_provider(
            context, value_tuple, self._declared_type, arc4_wtype=self._arc4_type, loc=loc
        )
        encoded, *rest = context.visitor.materialise_value_provider(
            encoded_vp, "encoded_for_storage"
        )
        assert not rest, "encoded result should be a single stack value"
        return encoded

    @typing.override
    def decode(
        self, context: IRFunctionBuildContext, value: Value, loc: SourceLocation
    ) -> ValueProvider:
        return arc4.decode_arc4_value(context, value, self._arc4_type, self._declared_type, loc)

    @cached_property
    @typing.override
    def encoded_ir_type(self) -> IRType:
        if is_arc4_static_size(self._arc4_type):
            num_bits = get_arc4_static_bit_size(self._arc4_type)
            return SizedBytesType(bits_to_bytes(num_bits))
        return PrimitiveIRType.bytes
