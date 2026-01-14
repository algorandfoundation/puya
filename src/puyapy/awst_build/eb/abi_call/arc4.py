import typing
from collections.abc import Iterable, Mapping, Sequence, Set

from puya import log
from puya.avm import OnCompletionAction, TransactionType
from puya.awst.nodes import (
    ABICall,
    ARC4CreateOption,
    ARC4MethodConfig,
    CompiledContract,
    Expression,
    SubmitInnerTransaction,
)
from puya.awst.txn_fields import TxnField
from puya.errors import CodeError
from puya.parse import SourceLocation
from puya.program_refs import ContractReference
from puyapy import models
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb._base import FunctionBuilder
from puyapy.awst_build.eb.abi_call._utils import (
    FIELD_TO_ITXN_ARGUMENT,
    ParsedMethod,
    add_on_completion,
    get_method_abi_args_and_kwargs,
    get_on_completion,
    get_python_kwargs,
    get_singular_on_complete,
    is_creating,
    maybe_resolve_literal,
    parse_abi_call_args,
    parse_abi_method_data,
    parse_contract_fragment_method,
)
from puyapy.awst_build.eb.arc4._base import ARC4FromLogBuilder
from puyapy.awst_build.eb.compiled import (
    APP_ALLOCATION_FIELDS,
    PROGRAM_FIELDS,
    CompiledContractExpressionBuilder,
)
from puyapy.awst_build.eb.contracts import ContractTypeExpressionBuilder
from puyapy.awst_build.eb.factories import builder_for_instance
from puyapy.awst_build.eb.interface import (
    InstanceBuilder,
    NodeBuilder,
)
from puyapy.awst_build.eb.subroutine import BaseClassSubroutineInvokerExpressionBuilder
from puyapy.awst_build.eb.transaction import InnerTransactionExpressionBuilder
from puyapy.awst_build.eb.transaction.itxn_args import PYTHON_ITXN_ARGUMENTS
from puyapy.awst_build.eb.tuple import TupleLiteralBuilder
from puyapy.models import (
    ContractFragmentBase,
)

logger = log.get_logger(__name__)

_ABI_CALL_TRANSACTION_FIELDS = [
    TxnField.ApplicationID,
    TxnField.OnCompletion,
    TxnField.ApprovalProgramPages,
    TxnField.ClearStateProgramPages,
    TxnField.GlobalNumUint,
    TxnField.GlobalNumByteSlice,
    TxnField.LocalNumUint,
    TxnField.LocalNumByteSlice,
    TxnField.ExtraProgramPages,
    TxnField.Fee,
    TxnField.Sender,
    TxnField.Note,
    TxnField.RekeyTo,
    TxnField.RejectVersion,
]
_ARC4_CREATE_TRANSACTION_FIELDS = [
    TxnField.OnCompletion,
    TxnField.Fee,
    TxnField.Sender,
    TxnField.Note,
    TxnField.RekeyTo,
]
_ARC4_UPDATE_TRANSACTION_FIELDS = [
    TxnField.ApplicationID,
    TxnField.Fee,
    TxnField.Sender,
    TxnField.Note,
    TxnField.RekeyTo,
    TxnField.RejectVersion,
]
_COMPILED_KWARG = "compiled"


