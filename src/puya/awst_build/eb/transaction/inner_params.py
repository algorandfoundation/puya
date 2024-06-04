from __future__ import annotations

import typing

from puya.awst import wtypes
from puya.awst.nodes import (
    INNER_PARAM_TXN_FIELDS,
    Copy,
    CreateInnerTransaction,
    Expression,
    SubmitInnerTransaction,
    TxnField,
    TxnFields,
    UInt64Constant,
    UpdateInnerTransaction,
)
from puya.awst_build import pytypes
from puya.awst_build.constants import TransactionType
from puya.awst_build.eb._base import (
    FunctionBuilder,
    NotIterableInstanceExpressionBuilder,
    TypeBuilder,
)
from puya.awst_build.eb._utils import bool_eval_to_constant
from puya.awst_build.eb.interface import InstanceBuilder, LiteralBuilder, NodeBuilder
from puya.awst_build.eb.transaction import get_field_python_name
from puya.awst_build.eb.transaction.base import expect_wtype
from puya.awst_build.eb.void import VoidExpressionBuilder
from puya.awst_build.utils import (
    construct_from_literal,
    expect_operand_type,
    require_instance_builder,
)
from puya.errors import CodeError, InternalError

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.nodes

    from puya.parse import SourceLocation

_parameter_mapping: typing.Final = {
    get_field_python_name(f): (f, pytypes.from_basic_wtype(f.wtype))
    for f in INNER_PARAM_TXN_FIELDS
}


def get_field_expr(arg_name: str, arg: InstanceBuilder) -> tuple[TxnField, Expression]:
    try:
        field, field_pytype = _parameter_mapping[arg_name]
    except KeyError as ex:
        raise CodeError(f"{arg_name} is not a valid keyword argument", arg.source_location) from ex
    if remapped_field := _maybe_transform_program_field_expr(field, arg):
        return remapped_field
    elif field.is_array:
        match arg:
            case InstanceBuilder(pytype=pytypes.TupleType(items=tuple_item_types)) if all(
                field.valid_type(t.wtype)
                for t in tuple_item_types  # TODO: revisit this re serialize
            ):
                expr = arg.resolve()
                return field, expr
        raise CodeError(f"{arg_name} should be of type tuple[{field.type_desc}, ...]")
    elif isinstance(arg, LiteralBuilder):
        # TODO: REMOVE HACK
        if wtypes.string_wtype in field.additional_input_wtypes and isinstance(arg.value, str):
            field_expr = construct_from_literal(arg, pytypes.StringType).resolve()
        else:
            field_expr = construct_from_literal(arg, field_pytype).resolve()
    else:
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
            t == pytypes.BytesType for t in tuple_item_types  # TODO: revisit this re serialize
        ):
            expr = eb.resolve()
        case _:
            expr = expect_operand_type(eb, pytypes.BytesType).resolve()
    return field, expr


class InnerTxnParamsTypeBuilder(TypeBuilder[pytypes.TransactionRelatedType]):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        transaction_fields: dict[TxnField, Expression] = {
            TxnFields.fee: UInt64Constant(
                source_location=self.source_location,
                value=0,
            )
        }
        transaction_type = self.produces().transaction_type
        if transaction_type:
            transaction_fields[TxnFields.type] = UInt64Constant(
                source_location=self.source_location,
                value=transaction_type.value,
                teal_alias=transaction_type.name,
            )
        for arg_name, arg in zip(arg_names, args, strict=True):
            if arg_name is None:
                raise CodeError(
                    f"Positional arguments are not supported for {self.produces()}",
                    location,
                )
            field, expression = get_field_expr(arg_name, require_instance_builder(arg))
            transaction_fields[field] = expression
        typ = self.produces()
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
    def serialize_bytes(self, location: SourceLocation) -> Expression:
        raise CodeError("cannot serialize inner transaction fieldset", location)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        if name == "submit":
            return _Submit(self.resolve(), self.pytype.transaction_type, location)
        elif name == "set":
            return _Set(self.resolve(), location)
        elif name == "copy":
            return _Copy(self.resolve(), self.pytype, location)
        return super().member_access(name, location)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        return bool_eval_to_constant(value=True, location=location, negate=negate)


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
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        from puya.awst_build.eb.transaction import InnerTransactionExpressionBuilder

        if args:
            raise CodeError(f"Unexpected arguments for {self.expr}", location)
        result_typ = pytypes.InnerTransactionResultTypes[self._txn_type]
        return InnerTransactionExpressionBuilder(
            SubmitInnerTransaction(
                itxns=(self.expr,),
                wtype=result_typ.wtype,
                source_location=location,
            ),
            result_typ,
        )


class _Copy(FunctionBuilder):
    def __init__(
        self, expr: Expression, typ: pytypes.TransactionRelatedType, location: SourceLocation
    ) -> None:
        super().__init__(location)
        self._typ = typ
        self.wtype = expect_wtype(expr, wtypes.WInnerTransactionFields)
        assert typ.wtype == self.wtype
        self.expr = expr

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        if args:
            raise CodeError(f"Unexpected arguments for {self.expr}", location)
        return InnerTxnParamsExpressionBuilder(
            Copy(
                wtype=self.wtype,
                value=self.expr,
                source_location=location,
            ),
            self._typ,
        )


class _Set(FunctionBuilder):
    def __init__(self, expr: Expression, source_location: SourceLocation):
        super().__init__(source_location)
        self.expr = expr

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        if None in arg_names:
            raise CodeError(
                "Positional arguments are not supported when setting transaction parameters",
                location,
            )
        transaction_fields = dict[TxnField, Expression]()
        for arg_name, arg in zip(arg_names, args, strict=True):
            assert arg_name is not None
            field, expression = get_field_expr(arg_name, require_instance_builder(arg))
            transaction_fields[field] = expression
        return VoidExpressionBuilder(
            UpdateInnerTransaction(
                itxn=self.expr,
                fields=transaction_fields,
                source_location=location,
            )
        )
