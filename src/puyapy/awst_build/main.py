from collections.abc import Sequence
from pathlib import Path

from puya import log
from puya.awst.nodes import Contract, LogicSignature, RootNode
from puya.models import ContractReference, LogicSigReference
from puya.parse import SourceLocation
from puya.utils import StableSet, make_path_relative_to_cwd

from puyapy.awst_build import constants
from puyapy.awst_build.context import ASTConversionContext
from puyapy.awst_build.module import ModuleASTConverter
from puyapy.parse import TYPESHED_PATH, ParseResult, SourceDiscoveryMechanism

logger = log.get_logger(__name__)


def transform_ast(
    parse_result: ParseResult,
) -> tuple[Sequence[RootNode], Sequence[ContractReference | LogicSigReference]]:
    ctx = ASTConversionContext(parse_result=parse_result)
    user_modules = []

    for module_name, src in parse_result.ordered_modules.items():
        module_rel_path = make_path_relative_to_cwd(src.path)
        if src.node.is_stub:
            if module_name in ("abc", "typing", "collections.abc"):
                logger.debug(f"Skipping stdlib stub {module_rel_path}")  # TODO: lowercase
            elif module_name.startswith("algopy"):
                logger.debug(f"Skipping algopy stub {module_rel_path}")
            elif src.path.is_relative_to(TYPESHED_PATH):
                logger.debug(f"Skipping typeshed stub {module_rel_path}")
            else:
                logger.warning(f"Skipping stub: {module_rel_path}")
        else:
            logger.debug(f"Discovered user module {module_name} at {module_rel_path}")
            module_ctx = ctx.for_module(src.path)
            user_modules.append((src, ModuleASTConverter(module_ctx, src.node)))

    compilation_set = list[ContractReference | LogicSigReference]()
    awst = [*_algopy_arc4_module(ctx)]
    for src, converter in user_modules:
        logger.debug(f"Building AWST for module {src.name}")
        root_nodes = converter.convert()
        awst.extend(root_nodes)
        if src.discovery_mechanism != SourceDiscoveryMechanism.dependency:
            for root_node in root_nodes:
                if isinstance(root_node, Contract | LogicSignature):
                    compilation_set.append(root_node.id)
    return awst, compilation_set


def _algopy_arc4_module(ctx: ASTConversionContext) -> list[RootNode]:
    from puya.awst import wtypes
    from puya.awst.nodes import (
        ARC4Router,
        Block,
        BoolConstant,
        Contract,
        ContractProgramMethod,
        MethodDocumentation,
        ReturnStatement,
    )

    # TODO: we don't need this anymore, just insert the relevant methods
    location = SourceLocation(file=Path("/algopy/arc4.py"), line=1)
    _, class_name = constants.ARC4_CONTRACT_BASE.rsplit(".", maxsplit=1)
    cref = ContractReference(constants.ARC4_CONTRACT_BASE)
    ctx.set_state_defs(cref, {})
    approval_program = ContractProgramMethod(
        cref=cref,
        source_location=location,
        return_type=wtypes.bool_wtype,
        documentation=MethodDocumentation(),
        member_name=constants.APPROVAL_METHOD,  # TODO: hmmm
        body=Block(
            source_location=location,
            body=[
                ReturnStatement(
                    value=ARC4Router(source_location=location),
                    source_location=location,
                )
            ],
        ),
    )
    clear_program = ContractProgramMethod(
        cref=cref,
        source_location=location,
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
    )
    arc4_base = Contract(
        id=cref,
        name=class_name,
        method_resolution_order=[],
        approval_program=approval_program,
        clear_program=clear_program,
        methods=[approval_program, clear_program],
        app_state=[],
        reserved_scratch_space=StableSet[int](),
        state_totals=None,
        description=None,
        source_location=location,
    )
    return [arc4_base]
