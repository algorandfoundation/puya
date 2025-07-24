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
from puya.ir import (
    models as ir,
    types_ as types,
)
from puya.ir.arc4_types import maybe_wtype_to_arc4_wtype
from puya.ir.avm_ops import AVMOp
from puya.ir.builder._utils import assign_tuple, undefined_value
from puya.ir.context import IRFunctionBuildContext
from puya.ir.op_utils import OpFactory, assert_value
from puya.parse import SourceLocation

logger = log.get_logger(__name__)


def visit_app_state_expression(
    context: IRFunctionBuildContext, expr: awst_nodes.AppStateExpression
) -> ir.ValueProvider:
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
) -> ir.ValueProvider:
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
) -> ir.ValueProvider:
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
    key: ir.Value,
    *,
    default_error_message: str,
) -> ir.ValueProvider:
    storage_codec = _get_storage_codec_for_node(expr)
    if isinstance(expr, awst_nodes.BoxValueExpression):
        # BoxRead will assert the box exists when lowered
        # It is deliberately used in this case to provide further optimization opportunities
        # when loading large box values.
        # It is deliberately not used when doing conditional box loads (maybe/get) because of
        # the implications.
        box_read = ir.BoxRead(
            key=key,
            value_type=types.bytes_,
            source_location=expr.source_location,
            exists_assertion_message=expr.exists_assertion_message or default_error_message,
        )
        (storage_value,) = context.visitor.materialise_value_provider(box_read, "storage_value")
    else:
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
    encoded_value: ir.Value
    did_exist: ir.Value


def _build_get_ex_op(
    context: IRFunctionBuildContext,
    encoded_avm_type: typing.Literal[AVMType.uint64, AVMType.bytes],
    expr: awst_nodes.StorageExpression,
    key: ir.Value,
) -> ir.ValueProvider:
    # note: result_type is intentionally using PrimitiveIRType rather than
    # the IRType of the storage expression. As it is not safe to assume what is in storage
    # is actually the type described by the expression, for example the box may have been
    # created larger than the static type implies
    match encoded_avm_type:
        case AVMType.uint64:
            result_type = types.uint64
        case AVMType.bytes:
            result_type = types.bytes_
        case unexpected:
            typing.assert_never(unexpected)

    if isinstance(expr, awst_nodes.AppStateExpression):
        current_app_offset = ir.UInt64Constant(value=0, source_location=expr.source_location)
        get_storage_value: ir.ValueProvider = ir.Intrinsic(
            op=AVMOp.app_global_get_ex,
            args=[current_app_offset, key],
            types=[result_type, types.bool_],
            source_location=expr.source_location,
        )
    elif isinstance(expr, awst_nodes.AppAccountStateExpression):
        current_app_offset = ir.UInt64Constant(value=0, source_location=expr.source_location)
        account = context.visitor.visit_and_materialise_single(expr.account)
        get_storage_value = ir.Intrinsic(
            op=AVMOp.app_local_get_ex,
            args=[account, current_app_offset, key],
            types=[result_type, types.bool_],
            source_location=expr.source_location,
        )
    else:
        typing.assert_type(expr, awst_nodes.BoxValueExpression)
        get_storage_value = ir.Intrinsic(
            op=AVMOp.box_get,
            args=[key],
            types=[result_type, types.bool_],
            source_location=expr.source_location,
        )
    return get_storage_value


def visit_state_exists(
    context: IRFunctionBuildContext, field: awst_nodes.StorageExpression, loc: SourceLocation
) -> ir.ValueProvider:
    key = context.visitor.visit_and_materialise_single(field.key)
    result_type = _get_storage_codec_for_node(field).encoded_ir_type
    if isinstance(field, awst_nodes.AppStateExpression):
        op = AVMOp.app_global_get_ex
        args = [ir.UInt64Constant(value=0, source_location=loc), key]
    elif isinstance(field, awst_nodes.AppAccountStateExpression):
        op = AVMOp.app_local_get_ex
        account = context.visitor.visit_and_materialise_single(field.account)
        args = [account, ir.UInt64Constant(value=0, source_location=loc), key]
    else:
        typing.assert_type(field, awst_nodes.BoxValueExpression)
        # use box_len for existence check, in case len(value) is > 4096
        result_type = types.uint64
        op = AVMOp.box_len
        args = [key]

    ir_types = [result_type, types.bool_]
    get_ex = ir.Intrinsic(op=op, args=args, types=ir_types, source_location=loc)
    _, maybe_exists = context.visitor.materialise_value_provider(get_ex, ("_", "maybe_exists"))
    return maybe_exists


