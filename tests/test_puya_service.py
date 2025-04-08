import asyncio
import contextlib
import shutil
from pathlib import Path
from typing import Any, cast

import pytest
from pygls.client import JsonRPCClient

from puya.awst.nodes import AWST
from puya.awst.serialize import get_converter
from puya.log import LogLevel, logging_context
from puya.puya_service import AnalyseParams, PuyaProtocol
from tests import EXAMPLES_DIR
from tests.utils import get_awst_cache


async def generate_awst_file(
    example_name: str = "hello_world_arc4",
) -> tuple[AWST, dict[str, str]]:
    """Generate AWST for the example."""
    example_path = EXAMPLES_DIR / example_name

    # Use get_awst_cache instead of compiling directly
    cache = get_awst_cache(EXAMPLES_DIR)
    awst = cache.module_awst

    contract_mapping = {
        "hello_world_arc4": "examples.hello_world_arc4.contract.HelloWorldContract",
        "arc4_escrow": "examples.arc4_escrow.contract.EscrowContract",
    }

    contract_name = contract_mapping[example_name]
    compilation_set = {contract_name: str(example_path)}

    return (awst, compilation_set)


def find_puya_executable() -> str:
    """Find the puya executable in the PATH."""
    try:
        puya_path = shutil.which("puya")
        if not puya_path:
            raise RuntimeError("Could not find puya executable")  # noqa: TRY301
        return puya_path  # noqa: TRY300
    except Exception as e:
        raise RuntimeError("Error finding puya executable") from e


@pytest.mark.asyncio
async def test_puya_service() -> None:
    """Integration test for Puya service mode."""

    with logging_context():
        # Find the puya executable path
        puya_path = find_puya_executable()
        client = JsonRPCClient(PuyaProtocol, get_converter)

        try:
            # Start the puya service
            await client.start_io(puya_path, "serve")

            # Generate AWST for testing
            awst, compilation_set = await generate_awst_file()

            # Convert compilation set paths to proper Path objects
            path_compilation_set = {
                key: Path(value) if isinstance(value, str) else value
                for key, value in compilation_set.items()
            }
            params = AnalyseParams(
                awst=awst,
                compilation_set=path_compilation_set,
            )

            # Send the request and get response
            response = await asyncio.wait_for(
                cast(Any, client.protocol).send_request_async("analyse", params), timeout=30.0
            )

            assert response is not None, "Analysis result should not be None"
            assert hasattr(response, "logs"), "Result should contain logs field"

            log_messages = [log.message for log in response.logs]
            log_levels = [log.level for log in response.logs]
            assert any(
                "Analysis completed in" in msg for msg in log_messages
            ), "Analysis completion message not found"
            assert LogLevel.error not in log_levels, "Analysis contained errors"
            assert LogLevel.info in log_levels, "Expected to find info logs"

        except TimeoutError as e:
            raise RuntimeError("Analysis timed out") from e

        finally:
            with contextlib.suppress(Exception):
                await asyncio.wait_for(cast(Any, client).stop(), timeout=5.0)
