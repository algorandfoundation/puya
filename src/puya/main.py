from pathlib import Path

import attrs
import cattrs.preconf.json

from puya import log
from puya.awst import (
    nodes as awst_nodes,
    serialize,
)
from puya.compile import compile_and_write
from puya.context import CompileContext
from puya.errors import log_exceptions
from puya.models import ContractReference, LogicSigReference
from puya.options import PuyaOptions

logger = log.get_logger(__name__)


@attrs.frozen(kw_only=True)
class _PuyaOptionsWithCompilationSet(PuyaOptions):
    compilation_set: dict[str, Path]


@attrs.frozen(kw_only=True)
class _SourceAnnotationsFile:
    sources_by_path: dict[Path, list[str] | None]


def main(*, options_json: str, awst_json: str, source_annotations_json: str | None) -> None:
    with log.logging_context() as log_ctx, log_exceptions():
        awst = serialize.awst_from_json(awst_json)
        json_converter = cattrs.preconf.json.make_converter()
        options = json_converter.loads(options_json, _PuyaOptionsWithCompilationSet)
        compilation_set = dict[ContractReference | LogicSigReference, Path]()
        awst_lookup = {n.id: n for n in awst}
        for target_id, path in options.compilation_set.items():
            match awst_lookup.get(target_id):
                case awst_nodes.ContractFragment(id=contract_id):
                    compilation_set[contract_id] = path
                case awst_nodes.LogicSignature(id=lsig_id):
                    compilation_set[lsig_id] = path
                case None:
                    logger.error(f"compilation target {target_id!r} not found in AWST")
                case other:
                    logger.error(f"unexpected compilation target type: {type(other).__name__}")
        sources_by_path = {}
        if source_annotations_json:
            sources_by_path = json_converter.loads(
                source_annotations_json, dict[Path, list[str] | None]
            )

        compile_context = CompileContext(
            options=options,
            compilation_set=compilation_set,
            sources_by_path=sources_by_path,
        )
        compile_and_write(log_ctx, compile_context, awst)
