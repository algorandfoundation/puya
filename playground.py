#!/usr/bin/env python3
import json
import queue
import re
import subprocess
import sys
import threading
import time
import statistics
import os
from pathlib import Path
from typing import Any, Dict

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
        debug: bool = False,  # Set default to False for benchmarking
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
        self.thread_data = []  # Store thread count data over time
        self.thread_monitor = None  # Thread for monitoring threads

    def _debug_print(self, message: str) -> None:
        """Print debug message if debug is enabled."""
        if self.debug:
            print(f"DEBUG: {message}")

    def start(self) -> None:
        """Start the Puya daemon (puyad) process."""
        # Use the direct puyad command instead of puya --daemon
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

            # Start thread monitoring
            self.thread_monitor = threading.Thread(target=self._monitor_threads)
            self.thread_monitor.daemon = True
            self.thread_monitor.start()

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

    def _monitor_threads(self) -> None:
        """Monitor thread information of the daemon process.
        Uses system tools to get thread count where available.
        """
        if not self.process:
            return
        
        try:
            # Get process PID
            pid = self.process.pid
            
            while self.is_running:
                try:
                    # Use ps command to get thread count on Unix-like systems
                    if sys.platform != "win32":
                        # Different ps commands for different Unix platforms
                        if sys.platform == "darwin":  # macOS
                            # On macOS, use -M to show threads or thcount if available
                            # Try thcount first (newer macOS versions)
                            ps_cmd = ["ps", "-p", str(pid), "-o", "thcount"]
                            result = subprocess.run(ps_cmd, capture_output=True, text=True)
                            
                            if result.returncode == 0:
                                # Parse the output - first line is header, second is the thread count
                                lines = result.stdout.strip().split('\n')
                                if len(lines) >= 2:
                                    try:
                                        thread_count = int(lines[1].strip())
                                    except ValueError:
                                        # Fallback to counting threads manually with -M option
                                        ps_cmd = ["ps", "-M", "-p", str(pid)]
                                        result = subprocess.run(ps_cmd, capture_output=True, text=True)
                                        if result.returncode == 0:
                                            # Count lines minus the header line
                                            thread_count = len(result.stdout.strip().split('\n')) - 1
                                        else:
                                            thread_count = -1
                                else:
                                    thread_count = -1
                            else:
                                # Try alternative approach with -M flag to list all threads
                                ps_cmd = ["ps", "-M", "-p", str(pid)]
                                result = subprocess.run(ps_cmd, capture_output=True, text=True)
                                if result.returncode == 0:
                                    # Count lines minus the header line
                                    thread_count = len(result.stdout.strip().split('\n')) - 1
                                else:
                                    thread_count = -1
                        else:  # Linux and other Unix
                            # Get thread count using nlwp on Linux
                            ps_cmd = ["ps", "-o", "nlwp", "-p", str(pid)]
                            result = subprocess.run(ps_cmd, capture_output=True, text=True)
                            
                            if result.returncode == 0:
                                # Parse the output - first line is header, second is the thread count
                                lines = result.stdout.strip().split('\n')
                                if len(lines) >= 2:
                                    thread_count = int(lines[1].strip())
                                else:
                                    thread_count = -1
                            else:
                                thread_count = -1
                        
                        # Get memory info - works on both macOS and Linux
                        memory_cmd = ["ps", "-o", "rss", "-p", str(pid)]
                        mem_result = subprocess.run(memory_cmd, capture_output=True, text=True)
                        
                        if mem_result.returncode == 0:
                            lines = mem_result.stdout.strip().split('\n')
                            if len(lines) >= 2:
                                # RSS is in KB, convert to MB
                                memory_kb = int(lines[1].strip())
                                memory_mb = memory_kb / 1024
                            else:
                                memory_mb = -1
                        else:
                            memory_mb = -1
                        
                        # Print debug info to help troubleshoot
                        if self.debug and thread_count > 0:
                            self._debug_print(f"Detected {thread_count} threads for process {pid}")
                            
                        # For simplicity, estimate CPU usage based on the difference in CPU times
                        # This is a rough approximation
                        cpu_percent = 0
                    else:
                        # On Windows, we don't have an easy equivalent without psutil
                        # Just use placeholder values
                        thread_count = -1
                        cpu_percent = 0
                        memory_mb = -1
                    
                    # Store the data
                    self.thread_data.append({
                        'timestamp': time.time(),
                        'thread_count': thread_count,
                        'cpu_percent': cpu_percent,
                        'memory_mb': memory_mb
                    })
                    
                    time.sleep(0.5)  # Sample every 500ms to reduce overhead
                except Exception as e:
                    self._debug_print(f"Error in thread monitoring: {e}")
                    # Don't break, just continue with next sample
            
        except Exception as e:
            self._debug_print(f"Error monitoring threads: {e}")

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
        # if self.stderr_lines:
        #     print("Error output:")
        #     for line in self.stderr_lines:
        #         print(f"  {line}")

    def _read_stdout(self) -> None:
        """Read output from the daemon process stdout using LSP protocol."""
        if not self.process or not self.process.stdout:
            return

        # Read line by line for both regular stdout and Content-Length headers
        for line in iter(self.process.stdout.readline, ""):
            line = line.strip()

            # Debug output for troubleshooting
            # self._debug_print(f"RAW STDOUT: {line!r}")

            # Handle Content-Length header line
            if line.startswith("Content-Length:"):
                try:
                    # Extract content length
                    content_length = int(line.split(":", 1)[1].strip())
                    self._debug_print(f"Found Content-Length: {content_length}")

                    # Read the next line (should be Content-Type or empty)
                    next_line = self.process.stdout.readline().strip()
                    # self._debug_print(f"Next line after Content-Length: {next_line!r}")

                    # Read one more line which should be empty (CR+LF)
                    empty_line = self.process.stdout.readline()
                    # self._debug_print(f"Empty line: {empty_line!r}")

                    # Now read exactly content_length bytes
                    content = ""
                    bytes_read = 0
                    while bytes_read < content_length:
                        char = self.process.stdout.read(1)
                        if not char:  # EOF
                            break
                        content += char
                        bytes_read += 1

                    # self._debug_print(f"Read content ({bytes_read} bytes): {content}")

                    if content:
                        try:
                            # Parse as JSON-RPC response
                            data = json.loads(content)

                            # Check if it's a response with id field
                            if "id" in data:
                                # self._debug_print(f"Received JSON-RPC response: {content}")
                                response = parse_json(content)
                                self.response_queue.put(response)
                            else:
                                # self._debug_print(f"Received JSON-RPC notification: {content}")
                                pass
                        except Exception as e:
                            print(f"Error parsing JSON-RPC response: {e}")
                except Exception as e:
                    print(f"Error processing LSP message: {e}")
            elif line and self.debug:
                # Regular stdout output (not LSP)
                print(f"Received (stdout): {line}")

    def _read_stderr(self) -> None:
        """Read output from the daemon process stderr."""
        if not self.process or not self.process.stderr:
            return

        for line in iter(self.process.stderr.readline, ""):
            line = line.strip()
            if line:
                # Only print stderr in debug mode to avoid cluttering during benchmarking
                if self.debug:
                    # print(f"Received (stderr): {line}")
                    pass
                self.stderr_lines.append(line)

                # Also try to extract JSON if present in the log message
                # This is a fallback in case the server is incorrectly sending responses to stderr
                try:
                    # Look for JSON in the line - common pattern in logs is "INFO: Sending data: {json}"
                    match = re.search(r"Sending data: ({.*})", line)
                    if match:
                        json_str = match.group(1)
                        # self._debug_print(f"Found JSON in stderr: {json_str}")
                        data = json.loads(json_str)

                        if "id" in data and "result" in data:
                            # self._debug_print(f"Found JSON-RPC response in stderr: {json_str}")
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

        # self._debug_print(f"Sending LSP message:\n{lsp_message}")

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
    
    def get_thread_stats(self) -> Dict[str, Any]:
        """Get statistics about thread usage."""
        if not self.thread_data:
            return {"error": "No thread data collected"}
        
        # Filter out invalid data points (where we couldn't get the value)
        valid_thread_data = [data for data in self.thread_data if data["thread_count"] > 0]
        
        if not valid_thread_data:
            return {"error": "No valid thread data collected"}
        
        thread_counts = [data["thread_count"] for data in valid_thread_data]
        memory_mbs = [data["memory_mb"] for data in valid_thread_data if data["memory_mb"] > 0]
        
        stats = {
            "thread_count": {
                "min": min(thread_counts) if thread_counts else -1,
                "max": max(thread_counts) if thread_counts else -1,
                "avg": statistics.mean(thread_counts) if thread_counts else -1,
                "median": statistics.median(thread_counts) if thread_counts else -1
            },
            "samples": len(valid_thread_data)
        }
        
        # Add memory stats if available
        if memory_mbs:
            stats["memory_mb"] = {
                "min": min(memory_mbs),
                "max": max(memory_mbs),
                "avg": statistics.mean(memory_mbs),
                "median": statistics.median(memory_mbs)
            }
            
        return stats


