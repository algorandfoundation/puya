import functools
import os
import shutil
import subprocess
import sysconfig
import typing
from importlib import metadata
from pathlib import Path

import attrs
import mypy.build
import mypy.errors
import mypy.find_sources
import mypy.fscache
import mypy.modulefinder
import mypy.nodes
import mypy.options
import mypy.util
from immutabledict import immutabledict
from packaging import version

from puya import log
from puya.arc32 import create_arc32_json
from puya.artifact_sorter import Artifact, ArtifactCompilationSorter
from puya.awst.nodes import Module
from puya.awst_build.arc32_client_gen import write_arc32_client
from puya.awst_build.main import transform_ast
from puya.client_gen import parse_app_spec_methods
from puya.context import CompileContext
from puya.errors import CodeError, InternalError, log_exceptions
from puya.ir.main import build_module_irs, optimize_and_destructure_ir
from puya.ir.models import (
    Contract as ContractIR,
    LogicSignature,
    ModuleArtifact,
)
from puya.ir.optimize.context import IROptimizeContext
from puya.log import LoggingContext
from puya.mir.main import program_ir_to_mir
from puya.models import (
    CompilationArtifact,
    CompiledContract,
    CompiledLogicSig,
    CompiledProgram,
    ContractMetaData,
    ContractReference,
    LogicSignatureMetaData,
    LogicSigReference,
    TemplateValue,
)
from puya.options import PuyaOptions
from puya.parse import (
    TYPESHED_PATH,
    ParseResult,
    parse_and_typecheck,
)
from puya.teal import models as teal
from puya.teal.main import mir_to_teal
from puya.teal.output import emit_teal
from puya.ussemble.main import assemble_program
from puya.utils import attrs_extend, determine_out_dir, make_path_relative_to_cwd

# this should contain the lowest version number that this compiler does NOT support
# i.e. the next minor version after what is defined in stubs/pyproject.toml:tool.poetry.version
MAX_SUPPORTED_ALGOPY_VERSION_EX = version.parse("2.1.0")
MIN_SUPPORTED_ALGOPY_VERSION = version.parse(f"{MAX_SUPPORTED_ALGOPY_VERSION_EX.major}.0.0")

logger = log.get_logger(__name__)


def compile_to_teal(puya_options: PuyaOptions) -> None:
    """Drive the actual core compilation step."""
    with log.logging_context() as log_ctx, log_exceptions():
        logger.debug(puya_options)
        context, parse_result = parse_with_mypy(puya_options)
        log_ctx.exit_if_errors()
        awst = transform_ast(context, parse_result)
        log_ctx.exit_if_errors()
        compiled_contracts_by_source_path = awst_to_teal(log_ctx, context, awst)
        log_ctx.exit_if_errors()
        write_artifacts(context, compiled_contracts_by_source_path)
    log_ctx.exit_if_errors()


def awst_to_teal(
    log_ctx: LoggingContext,
    context: CompileContext,
    module_asts: dict[str, Module],
) -> dict[Path, list[CompilationArtifact]]:
    log_ctx.exit_if_errors()
    module_irs = build_module_irs(context, module_asts)
    log_ctx.exit_if_errors()
    compiled_contracts = module_irs_to_teal(log_ctx, context, module_irs)
    log_ctx.exit_if_errors()
    return compiled_contracts


def parse_with_mypy(puya_options: PuyaOptions) -> tuple[CompileContext, ParseResult]:
    mypy_options = get_mypy_options()

    # this generates the ASTs from the build sources, and all imported modules (recursively)
    parse_result = parse_and_typecheck(puya_options.paths, mypy_options)
    # Sometimes when we call back into mypy, there might be errors.
    # We don't want to crash when that happens.
    parse_result.manager.errors.set_file("<puya>", module=None, scope=None, options=mypy_options)

    context = CompileContext(
        options=puya_options,
        sources=parse_result.sources,
        module_paths={m.fullname: m.path for m in parse_result.ordered_modules},
    )

    return context, parse_result


