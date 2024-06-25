import typing
from collections.abc import Sequence

import mypy.nodes

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    INNER_PARAM_TXN_FIELDS,
    Copy,
    CreateInnerTransaction,
    Expression,
    SubmitInnerTransaction,
    TupleExpression,
    TxnField,
    TxnFields,
    UInt64Constant,
    UpdateInnerTransaction,
)
from puya.awst_build import pytypes
from puya.awst_build.constants import TransactionType
from puya.awst_build.eb import _expect as expect
from puya.awst_build.eb._base import FunctionBuilder, NotIterableInstanceExpressionBuilder
from puya.awst_build.eb._utils import constant_bool_and_error
from puya.awst_build.eb.interface import InstanceBuilder, NodeBuilder, TypeBuilder
from puya.awst_build.eb.none import NoneExpressionBuilder
from puya.awst_build.eb.transaction.fields import get_field_python_name
from puya.awst_build.eb.transaction.inner import InnerTransactionExpressionBuilder
from puya.awst_build.eb.tuple import TupleLiteralBuilder
from puya.awst_build.utils import maybe_resolve_literal, require_instance_builder
from puya.errors import CodeError, InternalError
from puya.parse import SourceLocation

logger = log.get_logger(__name__)
_parameter_mapping: typing.Final = {
    get_field_python_name(f): (f, pytypes.from_basic_wtype(f.wtype))
    for f in INNER_PARAM_TXN_FIELDS
}


def get_field_expr(arg_name: str, arg: InstanceBuilder) -> tuple[TxnField, Expression]:
    try:
        field, field_pytype = _parameter_mapping[arg_name]
    except KeyError as ex:
        # TODO: non-throwing
        raise CodeError(f"{arg_name} is not a valid keyword argument", arg.source_location) from ex
    if remapped_field := _maybe_transform_program_field_expr(field, arg):
        return remapped_field
    elif field.is_array:
        match arg:
            case TupleLiteralBuilder(
                items=items,
                source_location=tup_loc,
            ) if field == TxnFields.app_args:
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
                expr: Expression = TupleExpression.from_items(
                    [item.to_bytes(item.source_location) for item in items], tup_loc
                )
                return field, expr
            case InstanceBuilder(pytype=pytypes.TupleType(items=tuple_item_types)) if all(
                field.valid_type(t.wtype) for t in tuple_item_types
            ):
                expr = arg.resolve()
                return field, expr
        raise CodeError(f"{arg_name} should be of type tuple[{field.type_desc}, ...]")
    elif field_pytype == pytypes.BytesType:
        # this handles the overlapping case of allowing Bytes && String to a single field
        field_expr = arg.to_bytes(arg.source_location)
    else:
        arg = maybe_resolve_literal(arg, field_pytype)
        arg_typ = arg.pytype
        if not (arg_typ and field.valid_type(arg_typ.wtype)):
            raise CodeError("bad argument type", arg.source_location)
        field_expr = arg.resolve()
    return field, field_expr


def _maybe_transform_program_field_expr(
    field: TxnField, eb: InstanceBuilder
) -> tuple[TxnField, Expression] | None:
    match field.immediate:
        case "ApprovalProgram":
            field = TxnFields.approval_program_pages
        case "ClearStateProgram":
            field = TxnFields.clear_state_program_pages
        case _:
            return None
    if field.wtype != wtypes.bytes_wtype:
        raise InternalError(
            f"Unhandled type for program pages field: {field.wtype}", eb.source_location
        )

    match eb:
        case InstanceBuilder(pytype=pytypes.TupleType(items=tuple_item_types)) if all(
            t == pytypes.BytesType for t in tuple_item_types
        ):
            pass
        case _:
            eb = expect.argument_of_type_else_dummy(eb, pytypes.BytesType, resolve_literal=True)
    return field, eb.resolve()


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
        transaction_fields: dict[TxnField, Expression] = {
            TxnFields.fee: UInt64Constant(
                source_location=self.source_location,
                value=0,
            )
        }
        transaction_type = typ.transaction_type
        if transaction_type:
            transaction_fields[TxnFields.type] = UInt64Constant(
                value=transaction_type.value,
                teal_alias=transaction_type.name,
                source_location=self.source_location,
            )

        for arg_name, arg in zip(arg_names, args, strict=True):
            if arg_name is None:
                logger.error("unexpected positional argument", location=arg.source_location)
            else:
                field, expression = get_field_expr(arg_name, require_instance_builder(arg))
                transaction_fields[field] = expression
        wtype = typ.wtype
        assert isinstance(wtype, wtypes.WInnerTransactionFields)
        return InnerTxnParamsExpressionBuilder(
            CreateInnerTransaction(
                fields=transaction_fields,
                wtype=wtype,
                source_location=location,
            ),
            typ,
        )


class InnerTxnParamsExpressionBuilder(
    NotIterableInstanceExpressionBuilder[pytypes.TransactionRelatedType]
):
    def __init__(self, expr: Expression, typ: pytypes.TransactionRelatedType):
        assert isinstance(typ, pytypes.TransactionRelatedType)
        super().__init__(typ, expr)

    @typing.override
    def to_bytes(self, location: SourceLocation) -> Expression:
        raise CodeError("cannot serialize inner transaction fieldset", location)

    @typing.override
    def member_access(
        self, name: str, expr: mypy.nodes.Expression, location: SourceLocation
    ) -> NodeBuilder:
        if name == "submit":
            return _Submit(self.resolve(), self.pytype.transaction_type, location)
        elif name == "set":
            return _Set(self.resolve(), location)
        elif name == "copy":
            return _Copy(self.resolve(), self.pytype, location)
        return super().member_access(name, expr, location)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        return constant_bool_and_error(value=True, location=location, negate=negate)


class _Submit(FunctionBuilder):
    def __init__(
        self, expr: Expression, txn_type: TransactionType | None, location: SourceLocation
    ) -> None:
        super().__init__(location)
        self._txn_type = txn_type
        self.expr = expr

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        expect.no_args(args, location)
        result_typ = pytypes.InnerTransactionResultTypes[self._txn_type]
        return InnerTransactionExpressionBuilder(
            SubmitInnerTransaction(group=self.expr, source_location=location), result_typ
        )


class _Copy(FunctionBuilder):
    def __init__(
        self, expr: Expression, typ: pytypes.TransactionRelatedType, location: SourceLocation
    ) -> None:
        super().__init__(location)
        self._typ = typ
        self.expr = expr

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        expect.no_args(args, location)
        return InnerTxnParamsExpressionBuilder(
            Copy(value=self.expr, source_location=location), self._typ
        )


class _Set(FunctionBuilder):
    def __init__(self, expr: Expression, source_location: SourceLocation):
        super().__init__(source_location)
        self.expr = expr

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        transaction_fields = dict[TxnField, Expression]()
        for arg_name, arg in zip(arg_names, args, strict=True):
            if arg_name is None:
                logger.error("unexpected positional argument", location=arg.source_location)
            else:
                field, expression = get_field_expr(arg_name, require_instance_builder(arg))
                transaction_fields[field] = expression
        return NoneExpressionBuilder(
            UpdateInnerTransaction(
                itxn=self.expr,
                fields=transaction_fields,
                source_location=location,
            )
        )
