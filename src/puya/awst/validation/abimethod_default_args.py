import typing
from collections.abc import Mapping

from puya import log
from puya.avm import AVMType, OnCompletionAction
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.awst.arc4_types import wtype_to_arc4
from puya.awst.awst_traverser import AWSTTraverser
from puya.awst.nodes import (
    ABIMethodArgConstantDefault,
    ABIMethodArgMemberDefault,
    ARC4ABIMethodConfig,
    ARC4BareMethodConfig,
    ARC4CreateOption,
)

logger = log.get_logger(__name__)


class ABIMethodDefaultArgsValidator(AWSTTraverser):
    @classmethod
    def validate(cls, module: awst_nodes.AWST) -> None:
        for module_statement in module:
            if isinstance(module_statement, awst_nodes.Contract):
                validator = cls(module_statement)
                module_statement.accept(validator)

    def __init__(self, contract: awst_nodes.Contract):
        self._contract: typing.Final = contract
        self._state_by_name: typing.Final[Mapping[str, awst_nodes.AppStorageDefinition]] = {
            s.member_name: s for s in contract.app_state
        }

    @typing.override
    def visit_contract_method(self, method: awst_nodes.ContractMethod) -> None:
        arc4_config = method.arc4_method_config
        if not (arc4_config is None or isinstance(arc4_config, ARC4BareMethodConfig)):
            args_by_name = {a.name: a for a in method.args}
            for parameter_name, default_source in arc4_config.default_args.items():
                # any invalid parameter matches should have been caught earlier
                parameter = args_by_name[parameter_name]
                if not isinstance(default_source, ABIMethodArgConstantDefault):
                    self._validate_member_default_arg(parameter, default_source)

    def _validate_member_default_arg(
        self,
        param: awst_nodes.SubroutineArgument,
        default_source: ABIMethodArgMemberDefault,
    ) -> None:
        param_arc4_type = wtype_to_arc4(param.wtype)

        # special handling for reference types
        match param_arc4_type:
            case "asset" | "application":
                param_arc4_type = "uint64"
            case "account":
                param_arc4_type = "address"

        source_name = default_source.name
        state_source = self._state_by_name.get(source_name)
        if state_source is not None:
            storage_type = wtypes.persistable_stack_type(
                state_source.storage_wtype, param.source_location
            )
            if (
                storage_type is AVMType.uint64
                # storage can provide an int to types <= uint64
                # TODO: check what ATC does with ufixed, see if it can be added
                and (param_arc4_type == "byte" or param_arc4_type.startswith("uint"))
            ) or (
                storage_type is AVMType.bytes
                # storage can provide fixed byte arrays
                and (
                    (param_arc4_type.startswith("byte[") and param_arc4_type != "byte[]")
                    or param_arc4_type == "address"
                )
            ):
                pass
            else:
                logger.error(
                    f"'{source_name}' cannot provide '{param_arc4_type}' type",
                    location=param.source_location,
                )
        else:
            method_source = self._contract.resolve_contract_method(source_name)
            match method_source:
                case None:
                    logger.error(
                        f"'{source_name}' is not a known state or method attribute",
                        location=param.source_location,
                    )
                case awst_nodes.ContractMethod(
                    arc4_method_config=abi_method_config, args=args, return_type=return_type
                ):
                    if not isinstance(abi_method_config, ARC4ABIMethodConfig):
                        logger.error(
                            "only ARC-4 ABI methods can be used as default values",
                            location=param.source_location,
                        )
                    elif OnCompletionAction.NoOp not in abi_method_config.allowed_completion_types:
                        logger.error(
                            f"'{source_name}' does not allow no_op on completion calls",
                            location=param.source_location,
                        )
                    elif abi_method_config.create == ARC4CreateOption.require:
                        logger.error(
                            f"'{source_name}' can only be used for create calls",
                            location=param.source_location,
                        )
                    elif not abi_method_config.readonly:
                        logger.error(
                            f"'{source_name}' is not readonly", location=param.source_location
                        )
                    elif args:
                        logger.error(
                            f"'{source_name}' does not take zero arguments",
                            location=param.source_location,
                        )
                    elif return_type is wtypes.void_wtype:
                        logger.error(
                            f"'{source_name}' does not provide a value",
                            location=param.source_location,
                        )
                    elif wtype_to_arc4(return_type) != param_arc4_type:
                        logger.error(
                            f"'{source_name}' does not provide '{param_arc4_type}' type",
                            location=param.source_location,
                        )
                case unexpected:
                    typing.assert_never(unexpected)