def visit_state_get(
    context: IRFunctionBuildContext, expr: awst_nodes.StateGet
) -> ir.ValueProvider:
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
    decoded_ir_type = types.wtype_to_ir_type(expr.field, allow_tuple=True)
    if isinstance(decoded_ir_type, types.TupleIRType):
        default_decoded_vp = ir.ValueTuple(
            values=default_decoded_values,
            ir_type=decoded_ir_type,
            source_location=expr.default.source_location,
        )
        return _conditional_tuple_value_provider(
            context,
            condition=did_exist,
            typ=decoded_ir_type,
            true_factory=lambda: storage_codec.decode(
                context, storage_value, expr.source_location
            ),
            false_factory=lambda: default_decoded_vp,
            loc=expr.source_location,
        )
    else:
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


def visit_state_get_ex(
    context: IRFunctionBuildContext, expr: awst_nodes.StateGetEx
) -> ir.ValueProvider:
    key = context.visitor.visit_and_materialise_single(expr.field.key)
    storage_codec = _get_storage_codec_for_node(expr.field)
    get_ex_op = _build_get_ex_op(context, storage_codec.encoded_avm_type, expr.field, key)
    storage_value, did_exist = context.visitor.materialise_value_provider(
        get_ex_op, ("maybe_value", "maybe_exists")
    )
    decoded_ir_type = types.wtype_to_ir_type(expr.field, allow_tuple=True)
    if not isinstance(decoded_ir_type, types.TupleIRType):
        decoded_vp = storage_codec.decode(context, storage_value, expr.source_location)
    else:
        default_decoded = undefined_value(decoded_ir_type, expr.source_location)
        decoded_vp = _conditional_tuple_value_provider(
            context,
            condition=did_exist,
            typ=decoded_ir_type,
            true_factory=lambda: storage_codec.decode(
                context, storage_value, expr.source_location
            ),
            false_factory=lambda: default_decoded,
            loc=expr.source_location,
        )

    maybe_values = context.visitor.materialise_value_provider(decoded_vp, "maybe_value")
    return ir.ValueTuple(
        values=[*maybe_values, did_exist],
        ir_type=types.TupleIRType(elements=[decoded_ir_type, types.bool_], fields=None),
        source_location=expr.source_location,
    )


def _conditional_tuple_value_provider(
    context: IRFunctionBuildContext,
    *,
    condition: ir.Value,
    typ: types.TupleIRType,
    true_factory: Callable[[], ir.ValueProvider],
    false_factory: Callable[[], ir.ValueProvider],
    loc: SourceLocation,
) -> ir.ValueProvider:
    """
    Builds a conditional that returns one of two ValueProviders

    true and false values are provided via factories so IR construction emits them at the correct
    time
    """
    true_block, false_block, merge_block = context.block_builder.mkblocks(
        "ternary_true", "ternary_false", "ternary_merge", source_location=loc
    )
    context.block_builder.terminate(
        ir.ConditionalBranch(
            condition=condition,
            non_zero=true_block,
            zero=false_block,
            source_location=loc,
        )
    )
    tmp_var_name = context.next_tmp_name("ternary_result")
    tmp_var_names = typ.build_item_names(tmp_var_name)
    tmp_var_ir_types = types.ir_type_to_ir_types(typ)
    context.block_builder.activate_block(true_block)
    true = true_factory()
    assign_tuple(
        context,
        source=true,
        names=tmp_var_names,
        ir_types=tmp_var_ir_types,
        assignment_location=true.source_location,
        register_location=loc,
    )
    context.block_builder.goto(merge_block)

    context.block_builder.activate_block(false_block)
    false = false_factory()
    assign_tuple(
        context,
        source=false,
        names=tmp_var_names,
        ir_types=tmp_var_ir_types,
        assignment_location=false.source_location,
        register_location=loc,
    )
    context.block_builder.goto(merge_block)

    context.block_builder.activate_block(merge_block)
    result = [
        context.ssa.read_variable(variable=name, ir_type=ir_type, block=merge_block)
        for name, ir_type in zip(tmp_var_names, tmp_var_ir_types, strict=True)
    ]
    return ir.ValueTuple(values=result, ir_type=typ, source_location=loc)