def load_options_file(path: str) -> dict:
    """Load options from a JSON file.
    
    Args:
        path: Path to the options.json file
        
    Returns:
        Options dictionary
    """
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading options file: {e}")
        sys.exit(1)


def run_benchmark(client: PuyaClient, awst_path: str, compilation_set: dict[str, str], 
                 num_requests: int = 500) -> Dict[str, Any]:
    """Run a benchmark of multiple analyze requests.
    
    Args:
        client: The PuyaClient instance
        awst_path: Path to the AWST JSON file
        compilation_set: Dictionary mapping compilation unit names to file paths
        num_requests: Number of requests to send (default: 500)
        
    Returns:
        Dictionary with benchmark results
    """
    print(f"\nStarting benchmark with {num_requests} analyze requests...")
    
    results = []
    success_count = 0
    error_count = 0
    
    start_time = time.time()
    
    for i in range(num_requests):
        request_start = time.time()
        sys.stdout.write(f"\rRunning request {i+1}/{num_requests}...")
        sys.stdout.flush()
        
        result = client.analyse(awst_path, compilation_set)
        request_end = time.time()
        
        if result:
            success_count += 1
        else:
            error_count += 1
        
        results.append({
            "request_num": i+1,
            "success": result is not None,
            "duration": request_end - request_start
        })
    
    end_time = time.time()
    total_duration = end_time - start_time
    
    print("\nBenchmark completed!")
    
    # Calculate statistics
    durations = [r["duration"] for r in results]
    
    benchmark_results = {
        "total_requests": num_requests,
        "successful_requests": success_count,
        "failed_requests": error_count,
        "success_rate": (success_count / num_requests) * 100 if num_requests > 0 else 0,
        "total_duration": total_duration,
        "requests_per_second": num_requests / total_duration if total_duration > 0 else 0,
        "duration_stats": {
            "min": min(durations) if durations else 0,
            "max": max(durations) if durations else 0,
            "avg": statistics.mean(durations) if durations else 0,
            "median": statistics.median(durations) if durations else 0,
            "std_dev": statistics.stdev(durations) if len(durations) > 1 else 0
        }
    }
    
    return benchmark_results


