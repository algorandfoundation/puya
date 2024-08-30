from collections.abc import Sequence
from pathlib import Path

from puya import log
from puya.awst.nodes import RootNode, Subroutine
from puya.models import ContractReference
from puya.parse import SourceLocation
from puya.utils import StableSet, make_path_relative_to_cwd

from puyapy.awst_build import constants
from puyapy.awst_build.context import ASTConversionContext
from puyapy.awst_build.module import ModuleASTConverter
from puyapy.parse import EMBEDDED_MODULES, TYPESHED_PATH

logger = log.get_logger(__name__)


def transform_ast(
    ctx: ASTConversionContext,
) -> tuple[Sequence[RootNode], Sequence[Subroutine]]:
    user_modules = []
    result = [*_algopy_arc4_module(ctx)]
    embedded_funcs = []
    for module in ctx.parse_result.ordered_modules:
        module_name = module.fullname
        module_rel_path = make_path_relative_to_cwd(module.path)
        if module.is_stub:
            if module_name in ("abc", "typing", "collections.abc"):
                logger.debug(f"Skipping stdlib stub {module_rel_path}")
            elif module_name.startswith("algopy"):
                logger.debug(f"Skipping algopy stub {module_rel_path}")
            elif Path(module.path).is_relative_to(TYPESHED_PATH):
                logger.debug(f"Skipping typeshed stub {module_rel_path}")
            else:
                logger.warning(f"Skipping stub: {module_rel_path}")
        elif module_name in EMBEDDED_MODULES:
            logger.debug(f"Building AWST for embedded algopy lib at {module_rel_path}")
            embedded_nodes = ModuleASTConverter(ctx, module).convert()
            for en in embedded_nodes:
                assert isinstance(en, Subroutine)
                embedded_funcs.append(en)
        else:
            logger.debug(f"Discovered user module {module_name} at {module_rel_path}")
            user_modules.append(ModuleASTConverter(ctx, module))

    for converter in user_modules:
        logger.debug(f"Building AWST for module {converter.module_name}")
        module_awst = converter.convert()
        result.extend(module_awst)
    return result, embedded_funcs


def _algopy_arc4_module(ctx: ASTConversionContext) -> list[RootNode]:
    from puya.awst import wtypes
    from puya.awst.nodes import (
        ARC4Router,
        Block,
        BoolConstant,
        ContractFragment,
        ContractMethod,
        MethodDocumentation,
        ReturnStatement,
    )

    location = SourceLocation(file="/algopy/arc4.py", line=-1)
    _, class_name = constants.ARC4_CONTRACT_BASE.rsplit(".", maxsplit=1)
    cref = ContractReference(constants.ARC4_CONTRACT_BASE)
    ctx.set_state_defs(cref, {})
    arc4_base = ContractFragment(
        id=cref,
        name=class_name,
        is_abstract=True,
        bases=[],
        init=None,
        approval_program=ContractMethod(
            cref=cref,
            source_location=location,
            synthetic=True,
            arc4_method_config=None,
            args=[],
            return_type=wtypes.bool_wtype,
            documentation=MethodDocumentation(),
            member_name=constants.APPROVAL_METHOD,
            body=Block(
                source_location=location,
                body=[
                    ReturnStatement(
                        value=ARC4Router(source_location=location),
                        source_location=location,
                    )
                ],
            ),
        ),
        clear_program=ContractMethod(
            cref=cref,
            source_location=location,
            synthetic=True,
            arc4_method_config=None,
            args=[],
            return_type=wtypes.bool_wtype,
            documentation=MethodDocumentation(),
            member_name=constants.CLEAR_STATE_METHOD,
            body=Block(
                source_location=location,
                body=[
                    ReturnStatement(
                        value=BoolConstant(value=True, source_location=location),
                        source_location=location,
                    )
                ],
            ),
        ),
        subroutines=[],
        app_state={},
        reserved_scratch_space=StableSet[int](),
        state_totals=None,
        docstring=None,
        source_location=location,
    )
    return [arc4_base]
