import json

import attrs

from puya import log
from puya.awst.nodes import Module
from puya.awst_load.configure_cattrs import configure_cattrs
from puya.context import CompileContext
from puya.options import PuyaOptions
from puya.parse import ParseSource

logger = log.get_logger(__name__)


@attrs.define(kw_only=True)
class AwstLoadContext(CompileContext):
    pass


def load_awst(options: PuyaOptions) -> tuple[CompileContext, dict[str, Module]]:
    converter = configure_cattrs()
    module_awst = dict[str, Module]()
    sources = list[ParseSource]()
    for path in options.paths:
        if not path.is_file():
            logger.error(f"{path} does not exist, or is not a file.")
        json_data = json.load(path.open())
        for module_name, module in converter.structure(json_data, dict[str, Module]).items():
            module_awst[module_name] = module
            sources.append(ParseSource(path=path, module_name=module_name, is_explicit=True))

    module_awst["algopy"] = Module(name="algopy", source_file_path="", body=[])
    module_awst["algopy_lib_arc4"] = Module(name="algopy_lib_arc4", source_file_path="", body=[])
    module_awst["algopy_lib_bytes"] = Module(name="algopy_lib_bytes", source_file_path="", body=[])
    context: CompileContext = AwstLoadContext(
        options=options, sources=tuple(sources), module_paths={}
    )
    return context, module_awst