def find_max_throughput(client: PuyaClient, awst_path: str, compilation_set: dict[str, str], 
                      timeout: int = 60) -> Dict[str, Any]:
    """Find the maximum throughput the server can handle.
    
    Args:
        client: The PuyaClient instance
        awst_path: Path to the AWST JSON file
        compilation_set: Dictionary mapping compilation unit names to file paths
        timeout: Maximum time to run the test in seconds
        
    Returns:
        Dictionary with throughput test results
    """
    print(f"\nStarting max throughput test (running for {timeout} seconds)...")
    
    start_time = time.time()
    end_time = start_time + timeout
    
    # Set up multiple worker threads to overwhelm the server
    request_queue = queue.Queue()
    result_queue = queue.Queue()
    stop_event = threading.Event()
    
    def worker():
        while not stop_event.is_set():
            try:
                result = client.analyse(awst_path, compilation_set)
                request_queue.put(1)  # Mark that a request was sent
                result_queue.put(1 if result else 0)  # Mark success/failure
            except Exception as e:
                print(f"Worker error: {e}")
                result_queue.put(0)  # Mark as failure
    
    # Start worker threads (use available CPU cores as a guide)
    workers = []
    # Use a sane default number of workers based on CPU count or hard-coded value
    try:
        # Try to get CPU count in a platform-independent way
        num_workers = os.cpu_count() or 4
        num_workers *= 2  # Double the number of available CPUs
    except:
        num_workers = 8  # Hard-coded fallback
            
    num_workers = min(num_workers, 32)  # Cap at 32 workers max
    
    print(f"Starting {num_workers} worker threads...")
    for _ in range(num_workers):
        t = threading.Thread(target=worker)
        t.daemon = True
        t.start()
        workers.append(t)
    
    # Print progress and collect stats
    try:
        while time.time() < end_time:
            time.sleep(1)
            elapsed = time.time() - start_time
            requests_processed = request_queue.qsize()
            rps = requests_processed / elapsed if elapsed > 0 else 0
            sys.stdout.write(f"\rElapsed: {elapsed:.1f}s, Requests: {requests_processed}, RPS: {rps:.2f}")
            sys.stdout.flush()
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    finally:
        print("\nStopping throughput test...")
        stop_event.set()
        
        # Give a moment for threads to finish
        time.sleep(1)
    
    # Calculate results
    total_elapsed = time.time() - start_time
    total_requests = request_queue.qsize()
    successful = sum(1 for _ in range(result_queue.qsize()) if result_queue.get() == 1)
    failures = total_requests - successful
    
    throughput_results = {
        "total_requests": total_requests,
        "successful_requests": successful,
        "failed_requests": failures,
        "success_rate": (successful / total_requests) * 100 if total_requests > 0 else 0,
        "total_duration": total_elapsed,
        "requests_per_second": total_requests / total_elapsed if total_elapsed > 0 else 0,
        "num_workers": num_workers
    }
    
    return throughput_results


