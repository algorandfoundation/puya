#!/usr/bin/env python3
import json
import queue
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

# Import jsonrpcclient library
try:
    from jsonrpcclient import Error, Ok, parse_json, request
except ImportError:
    print("Please install jsonrpcclient: pip install jsonrpcclient")
    import sys

    sys.exit(1)


class PuyaClient:
    """Client for communicating with the Puya daemon (puyad) via JSON-RPC."""

    def __init__(
        self,
        python_executable: str = "python",
        log_level: str = "info",
        log_format: str = "default",
        debug: bool = True,
    ):
        """Initialize the Puya client.

        Args:
            python_executable: Path to the Python executable.
            log_level: Log level to use.
            log_format: Log format to use.
            debug: Whether to print debug information.
        """
        self.python_executable = python_executable
        self.log_level = log_level
        self.log_format = log_format
        self.process = None
        self.stdout_thread = None
        self.stderr_thread = None
        self.is_running = False
        self.stderr_lines = []
        self.response_queue = queue.Queue()
        self._buffer = ""  # Buffer for collecting partial messages
        self.request_id = 1  # Simple counter for request IDs
        self.debug = debug

    def _debug_print(self, message: str) -> None:
        """Print debug message if debug is enabled."""
        if self.debug:
            print(f"DEBUG: {message}")

    def start(self) -> None:
        """Start the Puya daemon (puyad) process."""
        cmd = ["poetry", "run", "puyad"]

        print(f"Starting Puya daemon with command: {' '.join(cmd)}")

        try:
            # Start the process
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line buffered
            )

            self.is_running = True

            # Start threads to read stdout and stderr
            self.stdout_thread = threading.Thread(target=self._read_stdout)
            self.stdout_thread.daemon = True
            self.stdout_thread.start()

            self.stderr_thread = threading.Thread(target=self._read_stderr)
            self.stderr_thread.daemon = True
            self.stderr_thread.start()

            # Wait a moment for the daemon to initialize
            time.sleep(1)

            # Check if process is still running after initialization
            if self._check_process_running():
                return  # Success - daemon is running
            else:
                self._handle_startup_failure()

        except Exception as e:
            print(f"Error starting daemon process: {e}")
            self.is_running = False

    def _check_process_running(self) -> bool:
        """Check if the process is still running."""
        if not self.process:
            return False

        # Check if process has terminated
        return self.process.poll() is None

    def _handle_startup_failure(self) -> None:
        """Handle failure to start the daemon."""
        self.is_running = False
        print("Failed to start Puya daemon")
        if self.stderr_lines:
            print("Error output:")
            for line in self.stderr_lines:
                print(f"  {line}")

    def _read_stdout(self) -> None:
        """Read output from the daemon process stdout using LSP protocol."""
        if not self.process or not self.process.stdout:
            return

        # Read line by line for both regular stdout and Content-Length headers
        for line in iter(self.process.stdout.readline, ""):
            line = line.strip()

            # Debug output for troubleshooting
            self._debug_print(f"RAW STDOUT: {line!r}")

            # Handle Content-Length header line
            if line.startswith("Content-Length:"):
                try:
                    # Extract content length
                    content_length = int(line.split(":", 1)[1].strip())
                    self._debug_print(f"Found Content-Length: {content_length}")

                    # Read the next line (should be Content-Type or empty)
                    next_line = self.process.stdout.readline().strip()
                    self._debug_print(f"Next line after Content-Length: {next_line!r}")

                    # Read one more line which should be empty (CR+LF)
                    empty_line = self.process.stdout.readline()
                    self._debug_print(f"Empty line: {empty_line!r}")

                    # Now read exactly content_length bytes
                    content = ""
                    bytes_read = 0
                    while bytes_read < content_length:
                        char = self.process.stdout.read(1)
                        if not char:  # EOF
                            break
                        content += char
                        bytes_read += 1

                    self._debug_print(f"Read content ({bytes_read} bytes): {content}")

                    if content:
                        try:
                            # Parse as JSON-RPC response
                            data = json.loads(content)

                            # Check if it's a response with id field
                            if "id" in data:
                                print(f"Received JSON-RPC response: {content}")
                                response = parse_json(content)
                                self.response_queue.put(response)
                            else:
                                print(f"Received JSON-RPC notification: {content}")
                        except Exception as e:
                            print(f"Error parsing JSON-RPC response: {e}")
                except Exception as e:
                    print(f"Error processing LSP message: {e}")
            elif line:
                # Regular stdout output (not LSP)
                print(f"Received (stdout): {line}")

    def _read_stderr(self) -> None:
        """Read output from the daemon process stderr."""
        if not self.process or not self.process.stderr:
            return

        for line in iter(self.process.stderr.readline, ""):
            line = line.strip()
            if line:
                print(f"Received (stderr): {line}")
                self.stderr_lines.append(line)

                # Also try to extract JSON if present in the log message
                # This is a fallback in case the server is incorrectly sending responses to stderr
                try:
                    # Look for JSON in the line - common pattern in logs is "INFO: Sending data: {json}"
                    match = re.search(r"Sending data: ({.*})", line)
                    if match:
                        json_str = match.group(1)
                        self._debug_print(f"Found JSON in stderr: {json_str}")
                        data = json.loads(json_str)

                        if "id" in data and "result" in data:
                            print(f"Found JSON-RPC response in stderr: {json_str}")
                            response = parse_json(json_str)
                            self.response_queue.put(response)
                except Exception as e:
                    # Just ignore errors in this fallback path
                    self._debug_print(f"Error extracting JSON from stderr: {e}")

    def send_request(self, method: str, params: dict[str, Any] | None = None) -> Ok | Error | None:
        """Send a JSON-RPC request to the daemon and wait for a response.

        Args:
            method: The JSON-RPC method to call (e.g., "analyse").
            params: The parameters to send with the request.

        Returns:
            The response from the daemon, or None if there was an error.
        """
        # First check if process is still running
        if not self._check_process_running():
            print("Daemon process has terminated unexpectedly")
            self.is_running = False
            return None

        if not self.is_running or not self.process or not self.process.stdin:
            print("Daemon not running")
            return None

        # Clear any previous responses
        while not self.response_queue.empty():
            self.response_queue.get_nowait()

        # Use sequential request ID
        request_id = self.request_id
        self.request_id += 1  # Increment for next request

        # Create a manual JSON-RPC request to ensure params is always included
        json_request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params if params is not None else {},  # Always include params
        }

        # Convert the request to JSON string
        request_str = json.dumps(json_request)

        # Format according to LSP protocol (Content-Length header + double CRLF + content)
        lsp_message = f"Content-Length: {len(request_str)}\r\n\r\n{request_str}"

        print(f"Sending LSP message:\n{lsp_message}")

        try:
            # Send the request
            self.process.stdin.write(lsp_message)
            self.process.stdin.flush()
        except BrokenPipeError:
            print("Error: Broken pipe - daemon process may have terminated")
            self.is_running = False
            return None
        except OSError as e:
            print(f"Error communicating with daemon: {e}")
            self.is_running = False
            return None

        # Wait for the response (with timeout)
        try:
            response = self.response_queue.get(timeout=10)
            return response
        except queue.Empty:
            print("Timed out waiting for response")
            return None

    def analyse(self, awst_path: str, compilation_set: dict[str, str]) -> dict[str, Any] | None:
        """Send an analyse request to the daemon.

        Args:
            awst_path: Path to the AWST JSON file.
            compilation_set: Dictionary mapping compilation unit names to file paths.

        Returns:
            The analysis result, or None if there was an error.
        """
        try:
            # Read the AWST file
            with open(awst_path) as f:
                awst_json = json.loads(f.read())

            # Convert compilation_set paths to Path objects if they're strings
            path_compilation_set = {}
            for key, value in compilation_set.items():
                if isinstance(value, str):
                    path_compilation_set[key] = str(Path(value))
                else:
                    path_compilation_set[key] = value

            # Create the params for the JSON-RPC request
            params = {"awst": awst_json, "compilation_set": path_compilation_set}

            # Send the request
            response = self.send_request("analyse", params)
            if response is not None and isinstance(response, Ok):
                return response.result
            elif response is not None and isinstance(response, Error):
                print(f"Error during analysis: {response.message}")
            return None
        except FileNotFoundError as e:
            print(f"Error: File not found - {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in input file - {e}")
            return None
        except Exception as e:
            print(f"Error during analysis: {e}")
            return None

    def stop(self) -> None:
        """Stop the daemon process."""
        if self.is_running and self.process:
            print("Stopping Puya daemon")

            # Force terminate if running
            if self._check_process_running():
                try:
                    self.process.terminate()
                    try:
                        self.process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        print("Process didn't terminate, sending KILL signal")
                        self.process.kill()
                        self.process.wait(timeout=2)
                except Exception as e:
                    print(f"Error terminating process: {e}")

            self.is_running = False
            print("Puya daemon stopped")


def main():
    """Main function to demonstrate usage of the PuyaClient."""
    # Create a client
    client = PuyaClient(debug=True)

    try:
        # Start the daemon
        print("Starting Puya daemon (puyad)...")
        client.start()

        if not client.is_running:
            print("Failed to start daemon. Please check the error output above.")
            return

        print("Daemon started successfully!")

        # Wait to ensure daemon is fully initialized
        print("Waiting for daemon initialization...")
        time.sleep(2)

        # Example usage for analysis - uncomment and replace paths when needed
        # print("\nTesting analysis...")
        # awst_path = "path/to/awst.json"
        # compilation_set = {
        #     "unit1": "path/to/file1.py",
        #     "unit2": "path/to/file2.py"
        # }
        # result = client.analyse(awst_path, compilation_set)
        # if result:
        #     print(f"Analysis result: {json.dumps(result, indent=2)}")
        # else:
        #     print("Analysis failed")

        # Keep alive for interactive testing
        print("\nDaemon running. Press Ctrl+C to stop...")
        try:
            while client.is_running:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nExiting...")

    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        # Always stop the daemon
        client.stop()


if __name__ == "__main__":
    main()
