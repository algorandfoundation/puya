from pathlib import Path

from puya import log
from puya.awst.nodes import Module
from puya.awst.to_code_visitor import ToCodeVisitor
from puya.models import ContractReference
from puya.options import PuyaOptions
from puya.parse import SourceLocation
from puya.utils import StableSet, determine_out_dir, make_path_relative_to_cwd

from puyapy.awst_build import constants
from puyapy.awst_build.context import ASTConversionContext
from puyapy.awst_build.module import ModuleASTConverter
from puyapy.parse import EMBEDDED_MODULES, TYPESHED_PATH

logger = log.get_logger(__name__)


def transform_ast(ctx: ASTConversionContext) -> dict[str, Module]:
    result = dict[str, Module]()
    user_modules = {}
    result["algopy.arc4"] = _algopy_arc4_module(ctx)
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
            result[module_name] = ModuleASTConverter(ctx, module).convert()
        else:
            logger.debug(f"Discovered user module {module_name} at {module_rel_path}")
            user_modules[module_name] = ModuleASTConverter(ctx, module)

    sources = tuple(str(s.path) for s in ctx.parse_result.sources)
    for module_name, converter in user_modules.items():
        logger.debug(f"Building AWST for module {module_name}")
        module_awst = converter.convert()
        result[module_name] = module_awst
        if (
            ctx.options.output_awst
            and not converter.has_errors
            and module_awst.source_file_path.startswith(sources)
        ):
            output_awst(module_awst, ctx.options)
    return result


def _algopy_arc4_module(ctx: ASTConversionContext) -> Module:
    from puya.awst import wtypes
    from puya.awst.nodes import (
        # ARC4Router,
        Block,
        BoolConstant,
        ContractFragment,
        ContractMethod,
        MethodDocumentation,
        ReturnStatement,
    )

    location = SourceLocation(file="", line=-1)
    module_name, class_name = constants.ARC4_CONTRACT_BASE.rsplit(".", maxsplit=1)
    cref = ContractReference(module_name=module_name, class_name=class_name)
    ctx.set_state_defs(cref, {})
    body = [
        ContractFragment(
            module_name=module_name,
            name=class_name,
            name_override=None,
            is_abstract=True,
            bases=[],
            init=None,
            approval_program=None,
            # TODO: use the below once MRO is solved?
            # approval_program=ContractMethod(
            #     module_name=module_name,
            #     class_name=class_name,
            #     source_location=location,
            #     synthetic=True,
            #     arc4_method_config=None,
            #     args=[],
            #     return_type=wtypes.bool_wtype,
            #     documentation=MethodDocumentation(),
            #     name=constants.APPROVAL_METHOD,
            #     body=Block(
            #         source_location=location,
            #         body=[
            #             ReturnStatement(
            #                 value=ARC4Router(source_location=location),
            #                 source_location=location,
            #             )
            #         ],
            #     ),
            # ),
            clear_program=ContractMethod(
                module_name=module_name,
                class_name=class_name,
                source_location=location,
                synthetic=True,
                arc4_method_config=None,
                args=[],
                return_type=wtypes.bool_wtype,
                documentation=MethodDocumentation(),
                name=constants.CLEAR_STATE_METHOD,
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
        ),
    ]

    result = Module(name="algopy.arc4", source_file_path=location.file, body=body)
    return result


def output_awst(module_awst: Module, options: PuyaOptions) -> None:
    formatter = ToCodeVisitor()
    awst_module_str = formatter.visit_module(module_awst)
    if awst_module_str:
        module_path = Path(module_awst.source_file_path)
        if module_path.is_dir():
            module_path = module_path / "__init__.py"
        awst_module_output_path = (
            determine_out_dir(module_path.parent, options) / module_path.stem
        ).with_suffix(".awst")
        awst_module_output_path.write_text(awst_module_str, "utf-8")
