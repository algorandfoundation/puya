from pathlib import Path

import mypy.build
import structlog

from puya.awst.nodes import Module
from puya.awst.to_code_visitor import ToCodeVisitor
from puya.awst_build.context import ASTConversionContext
from puya.awst_build.module import ModuleASTConverter
from puya.context import CompileContext
from puya.errors import InternalError
from puya.options import PuyaOptions
from puya.parse import TYPESHED_PATH
from puya.utils import attrs_extend, determine_out_dir, make_path_relative_to_cwd

logger = structlog.get_logger()


def is_typeshed_stub(stub: Path) -> bool:
    return TYPESHED_PATH in stub.parents


def transform_ast(
    compile_context: CompileContext,
) -> dict[str, Module]:
    # module mapping is mutable here, but on the context it is an immutable Mapping
    # (from a type-checkers perspective, anyway)
    result = dict[str, Module]()
    ctx: ASTConversionContext = attrs_extend(
        ASTConversionContext,
        compile_context,
        module_asts=result,
    )
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
            if module_name in ("abc", "typing", "collections.abc"):
                logger.debug(f"Skipping stdlib stub {module_rel_path}")
            elif module_name.startswith("puyapy"):
                logger.debug(f"Skipping puyapy stub {module_rel_path}")
            elif module.is_stub and is_typeshed_stub(Path(module.path).absolute()):
                logger.debug(f"Skipping typeshed stub {module_rel_path}")
            elif module.is_stub:
                logger.warning(f"Skipping stub: {module_rel_path}")
            elif module_name == "_puyapy_":
                logger.debug(f"Building AWST for embedded puyapy lib at {module_rel_path}")
                module._fullname = "puyapy"  # noqa: SLF001
                module_awst = ModuleASTConverter.convert(ctx, module)
                result[module.name] = module_awst
            else:
                logger.debug(f"Building AWST for {module_rel_path}")
                module_awst = ModuleASTConverter.convert(ctx, module)
                if ctx.options.output_awst:
                    _output_awst(module_awst, ctx.options)
                result[module_name] = module_awst
    return result


def _output_awst(module_awst: Module, options: PuyaOptions) -> None:
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
