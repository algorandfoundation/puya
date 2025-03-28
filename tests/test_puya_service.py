import json
import subprocess
from pathlib import Path
from typing import Any

from pygls.client import JsonRPCClient

from puya.awst.serialize import get_converter
from puya.log import Log, LoggingContext, LogLevel, logging_context
from puya.puyad import AnalyseParams, PuyaProtocol
from puyapy.compile import compile_to_teal
from puyapy.options import PuyaPyOptions
from tests import EXAMPLES_DIR


class PuyadTestClient:
    """Client for testing the Puya daemon via JSON-RPC."""

    def __init__(self, *, debug: bool = False):
        """Initialize test client."""
        self.debug = debug
        self._log_ctx = LoggingContext()
        self._puyad = JsonRPCClient(PuyaProtocol, get_converter)
        self._puya_service_started = False

    def debug_print(self, message: str) -> None:
        """Print debug message."""
        if self.debug:
            self._log_ctx.logs.append(Log(level=LogLevel.debug, message=message, location=None))

    async def start(self) -> bool:
        """Start the Puya daemon process."""
        if self._puya_service_started:
            return True

        try:
            # Start the puya daemon
            puya_path = subprocess.check_output(["which", "puya"], text=True).strip()
            self.debug_print(f"Using puya at: {puya_path}")
            await self._puyad.start_io(puya_path)
            self._puya_service_started = True
            return True
        except Exception as e:
            self.debug_print(f"Error starting daemon: {e}")
            return False

    async def analyse(
        self, awst: list[Any], compilation_set: dict[str, str]
    ) -> dict[str, Any] | None:
        """Send analyse request to daemon."""
        try:
            params = AnalyseParams(
                awst=awst,
                compilation_set={key: Path(value) for key, value in compilation_set.items()},
            )
            response = await self._puyad.protocol.send_request_async("analyse", params)
            return response
        except Exception as e:
            self.debug_print(f"Error in analyse: {e}")
            return None

    async def stop(self) -> None:
        """Stop the daemon process."""
        if self._puya_service_started:
            try:
                await self._puyad.stop()
                self._puya_service_started = False
            except Exception as e:
                self.debug_print(f"Error stopping daemon: {e}")


async def generate_awst(
    example_name: str = "hello_world_arc4",
) -> tuple[list[Any], dict[str, str]]:
    """Generate AWST for hello_world_arc4 example without using a temporary file."""
    example_path = EXAMPLES_DIR / example_name

    options = PuyaPyOptions(
        paths=[example_path],
        output_awst_json=True,
        optimization_level=1,
        log_level=LogLevel.info,
    )

    # Use the compile_to_teal function to get the AWST directly
    compile_to_teal(options)

    # Read the AWST from the output JSON file
    awst_file = Path.cwd() / "module.awst.json"
    if not awst_file.exists():
        raise ValueError(f"Failed to compile TEAL: AWST file not found at {awst_file}")

    with open(awst_file) as f:
        awst = json.load(f)

    contract_mapping = {
        "hello_world_arc4": "examples.hello_world_arc4.contract.HelloWorldContract",
        "arc4_escrow": "examples.arc4_escrow.contract.EscrowContract",
    }

    contract_name = contract_mapping[example_name]
    compilation_set = {contract_name: str(example_path)}

    return (awst, compilation_set)


async def test_puya_service() -> None:
    """Integration test for Puya daemon."""
    with logging_context() as log_ctx:
        awst, compilation_set = await generate_awst()

        client = PuyadTestClient(debug=True)
        try:
            await client.start()
            result = await client.analyse(awst, compilation_set)

            assert result is not None, "Analysis result should not be None"
            assert "logs" in result, "Result should contain logs field"

            # Log information about the test results
            log_ctx.logs.append(
                Log(
                    level=LogLevel.info,
                    message=f"Analysis completed successfully with result: {result}",
                    location=None,
                )
            )

            if "logs" in result:
                log_messages = [
                    log.get("message", "") for log in result["logs"] if isinstance(log, dict)
                ]
                log_ctx.logs.append(
                    Log(
                        level=LogLevel.info,
                        message=f"Log messages from analysis: {log_messages}",
                        location=None,
                    )
                )
        except Exception as e:
            self.debug_print(f"Error in analyse: {e}")
            raise e
        finally:
            await client.stop()
