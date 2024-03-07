from __future__ import annotations

from typing import TYPE_CHECKING

import attrs
import mypy.nodes
import mypy.types
import structlog

from puya.arc4_util import get_abi_signature_from_wtypes, parse_method_signature
from puya.awst import wtypes
from puya.awst.nodes import (
    BytesConstant,
    BytesEncoding,
    CreateInnerTransaction,
    Expression,
    InnerTransactionField,
    Literal,
    MethodConstant,
    SingleEvaluation,
    SubmitInnerTransaction,
    TupleExpression,
    TxnField,
    TxnFields,
    UInt64Constant,
)
from puya.awst_build import constants
from puya.awst_build.arc4_utils import get_arc4_method_config
from puya.awst_build.eb.arc4.base import ARC4FromLogBuilder
from puya.awst_build.eb.base import (
    ExpressionBuilder,
    GenericClassExpressionBuilder,
    IntermediateExpressionBuilder,
    TypeClassExpressionBuilder,
)
from puya.awst_build.eb.transaction.inner_params import get_field_expr
from puya.awst_build.eb.var_factory import var_expression
from puya.awst_build.utils import (
    expect_operand_wtype,
    get_decorators_by_fullname,
)
from puya.errors import CodeError, InternalError
from puya.ir.arc4_router import arc4_encode

if TYPE_CHECKING:
    from collections.abc import Sequence

    from puya.awst_build.context import ASTConversionModuleContext
    from puya.models import ARC4MethodConfig
    from puya.parse import SourceLocation


logger: structlog.types.FilteringBoundLogger = structlog.get_logger(__name__)
APP_TRANSACTION_FIELDS = (
    TxnFields.app_id,
    TxnFields.on_completion,
    TxnFields.approval_program,
    TxnFields.clear_state_program,
    TxnFields.global_num_uint,
    TxnFields.global_num_byte_slice,
    TxnFields.local_num_uint,
    TxnFields.local_num_byte_slice,
    TxnFields.extra_program_pages,
    TxnFields.fee,
    TxnFields.sender,
    TxnFields.note,
    TxnFields.rekey_to,
)


@attrs.frozen
class _ABICallExpr:
    method: ExpressionBuilder | Literal
    abi_args: Sequence[ExpressionBuilder | Literal]
    transaction_kwargs: dict[str, ExpressionBuilder | Literal]


class ABICallGenericClassExpressionBuilder(GenericClassExpressionBuilder):
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        abi_call_expr = _extract_abi_call_args(args, arg_kinds, arg_names, location)
        method = abi_call_expr.method
        match method:
            case Literal(value=str(method_sig)):
                method_name, maybe_args, maybe_return_type = parse_method_signature(method_sig)
                arg_types = (
                    list(map(_arg_to_wtype, abi_call_expr.abi_args))
                    if maybe_args is None
                    else maybe_args
                )
                return_type = maybe_return_type or wtypes.void_wtype
            case ARC4MethodConfigExpressionBuilder() as eb:
                method_name = eb.method_config.name
                arg_types = eb.arg_types
                return_type = eb.return_type
            case _:
                raise CodeError(
                    "First argument must be a reference to an ARC4 ABI method", location
                )

        return var_expression(
            _create_abi_call_expr(
                get_abi_signature_from_wtypes(method_name, arg_types, return_type),
                arg_types,
                return_type,
                abi_call_expr.abi_args,
                abi_call_expr.transaction_kwargs,
                location,
            )
        )

    def index_multiple(
        self, indexes: Sequence[ExpressionBuilder | Literal], location: SourceLocation
    ) -> TypeClassExpressionBuilder:
        try:
            (index,) = indexes
        except ValueError as ex:
            raise CodeError("Expected a single type arg", location) from ex
        match index:
            case TypeClassExpressionBuilder() as type_class:
                wtype = type_class.produces()
            case _:
                raise CodeError("Invalid type parameter", index.source_location)
        return ABICallClassExpressionBuilder(wtype, location)


class ARC4ClientClassExpressionBuilder(IntermediateExpressionBuilder):
    def __init__(
        self,
        context: ASTConversionModuleContext,
        source_location: SourceLocation,
        type_info: mypy.nodes.TypeInfo,
    ):
        super().__init__(source_location)
        self.context = context
        self.type_info = type_info

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder | Literal:
        try:
            member = self.type_info.names[name]
        except KeyError as ex:
            raise CodeError(
                f"'{name}' is not a member of {self.type_info.fullname}", location
            ) from ex
        match member.node:
            case mypy.nodes.Decorator() as dec:
                decorators = get_decorators_by_fullname(self.context, dec)
                abimethod_dec = decorators.pop(constants.ABIMETHOD_DECORATOR, None)
                if abimethod_dec:
                    func_def = dec.func
                    arc4_method_config = get_arc4_method_config(
                        self.context, abimethod_dec, func_def
                    )
                    type_info = func_def.type
                    if isinstance(type_info, mypy.types.CallableType):
                        # convert the return type
                        return_type = self.context.type_to_wtype(
                            type_info.ret_type, source_location=location
                        )
                        # check & convert the arguments
                        mypy_args = func_def.arguments
                        mypy_arg_types = type_info.arg_types
                        if func_def.info is not mypy.nodes.FUNC_NO_INFO:
                            mypy_args = mypy_args[1:]
                            mypy_arg_types = mypy_arg_types[1:]
                        arg_types = list[wtypes.WType]()
                        for arg, arg_type in zip(mypy_args, mypy_arg_types, strict=True):
                            arg_types.append(
                                self.context.type_to_wtype(
                                    arg_type,
                                    source_location=self.context.node_location(arg, func_def.info),
                                )
                            )

                        return ARC4MethodConfigExpressionBuilder(
                            arc4_method_config, arg_types, return_type, location
                        )
        raise CodeError(f"'{self.type_info.fullname}.{name}' is not a valid ARC4 method", location)