class ABICallGenericTypeBuilder(FunctionBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        return _abi_call(args, arg_names, location, return_type_annotation=pytypes.NoneType)


class ABICallTypeBuilder(FunctionBuilder):
    def __init__(self, typ: pytypes.PyType, location: SourceLocation):
        assert isinstance(typ, pytypes.PseudoGenericFunctionType)
        self._return_type_annotation = typ.return_type
        super().__init__(location)

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        return _abi_call(
            args, arg_names, location, return_type_annotation=self._return_type_annotation
        )


class _ARC4CompilationFunctionBuilder(FunctionBuilder):
    allowed_fields: Sequence[TxnField]

    @property
    def allowed_kwargs(self) -> Set[str]:
        return {_COMPILED_KWARG, *get_python_kwargs(self.allowed_fields)}

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        # if on_completion not allowed, it must be an update
        is_update = TxnField.OnCompletion not in self.allowed_fields
        method_or_type, pos_args, kwargs = get_method_abi_args_and_kwargs(
            args, arg_names, self.allowed_kwargs
        )
        compiled = None
        if compiled_node := kwargs.pop(_COMPILED_KWARG, None):
            compiled = expect.argument_of_type_else_dummy(
                compiled_node, pytypes.CompiledContractType
            )

        match method_or_type:
            case None:
                raise CodeError("missing required positional argument 'method'", location)
            case BaseClassSubroutineInvokerExpressionBuilder(method=fmethod, cref=contract_ref):
                parsed_method = parse_contract_fragment_method(
                    fmethod, None, method_or_type.source_location
                )
            case ContractTypeExpressionBuilder(
                fragment=fragment, pytype=pytypes.TypeType(typ=typ)
            ) if pytypes.ARC4ContractBaseType < typ:
                contract_ref = fragment.id
                parsed_method = _get_lifecycle_method_call(
                    fragment,
                    kind="update" if is_update else "create",
                    location=method_or_type.source_location,
                )
            case other:
                expect.not_this_type(other, default=expect.default_raise)
        if compiled is None:
            compiled = CompiledContractExpressionBuilder(
                CompiledContract(
                    contract=contract_ref,
                    wtype=pytypes.CompiledContractType.wtype,
                    source_location=location,
                )
            )
        else:
            _warn_if_different_contract(
                compiled, contract_ref, related_location=method_or_type.source_location
            )

        field_nodes = {PYTHON_ITXN_ARGUMENTS[kwarg].field: node for kwarg, node in kwargs.items()}
        if is_update:
            add_on_completion(field_nodes, OnCompletionAction.UpdateApplication, location)
        # if on_completion is not set but can be inferred from config then use that
        elif (
            TxnField.OnCompletion not in field_nodes
            and (on_completion := get_singular_on_complete(parsed_method.abi_config)) is not None
        ):
            add_on_completion(field_nodes, on_completion, location)

        compiled = compiled.single_eval()
        for member_name, field in PROGRAM_FIELDS.items():
            field_nodes[field] = compiled.member_access(member_name, location)
        # is creating
        if not is_update:
            # add all app allocation fields
            for member_name, field in APP_ALLOCATION_FIELDS.items():
                field_nodes[field] = compiled.member_access(member_name, location)

        fields = dict[TxnField, Expression]()
        for field, field_node in field_nodes.items():
            params = FIELD_TO_ITXN_ARGUMENT[field]
            fields[field] = params.validate_and_convert(field_node).resolve()

        _validate_transaction_kwargs(
            field_nodes,
            parsed_method.abi_config,
            method_location=method_or_type.source_location,
            call_location=location,
        )

        abi_args = [expect.instance_builder(arg, default=expect.default_raise) for arg in pos_args]
        abi_call_args = [
            maybe_resolve_literal(
                arg, expected_type=arg_type, allow_literal=parsed_method.allow_literal_args
            ).resolve()
            for arg, arg_type in zip(abi_args, parsed_method.arg_types, strict=True)
        ]
        pytype = pytypes.GenericABIApplicationCall.parameterise(
            [parsed_method.declared_return_type or pytypes.NoneType], location
        )

        call_expr = ABICall(
            target=parsed_method.target,
            args=abi_call_args,
            fields=fields,
            wtype=pytype.wtype,
            source_location=location,
        )

        itxn_type = pytypes.InnerTransactionResultTypes[TransactionType.appl]
        itxn_builder = builder_for_instance(
            itxn_type,
            SubmitInnerTransaction(itxns=[call_expr], source_location=location),
        )

        if (
            parsed_method.declared_return_type is None
            or parsed_method.declared_return_type == pytypes.NoneType
        ):
            return itxn_builder
        itxn_builder = itxn_builder.single_eval()
        assert isinstance(itxn_builder, InnerTransactionExpressionBuilder)

        last_log = itxn_builder.get_field_value(TxnField.LastLog, pytypes.BytesType, location)
        abi_result = ARC4FromLogBuilder.abi_expr_from_log(
            parsed_method.declared_return_type, last_log, location
        )
        abi_result_builder = builder_for_instance(parsed_method.declared_return_type, abi_result)
        return TupleLiteralBuilder((abi_result_builder, itxn_builder), location)


def _warn_if_different_contract(
    compiled: InstanceBuilder, contract: ContractReference, *, related_location: SourceLocation
) -> None:
    # naive check for mismatch between method and compiled parameters
    expr = compiled.resolve()
    if isinstance(expr, CompiledContract) and expr.contract != contract:
        logger.warning(
            "compiled parameter is for a different contract",
            location=compiled.source_location,
        )
        logger.info("other contract reference", location=related_location)


class ARC4CreateFunctionBuilder(_ARC4CompilationFunctionBuilder):
    allowed_fields: Sequence[TxnField] = _ARC4_CREATE_TRANSACTION_FIELDS


class ARC4UpdateFunctionBuilder(_ARC4CompilationFunctionBuilder):
    allowed_fields: Sequence[TxnField] = _ARC4_UPDATE_TRANSACTION_FIELDS


def _abi_call(
    args: Sequence[NodeBuilder],
    arg_names: list[str | None],
    location: SourceLocation,
    *,
    return_type_annotation: pytypes.PyType,
) -> InstanceBuilder:
    parsed = parse_abi_call_args(
        args,
        arg_names,
        _ABI_CALL_TRANSACTION_FIELDS,
        return_type_annotation,
        _validate_transaction_kwargs,
        location,
    )

    pytype = pytypes.GenericABIApplicationCall.parameterise(
        [parsed.declared_return_type], location
    )

    call_expr = ABICall(
        target=parsed.target,
        args=parsed.abi_call_args,
        fields=parsed.fields,
        wtype=pytype.wtype,
        source_location=location,
    )

    itxn_type = pytypes.InnerTransactionResultTypes[TransactionType.appl]
    itxn_builder = builder_for_instance(
        itxn_type,
        SubmitInnerTransaction(itxns=[call_expr], source_location=location),
    )

    if parsed.declared_return_type == pytypes.NoneType:
        return itxn_builder
    itxn_builder = itxn_builder.single_eval()
    assert isinstance(itxn_builder, InnerTransactionExpressionBuilder)

    last_log = itxn_builder.get_field_value(TxnField.LastLog, pytypes.BytesType, location)
    abi_result = ARC4FromLogBuilder.abi_expr_from_log(
        parsed.declared_return_type, last_log, location
    )
    abi_result_builder = builder_for_instance(parsed.declared_return_type, abi_result)
    return TupleLiteralBuilder((abi_result_builder, itxn_builder), location)


def _get_lifecycle_method_call(
    fragment: ContractFragmentBase,
    kind: typing.Literal["create", "update"],
    location: SourceLocation,
) -> ParsedMethod:
    if kind == "create":
        possible_methods = list(fragment.find_arc4_method_metadata(can_create=True))
    elif kind == "update":
        possible_methods = list(
            fragment.find_arc4_method_metadata(oca=OnCompletionAction.UpdateApplication)
        )

    try:
        single_method, *others = possible_methods
    except ValueError:
        raise CodeError(f"could not find {kind} method on {fragment.id}", location) from None
    if others:
        raise CodeError(
            f"found multiple {kind} methods on {fragment.id}, please specify which one to use",
            location,
        )

    return parse_abi_method_data(single_method, location)


def _validate_transaction_kwargs(
    field_nodes: Mapping[TxnField, NodeBuilder],
    arc4_config: ARC4MethodConfig | None,
    method_location: SourceLocation | None,
    call_location: SourceLocation,
) -> None:
    # note these values may be None which indicates their value is unknown at compile time
    on_completion = get_on_completion(field_nodes)
    is_update = on_completion == OnCompletionAction.UpdateApplication
    is_create = is_creating(field_nodes)

    if is_create:
        # app_id not provided but method doesn't support creating
        if arc4_config and arc4_config.create == ARC4CreateOption.disallow:
            logger.error("method cannot be used to create application", location=method_location)
        # required args for creation missing
        else:
            _check_program_fields_are_present(
                "missing required arguments to create app", field_nodes, call_location
            )
    if is_update:
        if arc4_config and (
            OnCompletionAction.UpdateApplication not in arc4_config.allowed_completion_types
        ):
            logger.error("method cannot be used to update application", location=method_location)
        else:
            _check_program_fields_are_present(
                "missing required arguments to update app", field_nodes, call_location
            )
    # on_completion not valid for arc4_config
    elif (
        on_completion is not None
        and arc4_config
        and on_completion not in arc4_config.allowed_completion_types
    ):
        arg = field_nodes[TxnField.OnCompletion]
        logger.error(
            "on completion action is not supported by ARC-4 method being called",
            location=arg.source_location,
        )
        logger.info("method ARC-4 configuration", location=arc4_config.source_location)

    # programs provided when known not to be creating or updating
    if is_create is False and is_update is False:
        _check_fields_not_present(
            "provided argument is only valid when creating or updating an application",
            PROGRAM_FIELDS.values(),
            field_nodes,
        )
    if is_create is False:
        _check_fields_not_present(
            "provided argument is only valid when creating an application",
            APP_ALLOCATION_FIELDS.values(),
            field_nodes,
        )


def _check_program_fields_are_present(
    error_message: str, field_nodes: Mapping[TxnField, NodeBuilder], location: SourceLocation
) -> None:
    if missing_fields := [field for field in PROGRAM_FIELDS.values() if field not in field_nodes]:
        logger.error(
            f"{error_message}: {', '.join(get_python_kwargs(missing_fields))}",
            location=location,
        )


def _check_fields_not_present(
    error_message: str,
    fields_to_omit: Iterable[TxnField],
    field_nodes: Mapping[TxnField, NodeBuilder],
) -> None:
    for field in fields_to_omit:
        if node := field_nodes.get(field):
            logger.error(error_message, location=node.source_location)
