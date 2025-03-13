import json
import queue
import re
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict, Tuple

from puyapy.options import PuyaPyOptions
from puyapy.compile import compile_to_teal
from puya.log import LogLevel
from tests import EXAMPLES_DIR


class PuyadTestClient:
    """Client for testing the Puya daemon via JSON-RPC."""

    def __init__(self, debug: bool = False):
        """Initialize test client."""
        self.process = None
        self.stdout_thread = None
        self.stderr_thread = None
        self.is_running = False
        self.stderr_lines = []
        self.response_queue = queue.Queue()
        self.request_id = 1
        self.debug = debug

    def debug_print(self, message: str) -> None:
        """Print debug message."""
        if self.debug:
            pass

    def start(self) -> bool:
        """Start the Puya daemon process."""
        cmd = ["poetry", "run", "puyad"]

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

            self.stdout_thread = threading.Thread(target=self._read_stdout)
            self.stdout_thread.daemon = True
            self.stdout_thread.start()

            self.stderr_thread = threading.Thread(target=self._read_stderr)
            self.stderr_thread.daemon = True
            self.stderr_thread.start()

            time.sleep(1)

            if self._check_process_running():
                return True
            else:
                self._handle_startup_failure()
                return False

        except Exception:
            self.is_running = False
            return False

    def _check_process_running(self) -> bool:
        """Check if process is running."""
        if not self.process:
            return False
        return self.process.poll() is None

    def _handle_startup_failure(self) -> None:
        """Handle daemon startup failure."""
        self.is_running = False

    def _read_stdout(self) -> None:
        """Read daemon stdout using LSP protocol."""
        if not self.process or not self.process.stdout:
            return

        for line in iter(self.process.stdout.readline, ""):
            line = line.strip()

            if line.startswith("Content-Length:"):
                try:
                    content_length = int(line.split(":", 1)[1].strip())
                    self.debug_print(f"Found Content-Length: {content_length}")

                    next_line = self.process.stdout.readline().strip()

                    empty_line = self.process.stdout.readline()

                    content = ""
                    bytes_read = 0
                    while bytes_read < content_length:
                        char = self.process.stdout.read(1)
                        if not char:
                            break
                        content += char
                        bytes_read += 1

                    if content:
                        try:
                            data = json.loads(content)

                            if "id" in data:
                                self.debug_print(f"Received JSON-RPC response: {content}")
                                self.response_queue.put(data)
                            else:
                                self.debug_print(f"Received JSON-RPC notification: {content}")
                        except Exception:
                            pass
                except Exception:
                    pass

    def _read_stderr(self) -> None:
        """Read daemon stderr."""
        if not self.process or not self.process.stderr:
            return

        for line in iter(self.process.stderr.readline, ""):
            line = line.strip()
            if line:
                self.stderr_lines.append(line)

                try:
                    match = re.search(r"Sending data: ({.*})", line)
                    if match:
                        json_str = match.group(1)
                        data = json.loads(json_str)

                        if "id" in data and "result" in data:
                            self.response_queue.put(data)
                except Exception:
                    self.debug_print(f"Error extracting JSON from stderr: {e}")

    def send_request(self, method: str, params: Dict[str, Any] | None = None) -> Dict[str, Any] | None:
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
            "params": params if params is not None else {},
        }

        request_str = json.dumps(json_request)

        lsp_message = f"Content-Length: {len(request_str)}\r\n\r\n{request_str}"

        try:
            self.process.stdin.write(lsp_message)
            self.process.stdin.flush()
        except BrokenPipeError:
            self.is_running = False
            return None
        except OSError:
            self.is_running = False
            return None

        try:
            response = self.response_queue.get(timeout=10)
            return response
        except queue.Empty:
            return None

    def analyse(self, awst_path: str | Path, compilation_set: Dict[str, str]) -> Dict[str, Any] | None:
        """Send analyse request to daemon."""
        try:
            with open(awst_path, "r", encoding="utf-8") as f:
                awst_json = json.load(f)

            path_compilation_set = {}
            for key, value in compilation_set.items():
                if isinstance(value, str):
                    path_compilation_set[key] = str(Path(value))
                else:
                    path_compilation_set[key] = value

            params = {"awst": awst_json, "compilation_set": path_compilation_set}

            response = self.send_request("analyse", params)
            if response is not None and "result" in response:
                return response["result"]
            elif response is not None and "error" in response:
                return None
            return None
        except Exception:
            return None

    def stop(self) -> None:
        """Stop the daemon process."""
        if self.is_running and self.process:
            if self._check_process_running():
                try:
                    self.process.terminate()
                    try:
                        self.process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        self.process.kill()
                        self.process.wait(timeout=2)
                except Exception:
                    pass

            self.is_running = False


def generate_awst_file(tmp_path: Path) -> Tuple[Path, Dict[str, str]]:
    """Generate AWST file for hello_world_arc4 example."""
    example_path = EXAMPLES_DIR / "hello_world_arc4"
    awst_output_path = tmp_path / "module.awst.json"
    
    options = PuyaPyOptions(
        paths=[example_path],
        output_awst_json=True,
        optimization_level=1,
        log_level=LogLevel.info,
        out_dir=tmp_path
    )
    
    compile_to_teal(options)
    
    assert awst_output_path.exists(), f"AWST file was not created at {awst_output_path}"
    
    contract_name = "examples.hello_world_arc4.contract.HelloWorldContract"
    compilation_set = {contract_name: str(example_path)}
    
    return (awst_output_path, compilation_set)


def test_puyad_daemon(tmp_path: Path) -> None:
    """Integration test for Puya daemon."""
    awst_path, compilation_set = generate_awst_file(tmp_path)
    
    client = PuyadTestClient(debug=True)
    assert client.start(), "Failed to start puyad daemon"
    
    try:
        result = client.analyse(str(awst_path), compilation_set)
        
        assert result is not None, "Analysis result should not be None"
        assert "logs" in result, "Result should contain logs field"
        assert 'cancelled' in result and result['cancelled'] == False, "Analysis task completed without cancellation"
        
    finally:
        client.stop() 
