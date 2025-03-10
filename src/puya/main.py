from pathlib import Path
import sys
import time
import traceback
from typing import Dict, Optional, Union, Any, List, Tuple

import attrs
import cattrs.preconf.json

from puya import log
from puya.awst import (
    nodes as awst_nodes,
    serialize,
)
from puya.compile import awst_to_teal
from puya.errors import log_exceptions
from puya.options import PuyaOptions
from puya.program_refs import ContractReference, LogicSigReference

logger = log.get_logger(__name__)


@attrs.frozen(kw_only=True)
class PuyaOptionsWithCompilationSet(PuyaOptions):
    compilation_set: dict[str, Path]


def main(*, options_json: str, awst_json: str, source_annotations_json: str | None) -> None:
    """
    Main compilation function for Puya.
    
    Args:
        options_json: JSON string containing compilation options
        awst_json: JSON string containing the AWST
        source_annotations_json: Optional JSON string containing source annotations
        
    Raises:
        Exception: If compilation fails
    """
    with log.logging_context() as log_ctx, log_exceptions():
        json_converter = cattrs.preconf.json.make_converter()
        sources_by_path = {}
        if source_annotations_json:
            sources_by_path = json_converter.loads(
                source_annotations_json, dict[Path, list[str] | None]
            )
        log_ctx.sources_by_path = sources_by_path
        awst = serialize.awst_from_json(awst_json)
        options = json_converter.loads(options_json, PuyaOptionsWithCompilationSet)
        compilation_set = dict[ContractReference | LogicSigReference, Path]()
        awst_lookup = {n.id: n for n in awst}
        for target_id, path in options.compilation_set.items():
            match awst_lookup.get(target_id):
                case awst_nodes.Contract(id=contract_id):
                    compilation_set[contract_id] = path
                case awst_nodes.LogicSignature(id=lsig_id):
                    compilation_set[lsig_id] = path
                case None:
                    logger.error(f"compilation target {target_id!r} not found in AWST")
                case other:
                    logger.error(f"unexpected compilation target type: {type(other).__name__}")
        awst_to_teal(log_ctx, options, compilation_set, sources_by_path, awst)
    # note: needs to be outside the with block
    log_ctx.exit_if_errors()


def compile_with_daemon_if_available(
    options_json: str,
    awst_json: str,
    source_annotations_json: Optional[str] = None,
    use_daemon: bool = True,
    daemon_host: str = "127.0.0.1",
    daemon_port: int = 8765,
    auto_start_daemon: bool = True,
    timeout: int = 60,
) -> Dict[str, Any]:
    """
    Compile using the daemon if available, otherwise fall back to direct compilation.
    
    This function provides a seamless way to leverage the daemon for improved performance
    while still working when the daemon is not available.
    
    Args:
        options_json: JSON string containing compilation options
        awst_json: JSON string containing the AWST
        source_annotations_json: Optional JSON string containing source annotations
        use_daemon: Whether to try using the daemon at all (default: True)
        daemon_host: The host address of the daemon server (default: 127.0.0.1)
        daemon_port: The port number of the daemon server (default: 8765)
        auto_start_daemon: Whether to try starting the daemon if it's not running (default: True)
        timeout: Timeout in seconds for the compilation (default: 60)
    
    Returns:
        A dictionary with the following keys:
        - success: True if compilation was successful, False otherwise
        - used_daemon: True if the daemon was used, False otherwise
        - error: Error message if compilation failed
        - daemon_error: Error message if there was an error with the daemon
        - elapsed_time: Time taken for compilation in seconds
    """
    result = {
        "success": False,
        "used_daemon": False,
        "elapsed_time": 0.0,
    }
    
    start_time = time.time()
    
    if not use_daemon:
        # Direct compilation without daemon
        try:
            main(
                options_json=options_json,
                awst_json=awst_json,
                source_annotations_json=source_annotations_json,
            )
            result["success"] = True
        except Exception as e:
            result["success"] = False
            result["error"] = str(e)
            result["traceback"] = traceback.format_exc()
        finally:
            result["elapsed_time"] = time.time() - start_time
        return result
    
    # Try to use daemon
    try:
        # Import here to avoid circular imports
        from puya.daemon_client import PuyaDaemonClient, ensure_daemon_running
        
        # Check if daemon is running and responsive, optionally starting it
        daemon_running = ensure_daemon_running(
            host=daemon_host,
            port=daemon_port,
            auto_start=auto_start_daemon,
            timeout=10  # Allow 10 seconds for daemon startup
        )
        
        if daemon_running:
            # Use daemon for compilation
            client = PuyaDaemonClient(daemon_host, daemon_port)
            logger.info(f"Using daemon at {daemon_host}:{daemon_port} for compilation")
            daemon_result = client.compile_sync(
                options_json=options_json,
                awst_json=awst_json,
                source_annotations_json=source_annotations_json,
                timeout=timeout
            )
            
            # Update our result with the daemon's result
            result.update(daemon_result)
            result["used_daemon"] = True
            result["elapsed_time"] = time.time() - start_time
            return result
        else:
            # Failed to start daemon - fall back to direct compilation
            logger.warning("Failed to start daemon, falling back to direct compilation")
            try:
                main(
                    options_json=options_json,
                    awst_json=awst_json,
                    source_annotations_json=source_annotations_json,
                )
                result["success"] = True
                result["daemon_error"] = "Failed to start daemon"
            except Exception as e:
                result["success"] = False
                result["error"] = str(e)
                result["traceback"] = traceback.format_exc()
            finally:
                result["elapsed_time"] = time.time() - start_time
            return result
    except ImportError as e:
        # If daemon client can't be imported, fall back to direct compilation
        logger.warning(f"Daemon client import error: {e}, falling back to direct compilation")
        try:
            main(
                options_json=options_json,
                awst_json=awst_json,
                source_annotations_json=source_annotations_json,
            )
            result["success"] = True
            result["daemon_error"] = f"Import error: {e}"
        except Exception as e:
            result["success"] = False
            result["error"] = str(e)
            result["traceback"] = traceback.format_exc()
        finally:
            result["elapsed_time"] = time.time() - start_time
        return result
    except Exception as e:
        # If any other error occurs with daemon, fall back to direct compilation
        logger.warning(f"Daemon error: {e}, falling back to direct compilation")
        try:
            main(
                options_json=options_json,
                awst_json=awst_json,
                source_annotations_json=source_annotations_json,
            )
            result["success"] = True
            result["daemon_error"] = str(e)
        except Exception as e2:
            result["success"] = False
            result["error"] = str(e2)
            result["daemon_error"] = str(e)
            result["traceback"] = traceback.format_exc()
        finally:
            result["elapsed_time"] = time.time() - start_time
        return result