def get_mypy_options() -> mypy.options.Options:
    mypy_opts = mypy.options.Options()

    # improve mypy parsing performance by using a cut-down typeshed
    mypy_opts.custom_typeshed_dir = str(TYPESHED_PATH)
    mypy_opts.abs_custom_typeshed_dir = str(TYPESHED_PATH.resolve())

    # set python_executable so third-party packages can be found
    mypy_opts.python_executable = _get_python_executable()

    mypy_opts.preserve_asts = True
    mypy_opts.include_docstrings = True
    # next two options disable caching entirely.
    # slows things down but prevents intermittent failures.
    mypy_opts.incremental = False
    mypy_opts.cache_dir = os.devnull

    # strict mode flags, need to review these and all others too
    mypy_opts.disallow_any_generics = True
    mypy_opts.disallow_subclassing_any = True
    mypy_opts.disallow_untyped_calls = True
    mypy_opts.disallow_untyped_defs = True
    mypy_opts.disallow_incomplete_defs = True
    mypy_opts.check_untyped_defs = True
    mypy_opts.disallow_untyped_decorators = True
    mypy_opts.warn_redundant_casts = True
    mypy_opts.warn_unused_ignores = True
    mypy_opts.warn_return_any = True
    mypy_opts.strict_equality = True
    mypy_opts.strict_concatenate = True

    # disallow use of any
    mypy_opts.disallow_any_unimported = True
    mypy_opts.disallow_any_expr = True
    mypy_opts.disallow_any_decorated = True
    mypy_opts.disallow_any_explicit = True

    mypy_opts.pretty = True  # show source in output

    return mypy_opts


def module_irs_to_teal(
    log_ctx: LoggingContext,
    context: CompileContext,
    module_irs: dict[str, list[ModuleArtifact]],
) -> dict[Path, list[CompilationArtifact]]:
    result = dict[Path, list[CompilationArtifact]]()
    # used to check for conflicts that would occur on output
    artifacts_by_output_base = dict[Path, ModuleArtifact]()

    artifact_refs = dict[Path, list[ContractReference | LogicSigReference]]()
    for src in context.sources:
        module_ir = module_irs.get(src.module_name)
        if module_ir is None:
            raise InternalError(f"Could not find IR for {src.path}")
        if not module_ir:
            if src.is_explicit:
                logger.warning(
                    f"No contracts found in explicitly named source file:"
                    f" {make_path_relative_to_cwd(src.path)}"
                )
            continue
        artifact_refs[src.path] = [ir.metadata.ref for ir in module_ir]

    compiled_artifacts = dict[
        ContractReference | LogicSigReference, _CompiledContract | _CompiledLogicSig
    ]()

    @functools.cache
    def get_program_bytecode(
        ref: ContractReference | LogicSigReference,
        kind: typing.Literal["approval", "clear_state", "logic_sig"],
        template_constants: immutabledict[str, TemplateValue],
    ) -> bytes:
        try:
            comp_ref = compiled_artifacts[ref]
        except KeyError:
            raise CodeError(f"invalid reference: {ref}") from None
        if kind == "logic_sig" and isinstance(comp_ref, _CompiledLogicSig):
            return assemble_program(context, comp_ref.program.teal, template_constants).bytecode
        elif kind in ("approval", "clear_state") and isinstance(comp_ref, _CompiledContract):
            program = comp_ref.approval_program if kind == "approval" else comp_ref.clear_program
            return assemble_program(context, program.teal, template_constants).bytecode
        else:
            raise InternalError(f"invalid kind: {kind}, {type(comp_ref)}")

    all_artifact_irs = {
        ir.metadata.ref: Artifact(
            path=Path(ir.source_location.file),
            ir=ir,
        )
        for module_ir in module_irs.values()
        for ir in module_ir
    }

    optimize_context = attrs_extend(
        IROptimizeContext,
        context,
        get_program_bytecode=get_program_bytecode,
        state_totals={
            artifact.ir.metadata.ref: artifact.ir.metadata.state_totals
            for artifact in all_artifact_irs.values()
            if isinstance(artifact.ir, ContractIR)
        },
    )

    for artifact in ArtifactCompilationSorter.sort(
        [ref for refs in artifact_refs.values() for ref in refs], all_artifact_irs
    ):
        out_dir = determine_out_dir(artifact.path.parent, context.options)
        name = artifact.ir.metadata.name
        artifact_ir_base_path = out_dir / name

        num_errors_before_optimization = log_ctx.num_errors
        artifact_ir = optimize_and_destructure_ir(
            optimize_context, artifact.ir, artifact_ir_base_path
        )
        # IR validation that occurs at the end of optimize_and_destructure_ir may have revealed
        # further errors, add dummy artifacts and continue so other artifacts can still be lowered
        # and report any errors they encounter
        errors_in_optimization = log_ctx.num_errors > num_errors_before_optimization

        if existing := artifacts_by_output_base.get(artifact_ir_base_path):
            logger.error(f"Duplicate contract name {name}", location=artifact_ir.source_location)
            logger.info(f"Contract name {name} first seen here", location=existing.source_location)
        else:
            artifacts_by_output_base[artifact_ir_base_path] = artifact_ir

        compiled: _CompiledContract | _CompiledLogicSig
        match artifact_ir:
            case ContractIR() as contract:
                if errors_in_optimization:
                    compiled = _CompiledContract(
                        approval_program=_dummy_program(),
                        clear_program=_dummy_program(),
                        metadata=contract.metadata,
                    )
                else:
                    compiled = _contract_ir_to_teal(
                        context,
                        contract,
                        artifact_ir_base_path,
                    )

            case LogicSignature() as logic_sig:
                if errors_in_optimization:
                    compiled = _CompiledLogicSig(
                        program=_dummy_program(),
                        metadata=logic_sig.metadata,
                    )
                else:
                    compiled = _logic_sig_to_teal(
                        context,
                        logic_sig,
                        artifact_ir_base_path,
                    )
            case _:
                typing.assert_never(artifact_ir)

        compiled_artifacts[artifact_ir.metadata.ref] = compiled
        if artifact.path in artifact_refs:
            result.setdefault(artifact.path, []).append(compiled)
    return result