def main():
    """Main function to benchmark the Puya daemon's analyze functionality."""
    # Create a client with debugging enabled to diagnose thread monitoring issues
    client = PuyaClient(debug=True)  # Set to True to see thread monitoring debug output

    # Check if we have required files
    awst_path = Path("module.awst.json")
    options_path = Path("options.json")
    
    if not awst_path.exists():
        print(f"Error: AWST file not found at {awst_path}")
        return
        
    if not options_path.exists():
        print(f"Error: Options file not found at {options_path}")
        return
    
    # Load options file to extract compilation_set
    options = load_options_file(str(options_path))
    compilation_set = options.get("compilation_set", {})
    
    if not compilation_set:
        print("Error: compilation_set not found in options.json")
        return
        
    print(f"Loaded compilation set: {compilation_set}")

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

        # Run a single analysis first to verify it works
        print("\nTesting a single analysis request...")
        result = client.analyse(str(awst_path), compilation_set)
        
        if result:
            print("Single analysis request successful!")
        else:
            print("Single analysis request failed, cannot continue benchmarking.")
            return
        
        # Run benchmark with 500 requests
        benchmark_results = run_benchmark(client, str(awst_path), compilation_set, 500)
        
        # Print benchmark results
        print("\n--- Benchmark Results ---")
        print(f"Total Requests: {benchmark_results['total_requests']}")
        print(f"Successful: {benchmark_results['successful_requests']} ({benchmark_results['success_rate']:.2f}%)")
        print(f"Failed: {benchmark_results['failed_requests']}")
        print(f"Total Duration: {benchmark_results['total_duration']:.2f} seconds")
        print(f"Requests per Second: {benchmark_results['requests_per_second']:.2f}")
        print("\nRequest Duration Statistics:")
        print(f"  Min: {benchmark_results['duration_stats']['min']:.4f} seconds")
        print(f"  Max: {benchmark_results['duration_stats']['max']:.4f} seconds")
        print(f"  Avg: {benchmark_results['duration_stats']['avg']:.4f} seconds")
        print(f"  Median: {benchmark_results['duration_stats']['median']:.4f} seconds")
        print(f"  Std Dev: {benchmark_results['duration_stats']['std_dev']:.4f} seconds")
        
        # Get thread statistics
        thread_stats = client.get_thread_stats()
        print("\n--- Thread Statistics ---")
        if "error" in thread_stats:
            print(f"Thread data collection error: {thread_stats['error']}")
            print(f"Total thread data points collected: {len(client.thread_data)}")
            print(f"Platform detected: {sys.platform}")
            
            # Display some raw data if available
            if client.thread_data:
                print("\nSample of raw thread data:")
                for i, data in enumerate(client.thread_data[:5]):  # Show first 5 samples
                    print(f"  Sample {i+1}: thread_count={data['thread_count']}, memory_mb={data['memory_mb']:.2f}")
                    
                # Count data points with valid and invalid thread counts
                valid_count = sum(1 for data in client.thread_data if data["thread_count"] > 0)
                invalid_count = sum(1 for data in client.thread_data if data["thread_count"] <= 0)
                print(f"\nValid thread count readings: {valid_count}")
                print(f"Invalid thread count readings: {invalid_count}")
        else:
            print(f"Thread Count: min={thread_stats['thread_count']['min']}, " +
                f"max={thread_stats['thread_count']['max']}, " +
                f"avg={thread_stats['thread_count']['avg']:.2f}, " +
                f"median={thread_stats['thread_count']['median']:.2f}")
            
            if "memory_mb" in thread_stats:
                print(f"Memory Usage: min={thread_stats['memory_mb']['min']:.2f} MB, " +
                    f"max={thread_stats['memory_mb']['max']:.2f} MB, " +
                    f"avg={thread_stats['memory_mb']['avg']:.2f} MB, " +
                    f"median={thread_stats['memory_mb']['median']:.2f} MB")
            
            print(f"Samples collected: {thread_stats['samples']}")
        
        # Run throughput test (max requests)
        print("\nRunning throughput test to find maximum request handling capacity...")
        throughput_results = find_max_throughput(client, str(awst_path), compilation_set, timeout=30)
        
        print("\n--- Throughput Test Results ---")
        print(f"Total Requests: {throughput_results['total_requests']}")
        print(f"Successful: {throughput_results['successful_requests']} ({throughput_results['success_rate']:.2f}%)")
        print(f"Failed: {throughput_results['failed_requests']}")
        print(f"Total Duration: {throughput_results['total_duration']:.2f} seconds")
        print(f"Maximum Requests per Second: {throughput_results['requests_per_second']:.2f}")
        print(f"Number of Workers: {throughput_results['num_workers']}")
        
        # Save detailed results to a file
        results_file = "benchmark_results.json"
        with open(results_file, "w") as f:
            json.dump({
                "benchmark": benchmark_results,
                "thread_stats": thread_stats,
                "throughput": throughput_results
            }, f, indent=2)
        
        print(f"\nDetailed results saved to {results_file}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Always stop the daemon
        client.stop()


if __name__ == "__main__":
    main()
