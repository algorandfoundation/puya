import typing

from puya import log
from puya.avm import OnCompletionAction
from puya.awst import nodes as awst_nodes
from puya.awst.awst_traverser import AWSTTraverser

logger = log.get_logger(__name__)

# In arc56, `Create` only supports `NoOp`, `OptIn` and `DeleteApplication` as OCA
# - `UpdateApplication` would technically work but do nothing
#   (save for increasing the update version number)
# - `CloseOut` would fail as the account is not opted into the application
# See the arc56 implementation in utils:
# https://github.com/algorandfoundation/algokit-utils-py/blob/68e139d52e13db2afa3fe815dcfd44bcfa1eebea/src/algokit_abi/arc56.py#L92
_INVALID_CREATE_OCA = (
    OnCompletionAction.UpdateApplication,
    OnCompletionAction.CloseOut,
)


class ARC4CreateActionsValidator(AWSTTraverser):
    """
    Validates the create/OCA combinations on a contract's ARC-4 methods.
    """

    @classmethod
    def validate(cls, module: awst_nodes.AWST) -> None:
        for module_statement in module:
            validator = cls()
            module_statement.accept(validator)

    @typing.override
    def visit_contract(self, contract: awst_nodes.Contract) -> None:
        creation_configs = [
            config
            for method in contract.all_methods
            if (config := method.arc4_method_config) is not None
            and config.create != awst_nodes.ARC4CreateOption.disallow
        ]
        # creation methods whose allowed OCAs aren't all representable in arc56
        problematic_configs = [
            config for config in creation_configs if _invalid_create_ocas(config)
        ]
        for config in problematic_configs:
            _validate_create_config(config)


def _invalid_create_ocas(config: awst_nodes.ARC4MethodConfig) -> list[OnCompletionAction]:
    return [oca for oca in config.allowed_completion_types if oca in _INVALID_CREATE_OCA]


def _is_closeout_only(config: awst_nodes.ARC4MethodConfig) -> bool:
    return config.allowed_completion_types == (OnCompletionAction.CloseOut,)


def _validate_create_config(config: awst_nodes.ARC4MethodConfig) -> None:
    location = config.source_location
    allowed_completion_types = config.allowed_completion_types
    names = ", ".join(oca.name for oca in _invalid_create_ocas(config))
    has_valid_create_oca = any(oca not in _INVALID_CREATE_OCA for oca in allowed_completion_types)
    has_closeout = OnCompletionAction.CloseOut in allowed_completion_types

    if config.create == awst_nodes.ARC4CreateOption.require:
        # a create-only method with CloseOut as its only OCA can never be invoked:
        # a create + CloseOut always fails, as the account is never opted in at creation time
        if _is_closeout_only(config):
            logger.error(
                'required creation method with "CloseOut" as only allowed OCA will always fail, '
                "rendering the contract undeployable through this method",
                location=location,
            )
            return
        # create-only methods have no `call` list, so any non-representable OCA
        # is silently dropped from the arc56 spec
        logger.warning(
            f"arc56 clients will drop {names} on completion actions for creation method",
            location=location,
        )
        if has_closeout:
            logger.warning(
                "CloseOut on creation will always fail; consider removing it from allow_actions",
                location=location,
            )
    elif config.create == awst_nodes.ARC4CreateOption.allow:
        # with a valid create OCA the non-representable ones just go on the `call` list
        if has_valid_create_oca:
            return
        # CloseOut as the sole OCA is a dead create path: create + CloseOut always fails
        if _is_closeout_only(config):
            logger.error(
                'create="allow" with "CloseOut" as only OCA is a dead create path, '
                'consider switching to create="disallow"',
                location=location,
            )
            return
        # an update-only create capability (optionally with CloseOut) isn't arc56-representable
        logger.warning(
            f"arc56 clients will drop {names} on completion actions for creation method",
            location=location,
        )