class ARC4MethodConfigExpressionBuilder(IntermediateExpressionBuilder):
    def __init__(
        self,
        method_config: ARC4MethodConfig,
        arg_types: list[wtypes.WType],
        return_type: wtypes.WType,
        location: SourceLocation,
    ):
        super().__init__(location)
        self.method_config = method_config
        self.arg_types = arg_types
        self.return_type = return_type


class ABICallClassExpressionBuilder(TypeClassExpressionBuilder):
    def __init__(self, wtype: wtypes.WType, source_location: SourceLocation) -> None:
        super().__init__(source_location)
        self.wtype = wtype

    def produces(self) -> wtypes.WType:
        if self.wtype is None:
            raise CodeError("ABICall must have a type parameter", self.source_location)
        return self.wtype

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        abi_call_expr = _extract_abi_call_args(args, arg_kinds, arg_names, location)
        method = abi_call_expr.method

        match method:
            case Literal(value=str(method_str)):
                method_name, method_args, method_return = parse_method_signature(method_str)
            case _:
                raise CodeError(
                    "First argument must be a `str` value of an ARC4 method name/selector",
                    location,
                )

        if method_args:
            arg_wtypes = [
                _arg_to_wtype(arg, arg_wtype)
                for arg, arg_wtype in zip(abi_call_expr.abi_args, method_args, strict=True)
            ]
        else:
            arg_wtypes = list(map(_arg_to_wtype, abi_call_expr.abi_args))

        calculated_signature = get_abi_signature_from_wtypes(method_name, arg_wtypes, self.wtype)
        if not calculated_signature.startswith(method_str):
            raise CodeError(
                f"Method selector from args '{calculated_signature}' "
                f"does not match provided method selector: '{method_str}'",
                method.source_location,
            )

        return var_expression(
            _create_abi_call_expr(
                calculated_signature,
                arg_wtypes,
                self.wtype,
                abi_call_expr.abi_args,
                abi_call_expr.transaction_kwargs,
                location,
            )
        )


def _arg_to_wtype(
    arg: ExpressionBuilder | Literal, wtype: wtypes.WType | None = None
) -> wtypes.WType:
    # if wtype is known, then ensure arg can be coerced to that type
    if wtype:
        return expect_operand_wtype(arg, wtype).wtype
    # otherwise infer arg from literal type
    match arg:
        case ExpressionBuilder(value_type=wtypes.WType() as expr_wtype):
            return expr_wtype
        case Literal(value=bytes()):
            return wtypes.bytes_wtype
        case Literal(value=int()):
            return wtypes.uint64_wtype
        case Literal(value=str()):
            return wtypes.arc4_string_wtype
        case Literal(value=bool()):
            return wtypes.bool_wtype
    raise CodeError("Invalid arg type", arg.source_location)


