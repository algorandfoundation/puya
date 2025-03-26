import json
import queue
import re
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from puya.log import Log, LoggingContext, LogLevel, logging_context
from puyapy.compile import compile_to_teal
from puyapy.options import PuyaPyOptions
from tests import EXAMPLES_DIR


class PuyadTestClient:
    """Client for testing the Puya daemon via JSON-RPC."""

    def __init__(self, *, debug: bool = False):
        """Initialize test client."""
        self.process: subprocess.Popen[str] | None = None
        self.stdout_thread: threading.Thread | None = None
        self.stderr_thread: threading.Thread | None = None
        self.is_running: bool = False
        self.stderr_lines: list[str] = []
        self.response_queue: queue.Queue[dict[str, Any]] = queue.Queue()
        self.request_id: int = 1
        self.debug: bool = debug
        self._stop_threads: threading.Event = threading.Event()
        self._log_ctx = LoggingContext()

    def debug_print(self, message: str) -> None:
        """Print debug message."""
        if self.debug:
            self._log_ctx.logs.append(Log(level=LogLevel.debug, message=message, location=None))

    def start(self) -> bool:
        """Start the Puya daemon process."""
        cmd = ["poetry", "run", "puya", "--service"]

        try:
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )

            self.is_running = True
            self._stop_threads.clear()

            self.stdout_thread = threading.Thread(target=self._read_stdout)
            self.stderr_thread = threading.Thread(target=self._read_stderr)

            self.stdout_thread.daemon = True
            self.stderr_thread.daemon = True

            self.stdout_thread.start()
            self.stderr_thread.start()

            time.sleep(1)

            return self._check_process_running()
        except Exception as e:
            self.debug_print(f"Error starting daemon: {e}")
            self.is_running = False
            return False

    def _check_process_running(self) -> bool:
        """Check if process is running."""
        return self.process is not None and self.process.poll() is None

    def _read_stdout(self) -> None:
        """Read daemon stdout using LSP protocol."""
        if not self.process or not self.process.stdout:
            return

        try:
            for line in iter(self.process.stdout.readline, ""):
                if self._stop_threads.is_set():
                    break

                line = line.strip()
                if not line.startswith("Content-Length:"):
                    continue

                try:
                    content_length = int(line.split(":", 1)[1].strip())
                    self.debug_print(f"Found Content-Length: {content_length}")

                    self.process.stdout.readline()
                    self.process.stdout.readline()

                    content = self.process.stdout.read(content_length)
                    if not content or self._stop_threads.is_set():
                        break

                    try:
                        data = json.loads(content)
                        if "id" in data:
                            self.debug_print(f"Received JSON-RPC response: {content}")
                            self.response_queue.put(data)
                        else:
                            self.debug_print(f"Received JSON-RPC notification: {content}")
                    except json.JSONDecodeError as e:
                        self.debug_print(f"Error parsing JSON: {e}")
                except Exception as e:
                    self.debug_print(f"Error reading stdout: {e}")
        finally:
            if self.process and self.process.stdout:
                self.process.stdout.close()

    def _read_stderr(self) -> None:
        """Read daemon stderr."""
        if not self.process or not self.process.stderr:
            return

        try:
            for line in iter(self.process.stderr.readline, ""):
                if self._stop_threads.is_set():
                    break

                line = line.strip()
                if line:
                    self.stderr_lines.append(line)
                    self.debug_print(f"STDERR: {line}")

                    try:
                        match = re.search(r"Sending data: ({.*})", line)
                        if match:
                            data = json.loads(match.group(1))
                            if "id" in data and "result" in data:
                                self.response_queue.put(data)
                    except Exception as e:
                        self.debug_print(f"Error extracting JSON from stderr: {e}")
        finally:
            if self.process and self.process.stderr:
                self.process.stderr.close()

    def send_request(
        self, method: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        """Send JSON-RPC request to daemon."""
        if not self._check_process_running():
            self.is_running = False
            return None

        if not self.is_running or not self.process or not self.process.stdin:
            return None

        while not self.response_queue.empty():
            self.response_queue.get_nowait()

        request_id = self.request_id
        self.request_id += 1

        json_request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params or {},
        }

        request_str = json.dumps(json_request)
        lsp_message = f"Content-Length: {len(request_str)}\r\n\r\n{request_str}"

        try:
            self.process.stdin.write(lsp_message)
            self.process.stdin.flush()
        except (BrokenPipeError, OSError):
            self.is_running = False
            return None

        try:
            return self.response_queue.get(timeout=10)
        except queue.Empty:
            return None

    def analyse(
        self, awst_path: str | Path, compilation_set: dict[str, str]
    ) -> dict[str, Any] | None:
        """Send analyse request to daemon."""
        try:
            awst_file_path = Path(awst_path)
            with awst_file_path.open(encoding="utf-8") as f:
                awst_json = json.load(f)

            path_compilation_set = {
                key: str(Path(value)) if isinstance(value, str) else value
                for key, value in compilation_set.items()
            }

            params = {"awst": awst_json, "compilation_set": path_compilation_set}
            response = self.send_request("analyse", params)

            if response is not None:
                return response.get("result")
            else:
                return None
        except Exception as e:
            self.debug_print(f"Error in analyse: {e}")
            return None

    def stop(self) -> None:
        """Stop the daemon process."""
        self._stop_threads.set()

        if self.is_running and self.process:
            if self._check_process_running():
                try:
                    if self.process.stdin:
                        self.process.stdin.close()

                    self.process.terminate()
                    try:
                        self.process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        self.process.kill()
                        self.process.wait(timeout=1)
                except Exception as e:
                    self.debug_print(f"Error stopping daemon: {e}")

            self.is_running = False

        for thread in [self.stdout_thread, self.stderr_thread]:
            if thread and thread.is_alive():
                thread.join(timeout=1)


def generate_awst_file(
    tmp_path: Path, example_name: str = "hello_world_arc4"
) -> tuple[Path, dict[str, str]]:
    """Generate AWST file for hello_world_arc4 example."""
    example_path = EXAMPLES_DIR / example_name
    awst_output_path = tmp_path / "module.awst.json"

    options = PuyaPyOptions(
        paths=[example_path],
        output_awst_json=True,
        optimization_level=1,
        log_level=LogLevel.info,
        out_dir=tmp_path,
    )

    compile_to_teal(options)

    assert awst_output_path.exists(), f"AWST file was not created at {awst_output_path}"

    contract_mapping = {
        "hello_world_arc4": "examples.hello_world_arc4.contract.HelloWorldContract",
        "arc4_escrow": "examples.arc4_escrow.contract.EscrowContract",
    }

    contract_name = contract_mapping[example_name]
    compilation_set = {contract_name: str(example_path)}

    return (awst_output_path, compilation_set)


def test_puyad_daemon(tmp_path: Path) -> None:
    """Integration test for Puya daemon."""
    with logging_context() as log_ctx:
        awst_path, compilation_set = generate_awst_file(tmp_path)

        client = PuyadTestClient(debug=True)
        try:
            assert client.start(), "Failed to start puyad daemon"
            result = client.analyse(str(awst_path), compilation_set)

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

        finally:
            client.stop()
            time.sleep(0.5)
