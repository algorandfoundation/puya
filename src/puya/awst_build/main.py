from pathlib import Path

from puya import log
from puya.awst.nodes import Module
from puya.awst.to_code_visitor import ToCodeVisitor
from puya.awst_build.context import ASTConversionContext
from puya.awst_build.module import ModuleASTConverter
from puya.context import CompileContext
from puya.options import PuyaOptions
from puya.parse import EMBEDDED_MODULES, TYPESHED_PATH, ParseResult
from puya.utils import attrs_extend, determine_out_dir, make_path_relative_to_cwd

logger = log.get_logger(__name__)


def transform_ast(compile_context: CompileContext, parse_result: ParseResult) -> dict[str, Module]:
    result = dict[str, Module]()
    ctx: ASTConversionContext = attrs_extend(
        ASTConversionContext, compile_context, parse_result=parse_result
    )
    user_modules = {}
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
