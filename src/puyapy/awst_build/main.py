from collections.abc import Sequence

from puya import log
from puya.awst.nodes import Contract, LogicSignature, RootNode
from puya.program_refs import ContractReference, LogicSigReference
from puya.utils import make_path_relative_to_cwd
from puyapy.awst_build.context import ASTConversionContext
from puyapy.awst_build.module import ModuleASTConverter
from puyapy.options import PuyaPyOptions
from puyapy.parse import ParseResult, SourceDiscoveryMechanism
from puyapy.validation.main import validate_awst

logger = log.get_logger(__name__)


def transform_ast(
    parse_result: ParseResult,
    puyapy_options: PuyaPyOptions,
) -> tuple[Sequence[RootNode], Sequence[ContractReference | LogicSigReference]]:
    ctx = ASTConversionContext(parse_result=parse_result, options=puyapy_options)
    user_modules = []

    for module_name, src in parse_result.ordered_modules.items():
        module_rel_path = make_path_relative_to_cwd(src.path)
        if src.node.is_stub:
            if module_name in ("abc", "typing", "collections.abc"):
                logger.debug(f"Skipping stdlib stub {module_rel_path}")  # TODO: lowercase
            elif module_name.startswith("algopy"):
                logger.debug(f"Skipping algopy stub {module_rel_path}")
            elif src.is_typeshed_file:
                logger.debug(f"Skipping typeshed stub {module_rel_path}")
            else:
                logger.warning(f"Skipping stub: {module_rel_path}")
        else:
            logger.debug(f"Discovered user module {module_name} at {module_rel_path}")
            module_ctx = ctx.for_module(src.path)
            user_modules.append((src, ModuleASTConverter(module_ctx, src.node)))

    compilation_set = list[ContractReference | LogicSigReference]()
    awst = list[RootNode]()
    for src, converter in user_modules:
        logger.debug(f"Building AWST for module {src.name}")
        root_nodes = converter.convert()
        awst.extend(root_nodes)
        if src.discovery_mechanism != SourceDiscoveryMechanism.dependency:
            for root_node in root_nodes:
                if isinstance(root_node, Contract | LogicSignature):
                    compilation_set.append(root_node.id)
    # do front end specific AWST validation
    validate_awst(awst)

    return awst, compilation_set
