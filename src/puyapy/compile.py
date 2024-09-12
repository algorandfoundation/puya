import os
import shutil
import subprocess
import sysconfig
from collections.abc import Callable, Mapping, Sequence
from importlib import metadata
from pathlib import Path

import mypy.build
import mypy.errors
import mypy.find_sources
import mypy.fscache
import mypy.modulefinder
import mypy.nodes
import mypy.options
import mypy.util
from packaging import version
from puya import log, models
from puya.arc32 import create_arc32_json
from puya.awst.nodes import AWST
from puya.awst.serialize import awst_to_json
from puya.awst.to_code_visitor import ToCodeVisitor
from puya.compile import awst_to_teal
from puya.errors import log_exceptions
from puya.utils import make_path_relative_to_cwd

from puyapy.awst_build.arc32_client_gen import write_arc32_client
from puyapy.awst_build.main import transform_ast
from puyapy.client_gen import parse_app_spec_methods
from puyapy.options import PuyaPyOptions
from puyapy.parse import TYPESHED_PATH, ParseResult, parse_and_typecheck
from puyapy.utils import determine_out_dir

# this should contain the lowest version number that this compiler does NOT support
# i.e. the next minor version after what is defined in stubs/pyproject.toml:tool.poetry.version
MAX_SUPPORTED_ALGOPY_VERSION_EX = version.parse("2.2.0")
MIN_SUPPORTED_ALGOPY_VERSION = version.parse(f"{MAX_SUPPORTED_ALGOPY_VERSION_EX.major}.0.0")

logger = log.get_logger(__name__)


def compile_to_teal(puyapy_options: PuyaPyOptions) -> None:
    """Drive the actual core compilation step."""
    with log.logging_context() as log_ctx, log_exceptions():
        logger.debug(puyapy_options)
        try:
            parse_result = parse_with_mypy(puyapy_options.paths)
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
        if puyapy_options.output_awst or puyapy_options.output_awst_json:
            awst_out_dir = (
                puyapy_options.out_dir or Path.cwd()  # TODO: maybe make this defaulted on init?
            )
            nodes = [
                n for n in awst if n.source_location.file in parse_result.explicit_source_paths
            ]
            if puyapy_options.output_awst:
                output_awst(nodes, awst_out_dir)
            if puyapy_options.output_awst_json:
                output_awst_json(nodes, awst_out_dir)
        awst_lookup = {n.id: n for n in awst}
        compilation_set = {
            target_id: determine_out_dir(
                awst_lookup[target_id].source_location.file.parent, puyapy_options
            )
            for target_id in compilation_targets
        }
        teal = awst_to_teal(
            log_ctx, puyapy_options, compilation_set, parse_result.sources_by_path, awst
        )
        log_ctx.exit_if_errors()
        if puyapy_options.output_client:
            write_arc32_clients(compilation_set, teal)
    # needs to be outside the with block
    log_ctx.exit_if_errors()


def write_arc32_clients(
    compilation_set: Mapping[models.ContractReference | models.LogicSigReference, Path],
    artifacts: Sequence[models.CompilationArtifact],
) -> None:
    for artifact in artifacts:
        if isinstance(artifact, models.CompiledContract) and artifact.metadata.is_arc4:
            contract_out_dir = compilation_set.get(artifact.id)
            if contract_out_dir:
                app_spec_json = create_arc32_json(
                    artifact.approval_program.teal_src,
                    artifact.clear_program.teal_src,
                    artifact.metadata,
                )
                # use round trip of ARC32 -> reparse to ensure consistency
                # of client output regardless if generating from ARC32 or
                # Puya ARC4Contract
                name, methods = parse_app_spec_methods(app_spec_json)
                write_arc32_client(name, methods, contract_out_dir)


def parse_with_mypy(paths: Sequence[Path]) -> ParseResult:
    mypy_options = get_mypy_options()

    # this generates the ASTs from the build sources, and all imported modules (recursively)
    parse_result = parse_and_typecheck(paths, mypy_options)
    # Sometimes when we call back into mypy, there might be errors.
    # We don't want to crash when that happens.
    parse_result.manager.errors.set_file("<puyapy>", module=None, scope=None, options=mypy_options)

    return parse_result


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
