import abc
import typing
from collections.abc import Sequence

import mypy.nodes

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    Copy,
    CreateInnerTransaction,
    Expression,
    SubmitInnerTransaction,
    TupleExpression,
    UInt64Constant,
    UpdateInnerTransaction,
)
from puya.awst.txn_fields import TxnField
from puya.awst_build import pytypes
from puya.awst_build.eb import _expect as expect
from puya.awst_build.eb._base import FunctionBuilder, NotIterableInstanceExpressionBuilder
from puya.awst_build.eb._utils import constant_bool_and_error, dummy_value
from puya.awst_build.eb.interface import InstanceBuilder, NodeBuilder, TypeBuilder
from puya.awst_build.eb.none import NoneExpressionBuilder
from puya.awst_build.eb.transaction.fields import PythonTxnFieldParam
from puya.awst_build.eb.transaction.inner import InnerTransactionExpressionBuilder
from puya.awst_build.eb.tuple import TupleLiteralBuilder
from puya.awst_build.utils import maybe_resolve_literal
from puya.errors import CodeError
from puya.parse import SourceLocation

logger = log.get_logger(__name__)


def map_field_expr(params: PythonTxnFieldParam, builder: NodeBuilder) -> Expression:
    field = params.field
    field_pytype = params.type

    def dummy_result() -> Expression:
        if not field.is_array:
            dummy_pytype = field_pytype
        else:
            dummy_pytype = pytypes.GenericTupleType.parameterise(
                [field_pytype] * field.num_values, builder.source_location
            )
        return dummy_value(dummy_pytype, builder.source_location).resolve()

    if expect.instance_builder(builder):
        arg = builder
    else:
        return dummy_result()
    if field.is_array:
        match arg:
            case TupleLiteralBuilder(
                items=items, source_location=tup_loc
            ) if field == TxnField.ApplicationArgs:
                for item in items:
                    if item.pytype == pytypes.AccountType:
                        logger.warning(
                            f"{item.pytype} will not be added to foreign array,"
                            f" use .bytes to suppress this warning",
                            location=item.source_location,
                        )
                    elif item.pytype in (pytypes.AssetType, pytypes.ApplicationType):
                        logger.warning(
                            f"{item.pytype} will not be added to foreign array,"
                            f" use .id to suppress this warning",
                            location=item.source_location,
                        )
                return TupleExpression.from_items(
                    [item.to_bytes(item.source_location) for item in items], tup_loc
                )
            case InstanceBuilder(
                pytype=pytypes.TupleType(items=tuple_item_types)
            ) as tup_builder if all(field.valid_type(t.wtype) for t in tuple_item_types):
                return tup_builder.resolve()
            case _:
                return expect.argument_of_type_else_dummy(
                    arg, field_pytype, resolve_literal=True
                ).resolve()
    elif field.wtype == wtypes.bytes_wtype and arg.pytype in (
        pytypes.StrLiteralType,
        pytypes.StringType,
    ):
        # this handles the overlapping case of allowing Bytes && String to a single field
        field_expr = arg.to_bytes(arg.source_location)
    else:
        arg = maybe_resolve_literal(arg, field_pytype)
        if not field.valid_type(arg.pytype.wtype):
            logger.error("unexpected argument type", location=arg.source_location)
            return dummy_result()
        field_expr = arg.resolve()
    return field_expr


class InnerTxnParamsTypeBuilder(TypeBuilder[pytypes.TransactionRelatedType]):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        typ = self.produces()
        transaction_type = typ.transaction_type
        wtype = typ.wtype
        assert isinstance(wtype, wtypes.WInnerTransactionFields)

        transaction_fields = dict[TxnField, Expression]()
        transaction_fields[TxnField.Fee] = UInt64Constant(
            value=0, source_location=self.source_location
        )
        if transaction_type is not None:
            transaction_fields[TxnField.TypeEnum] = UInt64Constant(
                value=transaction_type.value,
                teal_alias=transaction_type.name,
                source_location=self.source_location,
            )
        transaction_fields.update(_map_itxn_args(arg_names, args))

        create_expr = CreateInnerTransaction(
            fields=transaction_fields, wtype=wtype, source_location=location
        )
        return InnerTxnParamsExpressionBuilder(typ, create_expr)


class InnerTxnParamsExpressionBuilder(
    NotIterableInstanceExpressionBuilder[pytypes.TransactionRelatedType]
):
    @typing.override
    def to_bytes(self, location: SourceLocation) -> Expression:
        raise CodeError("cannot serialize inner transaction fieldset", location)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        if name == "submit":
            return _Submit(self, location)
        elif name == "set":
            return _Set(self, location)
        elif name == "copy":
            return _Copy(self, location)
        return super().member_access(name, location)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        return constant_bool_and_error(value=True, location=location, negate=negate)


class _MemberFunction(FunctionBuilder, abc.ABC):
    def __init__(self, base: InnerTxnParamsExpressionBuilder, location: SourceLocation) -> None:
        super().__init__(location)
        self.base = base


class _Submit(_MemberFunction):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        expect.no_args(args, location)
        result_typ = pytypes.InnerTransactionResultTypes[self.base.pytype.transaction_type]
        submit_expr = SubmitInnerTransaction(group=self.base.resolve(), source_location=location)
        return InnerTransactionExpressionBuilder(submit_expr, result_typ)


class _Copy(_MemberFunction):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        expect.no_args(args, location)
        copy_expr = Copy(value=self.base.resolve(), source_location=location)
        return InnerTxnParamsExpressionBuilder(self.base.pytype, copy_expr)


class _Set(_MemberFunction):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        transaction_fields = _map_itxn_args(arg_names, args)
        update_expr = UpdateInnerTransaction(
            itxn=self.base.resolve(), fields=transaction_fields, source_location=location
        )
        return NoneExpressionBuilder(update_expr)


def _map_itxn_args(
    arg_names: list[str | None], args: Sequence[NodeBuilder]
) -> dict[TxnField, Expression]:
    transaction_fields = dict[TxnField, Expression]()
    for arg_name, arg in zip(arg_names, args, strict=True):
        if arg_name is None:
            logger.error("unexpected positional argument", location=arg.source_location)
        elif (field := _parameter_mapping.get(arg_name)) is None:
            logger.error("unrecognised keyword argument", location=arg.source_location)
        else:
            expression = map_field_expr(field, arg)
            transaction_fields[field] = expression
    return transaction_fields