def _get_python_executable() -> str | None:
    prefix = _get_prefix()
    if not prefix:
        logger.warning("Could not determine python prefix or algopy version")
        return None
    logger.info(f"Found python prefix: {prefix}")
    venv_paths = sysconfig.get_paths(vars={"base": prefix})

    python_exe = None
    for python in ("python3", "python"):
        python_exe = shutil.which(python, path=venv_paths["scripts"])
        if python_exe:
            logger.debug(f"Using python executable: {python_exe}")
            break
    else:
        logger.warning("Found a python prefix, but could not find the expected python interpreter")
    # use glob here, as we don't want to assume the python version
    discovered_site_packages = list(
        Path(prefix).glob(str(Path("[Ll]ib") / "**" / "site-packages"))
    )
    try:
        (site_packages,) = discovered_site_packages
    except ValueError:
        logger.warning(
            "Found a prefix, but could not find the expected"
            f" site-packages: {prefix=}, {discovered_site_packages=}"
        )
    else:
        logger.debug(f"Using python site-packages: {site_packages}")
        _check_algopy_version(site_packages)

    return python_exe


def _get_prefix() -> str | None:
    # look for VIRTUAL_ENV as we want the venv puyapy is being run against (i.e. the project),
    # if no venv is active, then fallback to the ambient python prefix
    venv = os.getenv("VIRTUAL_ENV")
    if venv:
        return venv
    for python in ("python3", "python"):
        prefix_result = subprocess.run(  # noqa: S602
            f"{python} -c 'import sys; print(sys.prefix or sys.base_prefix)'",
            shell=True,
            text=True,
            capture_output=True,
            check=False,
        )
        if prefix_result.returncode == 0 and (maybe_prefix := prefix_result.stdout.strip()):
            return maybe_prefix
    return None


_STUBS_PACKAGE_NAME = "algorand-python"


def _check_algopy_version(site_packages: Path) -> None:
    pkgs = metadata.Distribution.discover(name=_STUBS_PACKAGE_NAME, path=[str(site_packages)])
    try:
        (algopy,) = pkgs
    except ValueError:
        logger.warning("Could not determine algopy version")
        return
    algopy_version = version.parse(algopy.version)
    logger.debug(f"Found algopy: {algopy_version}")

    if not (MIN_SUPPORTED_ALGOPY_VERSION <= algopy_version < MAX_SUPPORTED_ALGOPY_VERSION_EX):
        logger.warning(
            f"{_STUBS_PACKAGE_NAME} version {algopy_version} is outside the supported range:"
            f" >={MIN_SUPPORTED_ALGOPY_VERSION}, <{MAX_SUPPORTED_ALGOPY_VERSION_EX}",
            important=True,
            related_lines=[
                "This will cause typing errors if there are incompatibilities in the API used.",
                "Please update your algorand-python package to be in the supported range.",
            ],
        )


@attrs.frozen
class _CompiledProgram(CompiledProgram):
    teal: teal.TealProgram
    teal_src: str
    bytecode: bytes | None


@attrs.frozen
class _CompiledContract(CompiledContract):
    approval_program: _CompiledProgram
    clear_program: _CompiledProgram
    metadata: ContractMetaData