def visit_state_delete(
    context: IRFunctionBuildContext, statement: awst_nodes.StateDelete
) -> ir.ValueProvider | None:
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

    state_delete = ir.Intrinsic(op=op, args=args, source_location=statement.source_location)
    if statement.wtype == wtypes.bool_wtype:
        return state_delete

    context.block_builder.add(state_delete)
    return None


class StorageCodec(abc.ABC):
    @abc.abstractmethod
    def encode(
        self, context: IRFunctionBuildContext, values: Sequence[ir.Value], loc: SourceLocation
    ) -> ir.Value: ...

    @abc.abstractmethod
    def decode(
        self, context: IRFunctionBuildContext, value: ir.Value, loc: SourceLocation
    ) -> ir.ValueProvider: ...

    @property
    @abc.abstractmethod
    def encoded_ir_type(self) -> types.IRType: ...

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

    if isinstance(declared_type, wtypes.WTuple):
        arc4_wtype = maybe_wtype_to_arc4_wtype(declared_type)
        if arc4_wtype is None:
            raise InternalError("expected persistable tuple type to be ARC-4 encodable", loc)
        return _ARC4StorageCodec(declared_type=declared_type, arc4_type=arc4_wtype, loc=loc)

    if declared_type.scalar_type is None:
        raise InternalError(f"unable to construct storage codec for type: {declared_type!r}", loc)
    ir_type = types.wtype_to_ir_type(declared_type, loc)
    return _PassthroughStorageCodec(ir_type)


class _UInt64AsBytesStorageCodec(StorageCodec):
    @typing.override
    def encode(
        self, context: IRFunctionBuildContext, values: Sequence[ir.Value], loc: SourceLocation
    ) -> ir.Value:
        assert len(values) == 1, f"{type(self).__name__}.encode(..) expects single value"
        (value,) = values
        factory = OpFactory(context, loc)
        return factory.itob(value=value, temp_desc="encoded_value")

    @typing.override
    def decode(
        self, context: IRFunctionBuildContext, value: ir.Value, loc: SourceLocation
    ) -> ir.ValueProvider:
        factory = OpFactory(context, loc)
        return factory.btoi(value=value, temp_desc="maybe_value_converted")

    @property
    @typing.override
    def encoded_ir_type(self) -> types.IRType:
        return types.SizedBytesType(num_bytes=8)


class _PassthroughStorageCodec(StorageCodec):
    def __init__(self, encoded_ir_type: types.IRType) -> None:
        self._encoded_ir_type = encoded_ir_type

    @typing.override
    def encode(
        self, context: IRFunctionBuildContext, values: Sequence[ir.Value], loc: SourceLocation
    ) -> ir.Value:
        assert len(values) == 1, f"{type(self).__name__}.encode(..) expects single value"
        (value,) = values
        return value

    @typing.override
    def decode(
        self, context: IRFunctionBuildContext, value: ir.Value, loc: SourceLocation
    ) -> ir.ValueProvider:
        return value

    @property
    @typing.override
    def encoded_ir_type(self) -> types.IRType:
        return self._encoded_ir_type


class _ARC4StorageCodec(StorageCodec):
    """For when user / high-level types must be converted to ARC-4 for storage"""

    def __init__(
        self, *, declared_type: wtypes.WType, arc4_type: wtypes.ARC4Type, loc: SourceLocation
    ) -> None:
        self._declared_type = types.wtype_to_ir_type(
            declared_type, source_location=loc, allow_tuple=True
        )
        self._encoded_type = types.wtype_to_encoded_ir_type(arc4_type, loc)

    @typing.override
    def encode(
        self, context: IRFunctionBuildContext, values: Sequence[ir.Value], loc: SourceLocation
    ) -> ir.Value:
        encoded_vp = ir.BytesEncode.maybe(
            values=values,
            values_type=self._declared_type,
            encoding=self._encoded_type.encoding,
            source_location=loc,
        )
        encoded, *rest = context.visitor.materialise_value_provider(
            encoded_vp, "encoded_for_storage"
        )
        assert not rest, "encoded result should be a single stack value"
        return encoded

    @typing.override
    def decode(
        self, context: IRFunctionBuildContext, value: ir.Value, loc: SourceLocation
    ) -> ir.ValueProvider:
        return ir.DecodeBytes.maybe(
            value=value,
            encoding=self._encoded_type.encoding,
            ir_type=self._declared_type,
            source_location=loc,
        )

    @cached_property
    @typing.override
    def encoded_ir_type(self) -> types.IRType:
        return self._encoded_type
