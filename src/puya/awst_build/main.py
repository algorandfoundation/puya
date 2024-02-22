from pathlib import Path

import mypy.build
import structlog

from puya.awst.nodes import Module
from puya.awst.to_code_visitor import ToCodeVisitor
from puya.awst_build.context import ASTConversionContext
from puya.awst_build.module import ModuleASTConverter
from puya.awst_build.validation.main import validate_awst
from puya.context import CompileContext
from puya.errors import InternalError
from puya.options import PuyaOptions
from puya.parse import EMBEDDED_MODULES, TYPESHED_PATH
from puya.utils import attrs_extend, determine_out_dir, make_path_relative_to_cwd

logger = structlog.get_logger()


def transform_ast(compile_context: CompileContext) -> dict[str, Module]:
    # module mapping is mutable here, but on the context it is an immutable Mapping
    # (from a type-checkers perspective, anyway)
    result = dict[str, Module]()
    ctx: ASTConversionContext = attrs_extend(
        ASTConversionContext, compile_context, module_asts=result
    )
    user_modules = {}
    for scc_module_names in mypy.build.sorted_components(ctx.parse_result.graph):
        for module_name in scc_module_names:
            module = ctx.parse_result.manager.modules.get(module_name)
            if module is None:
                raise InternalError(f"mypy failed to parse: {module_name}")
            module_rel_path = make_path_relative_to_cwd(module.path)
            if module_name != module.fullname:
                raise InternalError(
                    f"mypy parsed wrong module, expected '{module_name}': {module.fullname}"
                )
            if module.is_stub:
                if module_name in ("abc", "typing", "collections.abc"):
                    logger.debug(f"Skipping stdlib stub {module_rel_path}")
                elif module_name.startswith("puyapy"):
                    logger.debug(f"Skipping puyapy stub {module_rel_path}")
                elif Path(module.path).is_relative_to(TYPESHED_PATH):
                    logger.debug(f"Skipping typeshed stub {module_rel_path}")
                else:
                    logger.warning(f"Skipping stub: {module_rel_path}")
            elif embedded_src := EMBEDDED_MODULES.get(module.name):
                logger.debug(f"Building AWST for embedded puyapy lib at {module_rel_path}")
                module._fullname = embedded_src.puya_module_name  # noqa: SLF001
                result[embedded_src.puya_module_name] = ModuleASTConverter.convert(ctx, module)
            else:
                user_modules[module_name] = module
    for _, _ in user_modules.items():
        # TODO: pre-parse step: extract state info, constants, etc
        pass
    for module_name, module in user_modules.items():
        logger.debug(f"Building AWST for module {module_name}")
        errors_before_module = ctx.errors.num_errors
        module_awst = ModuleASTConverter.convert(ctx, module)
        validate_awst(ctx, module_awst)
        had_errors = ctx.errors.num_errors > errors_before_module
        if ctx.options.output_awst and not had_errors:
            output_awst(module_awst, ctx.options)
        result[module_name] = module_awst
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