def _create_abi_call_expr(
    method_selector: str,
    abi_arg_types: Sequence[wtypes.WType],
    abi_return_type: wtypes.WType,
    abi_args: Sequence[ExpressionBuilder | Literal],
    transaction_kwargs: dict[str, ExpressionBuilder | Literal],
    location: SourceLocation,
) -> Expression:
    abi_arg_exprs: list[Expression] = [
        MethodConstant(
            value=method_selector,
            source_location=location,
        )
    ]
    asset_exprs = list[Expression]()
    account_exprs = list[Expression]()
    application_exprs = list[Expression]()

    def append_ref_arg(ref_list: list[Expression], arg_expr: Expression) -> None:
        # asset refs start at 0, account and application start at 1
        implicit_offset = 0 if ref_list is asset_exprs else 1
        # TODO: what about references that are used more than once?
        ref_index = len(ref_list)
        ref_list.append(arg_expr)
        abi_arg_exprs.append(
            BytesConstant(
                value=(ref_index + implicit_offset).to_bytes(length=1),
                encoding=BytesEncoding.base16,
                source_location=arg_expr.source_location,
            )
        )

    for arg, wtype in zip(abi_args, abi_arg_types, strict=True):
        arg_expr = expect_operand_wtype(arg, wtype)
        match wtype:
            case wtypes.ARC4Type():
                abi_arg_exprs.append(arg_expr)
            case wtypes.asset_wtype:
                append_ref_arg(asset_exprs, arg_expr)
            case wtypes.account_wtype:
                append_ref_arg(account_exprs, arg_expr)
            case wtypes.application_wtype:
                append_ref_arg(application_exprs, arg_expr)
            case _ if wtypes.has_arc4_equivalent_type(wtype):
                arc4_wtype = wtypes.avm_to_arc4_equivalent_type(wtype)
                abi_arg_exprs.append(arc4_encode(arg_expr, arc4_wtype, arg_expr.source_location))
            case wtypes.WGroupTransaction():
                raise CodeError(
                    "Transaction arguments are not supported for contract to contract calls",
                    arg_expr.source_location,
                )
            case _:
                raise CodeError("Invalid argument type", arg_expr.source_location)

    fields: dict[TxnField, Expression] = {
        TxnFields.type: UInt64Constant(
            value=constants.TransactionType.appl.value,
            teal_alias=constants.TransactionType.appl.name,
            source_location=location,
        )
    }
    if abi_arg_exprs:
        fields[TxnFields.app_args] = TupleExpression(
            items=abi_arg_exprs,
            wtype=wtypes.WTuple.from_types([wtypes.bytes_wtype] * len(abi_arg_exprs)),
            source_location=location,  # TODO
        )
    if account_exprs:
        fields[TxnFields.accounts] = TupleExpression(
            items=account_exprs,
            wtype=wtypes.WTuple.from_types([wtypes.account_wtype] * len(account_exprs)),
            source_location=location,  # TODO
        )
    if application_exprs:
        fields[TxnFields.apps] = TupleExpression(
            items=application_exprs,
            wtype=wtypes.WTuple.from_types([wtypes.application_wtype] * len(application_exprs)),
            source_location=location,  # TODO
        )
    if asset_exprs:
        fields[TxnFields.assets] = TupleExpression(
            items=asset_exprs,
            wtype=wtypes.WTuple.from_types([wtypes.asset_wtype] * len(asset_exprs)),
            source_location=location,  # TODO
        )
    for field in APP_TRANSACTION_FIELDS:
        try:
            value = transaction_kwargs.pop(field.python_name)
        except KeyError:
            continue
        field, field_expr = get_field_expr(field.python_name, value)
        fields[field] = field_expr

    if transaction_kwargs:
        bad_args = "', '".join(transaction_kwargs)
        raise CodeError(f"Unknown arguments: '{bad_args}'", location)

    create_itxn = CreateInnerTransaction(
        fields=fields,
        wtype=wtypes.WInnerTransactionFields.from_type(constants.TransactionType.appl),
        source_location=location,
    )
    itxn = SubmitInnerTransaction(
        itxns=(create_itxn,),
        source_location=location,
        wtype=wtypes.WInnerTransaction.from_type(constants.TransactionType.appl),
    )

    if abi_return_type == wtypes.void_wtype:
        return itxn
    else:
        itxn_tmp = SingleEvaluation(itxn)
        last_log = InnerTransactionField(
            source_location=location,
            itxn=itxn_tmp,
            field=TxnFields.last_log,
            wtype=TxnFields.last_log.wtype,
        )
        return TupleExpression(
            items=(
                ARC4FromLogBuilder.abi_expr_from_log(abi_return_type, last_log, location),
                itxn_tmp,
            ),
            wtype=wtypes.WTuple.from_types(
                (
                    abi_return_type,
                    wtypes.WInnerTransaction.from_type(constants.TransactionType.appl),
                )
            ),
            source_location=location,
        )


def _extract_abi_call_args(
    args: Sequence[ExpressionBuilder | Literal],
    arg_kinds: list[mypy.nodes.ArgKind],
    arg_names: list[str | None],
    location: SourceLocation,
) -> _ABICallExpr:
    method: ExpressionBuilder | Literal | None = None
    abi_args = list[ExpressionBuilder | Literal]()
    kwargs = dict[str, ExpressionBuilder | Literal]()
    for i in range(len(args)):
        arg_kind = arg_kinds[i]
        arg_name = arg_names[i]
        arg = args[i]
        if arg_kind == mypy.nodes.ArgKind.ARG_POS and i == 0:
            method = arg
        elif arg_kind == mypy.nodes.ArgKind.ARG_POS:
            abi_args.append(arg)
        elif arg_kind == mypy.nodes.ArgKind.ARG_NAMED:
            if arg_name is None:
                raise InternalError(f"Expected named argument at pos {i}", location)
            kwargs[arg_name] = arg
        else:
            raise CodeError(f"Unexpected argument kind for '{arg_name}'", location)
    if method is None:
        raise CodeError("Missing required method positional argument", location)
    return _ABICallExpr(method=method, abi_args=abi_args, transaction_kwargs=kwargs)
