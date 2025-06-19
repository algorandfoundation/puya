from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

import mypy.errors

from puya import log
from puya.arc56 import create_arc56_json
from puya.awst.nodes import AWST, RootNode
from puya.awst.serialize import awst_to_json, source_annotations_to_json
from puya.awst.to_code_visitor import ToCodeVisitor
from puya.compilation_artifacts import CompilationArtifact, CompiledContract
from puya.compile import awst_to_teal
from puya.errors import log_exceptions
from puya.program_refs import ContractReference, LogicSigReference
from puya.utils import make_path_relative_to_cwd
from puyapy.awst_build.arc4_client_gen import write_arc4_client
from puyapy.awst_build.main import transform_ast
from puyapy.client_gen import parse_arc56
from puyapy.options import PuyaPyOptions
from puyapy.parse import ParseResult, SourceDiscoveryMechanism, parse_python

logger = log.get_logger(__name__)


def compile_to_teal(puyapy_options: PuyaPyOptions) -> None:
    """Drive the actual core compilation step."""
    with log.logging_context() as log_ctx, log_exceptions():
        logger.debug(puyapy_options)
        try:
            parse_result = parse_python(puyapy_options.paths)
            log_ctx.sources_by_path = parse_result.sources_by_path
            log_ctx.exit_if_errors()
            awst, compilation_targets = transform_ast(parse_result)
        except mypy.errors.CompileError:
            # the placement of this catch is probably overly conservative,
            # but in parse_with_mypy there is a piece copied from mypyc, around setting
            # the location during mypy callbacks in case errors are produced.
            # also this error should have already been logged
            assert log_ctx.num_errors > 0, "expected mypy errors to be logged"
        log_ctx.exit_if_errors()
        output_inputs(awst, parse_result, puyapy_options)
        awst_lookup = {n.id: n for n in awst}
        compilation_set = {
            target_id: determine_out_dir(loc.file.parent, puyapy_options)
            for target_id, loc in (
                (t, awst_lookup[t].source_location) for t in compilation_targets
            )
            if loc.file
        }
        teal = awst_to_teal(
            log_ctx, puyapy_options, compilation_set, parse_result.sources_by_path, awst
        )
        log_ctx.exit_if_errors()
        if puyapy_options.output_client:
            write_arc4_clients(puyapy_options.template_vars_prefix, compilation_set, teal)
    # needs to be outside the with block
    log_ctx.exit_if_errors()


def output_inputs(
    awst: Sequence[RootNode], parse_result: ParseResult, puyapy_options: PuyaPyOptions
) -> None:
    awst_out_dir = (
        puyapy_options.out_dir or Path.cwd()  # TODO: maybe make this defaulted on init?
    )
    nodes = [n for n in awst if n.source_location.file in parse_result.explicit_source_paths]
    if puyapy_options.output_awst:
        output_awst(nodes, awst_out_dir)
    if puyapy_options.output_awst_json:
        output_awst_json(nodes, awst_out_dir)
    if puyapy_options.output_source_annotations_json:
        output_source_annotations_json(
            {
                s.path: s.lines
                for s in parse_result.ordered_modules.values()
                if s.discovery_mechanism != SourceDiscoveryMechanism.dependency
            },
            awst_out_dir,
        )


def write_arc4_clients(
    template_prefix: str,
    compilation_set: Mapping[ContractReference | LogicSigReference, Path],
    artifacts: Sequence[CompilationArtifact],
) -> None:
    for artifact in artifacts:
        if isinstance(artifact, CompiledContract) and artifact.metadata.is_arc4:
            contract_out_dir = compilation_set.get(artifact.id)
            if contract_out_dir:
                app_spec_json = create_arc56_json(
                    approval_program=artifact.approval_program,
                    clear_program=artifact.clear_program,
                    metadata=artifact.metadata,
                    template_prefix=template_prefix,
                )
                # use round trip of ARC-56 -> reparse to ensure consistency
                # of client output regardless if generating from ARC-56 or
                # Puya ARC4Contract
                contract = parse_arc56(app_spec_json)
                write_arc4_client(contract, contract_out_dir)


def output_awst(awst: AWST, awst_out_dir: Path) -> None:
    _output_awst_any(awst, ToCodeVisitor().visit_module, awst_out_dir, ".awst")


def output_awst_json(awst: AWST, awst_out_dir: Path) -> None:
    _output_awst_any(awst, awst_to_json, awst_out_dir, ".awst.json")


def _output_awst_any(
    awst: AWST, formatter: Callable[[AWST], str], awst_out_dir: Path, suffix: str
) -> None:
    out_text = formatter(awst)
    awst_out_dir.mkdir(exist_ok=True)
    output_path = awst_out_dir / f"module{suffix}"
    logger.info(f"writing {make_path_relative_to_cwd(output_path)}")
    output_path.write_text(out_text, "utf-8")


def determine_out_dir(contract_path: Path, options: PuyaPyOptions) -> Path:
    if not options.out_dir:
        out_dir = contract_path
    else:
        # find input path the contract is relative to
        for src_path in options.paths:
            src_path = src_path.resolve()
            src_path = src_path if src_path.is_dir() else src_path.parent
            try:
                relative_path = contract_path.relative_to(src_path)
            except ValueError:
                continue
            # construct a path that maintains a hierarchy to src_path
            out_dir = options.out_dir / relative_path
            if not options.out_dir.is_absolute():
                out_dir = src_path / out_dir
            break
        else:
            # if not relative to any input path
            if options.out_dir.is_absolute():
                out_dir = options.out_dir / contract_path
            else:
                out_dir = contract_path / options.out_dir

    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def output_source_annotations_json(
    sources_by_path: Mapping[Path, Sequence[str] | None], awst_out_dir: Path
) -> None:
    out_text = source_annotations_to_json(sources_by_path)
    output_path = awst_out_dir / "module.source.json"
    logger.info(f"writing {make_path_relative_to_cwd(output_path)}")
    output_path.write_text(out_text, "utf-8")