@attrs.frozen
class _CompiledLogicSig(CompiledLogicSig):
    program: _CompiledProgram
    metadata: LogicSignatureMetaData


def _dummy_program() -> _CompiledProgram:
    return _CompiledProgram(
        teal=teal.TealProgram(
            target_avm_version=0, main=teal.TealSubroutine(signature="", blocks=[]), subroutines=[]
        ),
        teal_src="",
        bytecode=b"",
    )


def _contract_ir_to_teal(
    context: CompileContext,
    contract_ir: ContractIR,
    contract_ir_base_path: Path,
) -> _CompiledContract:
    approval_mir = program_ir_to_mir(
        context, contract_ir.approval_program, contract_ir_base_path.with_suffix(".approval.mir")
    )
    clear_state_mir = program_ir_to_mir(
        context, contract_ir.clear_program, contract_ir_base_path.with_suffix(".clear.mir")
    )
    approval = mir_to_teal(context, approval_mir)
    clear_state = mir_to_teal(context, clear_state_mir)
    return _CompiledContract(
        approval_program=_compile_program(context, approval),
        clear_program=_compile_program(context, clear_state),
        metadata=contract_ir.metadata,
    )


def _logic_sig_to_teal(
    context: CompileContext,
    logic_sig_ir: LogicSignature,
    logic_sig_ir_base_path: Path,
) -> _CompiledLogicSig:
    program_mir = program_ir_to_mir(
        context, logic_sig_ir.program, logic_sig_ir_base_path.with_suffix(".mir")
    )
    program = mir_to_teal(context, program_mir)
    return _CompiledLogicSig(
        program=_compile_program(context, program),
        metadata=logic_sig_ir.metadata,
    )


def _compile_program(context: CompileContext, program: teal.TealProgram) -> _CompiledProgram:
    return _CompiledProgram(
        teal=program,
        teal_src=emit_teal(context, program),
        bytecode=(
            assemble_program(
                context,
                program,
                {k: (v, None) for k, v in context.options.template_variables.items()},
            ).bytecode
            if context.options.output_bytecode
            else None
        ),
    )


def write_artifacts(
    context: CompileContext,
    compiled_artifacts_by_source_path: dict[Path, list[CompilationArtifact]],
) -> None:
    if not compiled_artifacts_by_source_path:
        logger.warning("No contracts or logic signatures discovered in any source files")
        return
    for src, compiled_artifacts in compiled_artifacts_by_source_path.items():
        out_dir = determine_out_dir(src.parent, context.options)
        for artifact in compiled_artifacts:
            teal_file_stem = artifact.metadata.name
            arc32_file_stem = f"{teal_file_stem}.arc32.json"
            artifact_base_path = out_dir / teal_file_stem
            match artifact:
                case CompiledLogicSig(program=program):
                    programs = {"": program}
                case CompiledContract(approval_program=approval, clear_program=clear) as contract:
                    programs = {
                        ".approval": approval,
                        ".clear": clear,
                    }
                    if contract.metadata.is_arc4:
                        app_spec_json = create_arc32_json(
                            approval.teal_src,
                            clear.teal_src,
                            contract.metadata,
                        )
                        if context.options.output_arc32:
                            arc32_path = out_dir / arc32_file_stem
                            logger.info(f"Writing {make_path_relative_to_cwd(arc32_path)}")
                            arc32_path.write_text(app_spec_json)
                        if context.options.output_client:
                            # use round trip of ARC32 -> reparse to ensure consistency
                            # of client output regardless if generating from ARC32 or
                            # Puya ARC4Contract
                            name, methods = parse_app_spec_methods(app_spec_json)
                            write_arc32_client(name, methods, out_dir)
                case _:
                    typing.assert_never(artifact)
            if context.options.output_teal:
                _write_output(
                    artifact_base_path,
                    {
                        f"{suffix}.teal": program.teal_src.encode("utf8")
                        for suffix, program in programs.items()
                    },
                )
            if context.options.output_bytecode:
                _write_output(
                    artifact_base_path,
                    {f"{suffix}.bin": program.bytecode for suffix, program in programs.items()},
                )


def _write_output(base_path: Path, programs: dict[str, bytes | None]) -> None:
    for suffix, program in programs.items():
        output_path = base_path.with_suffix(suffix)
        if program is None:
            logger.critical(f"Unable to output {make_path_relative_to_cwd(output_path)}")
        else:
            logger.info(f"Writing {make_path_relative_to_cwd(output_path)}")
            output_path.write_bytes(program)
