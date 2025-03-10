# Puya Daemon Mode

Puya's daemon mode allows for much faster compilation by keeping the Python interpreter and Puya compiler loaded in memory between compilation requests. This significantly reduces the overhead of starting Python for each compilation, making it especially useful for:

-   Development workflows with frequent recompilation
-   Tools that need to compile Algorand Python contracts
-   Integration with IDEs or development environments

## Getting Started

### Starting the Daemon

You can start the daemon directly from the command line:

```bash
python -m puya --daemon --host=127.0.0.1 --port=8765
```

By default, the daemon will:

-   Listen on 127.0.0.1:8765
-   Save its PID to ~/.puya/daemon.pid
-   Use 'info' log level and 'default' log format

### Stopping the Daemon

You can stop the daemon explicitly:

```bash
python -m puya --daemon-stop --host=127.0.0.1 --port=8765
```

The daemon will:

1. Finish any pending compilation requests
2. Clean up the PID file
3. Shut down gracefully

### Command Line Options

The daemon supports several command line options:

| Option          | Description                             | Default            |
| --------------- | --------------------------------------- | ------------------ |
| `--daemon`      | Start in daemon mode                    | -                  |
| `--daemon-stop` | Stop the daemon                         | -                  |
| `--host`        | Host address to bind to                 | 127.0.0.1          |
| `--port`        | Port to listen on                       | 8765               |
| `--pid-file`    | Path to PID file                        | ~/.puya/daemon.pid |
| `--log-level`   | Log level (debug, info, warning, error) | info               |
| `--log-format`  | Log format (default, json)              | default            |

## Using with Python Code

### High-Level API

The simplest way to use the daemon is through the high-level API:

```python
from puya.main import compile_with_daemon_if_available

# Compile using the daemon if available, or fall back to direct compilation
result = compile_with_daemon_if_available(
    options_json="...",
    awst_json="...",
    source_annotations_json=None,  # Optional
    use_daemon=True,               # Whether to try using daemon at all
    auto_start_daemon=True,        # Start daemon if not running
)

print(f"Compilation successful: {result['success']}")
print(f"Used daemon: {result['used_daemon']}")
```

### Direct Daemon Client

For more control, you can use the daemon client directly:

```python
from puya.daemon_client import PuyaDaemonClient, ensure_daemon_running

# Ensure daemon is running
if ensure_daemon_running():
    client = PuyaDaemonClient()

    # Compile using the daemon
    result = client.compile_sync(
        options_json="...",
        awst_json="...",
        source_annotations_json=None  # Optional
    )

    print(f"Compilation result: {result}")

    # When done with the daemon
    # client.stop_server_sync()  # Uncomment to stop the daemon
```

### Health Checks and Management

The daemon_utils module provides utilities for managing the daemon:

```python
from puya.daemon_utils import check_daemon_health, start_daemon_process, terminate_daemon

# Check daemon health
health = check_daemon_health()
print(f"Daemon running: {health['responsive']}")

# Start daemon if needed
if not health['responsive']:
    success, error, pid = start_daemon_process()
    if success:
        print(f"Started daemon with PID {pid}")
    else:
        print(f"Failed to start daemon: {error}")

# Terminate daemon when done
if health['responsive']:
    success, message = terminate_daemon(force=False)
    print(f"Terminated: {success}, {message}")
```

## JSON-RPC API

The daemon uses WebSocket JSON-RPC for communication. The API supports the following methods:

### compile

Compiles Algorand Python code using the provided inputs.

**Parameters:**

-   `options_json` - JSON string containing compilation options
-   `awst_json` - JSON string containing the AWST
-   `source_annotations_json` - (Optional) JSON string containing source annotations

**Example:**

```json
{
    "jsonrpc": "2.0",
    "method": "compile",
    "params": {
        "options_json": "...",
        "awst_json": "...",
        "source_annotations_json": "..."
    },
    "id": 1
}
```

### ping

Check if the daemon is responsive.

**Example:**

```json
{
    "jsonrpc": "2.0",
    "method": "ping",
    "params": {},
    "id": 1
}
```

### stop

Stop the daemon.

**Example:**

```json
{
    "jsonrpc": "2.0",
    "method": "stop",
    "params": {},
    "id": 1
}
```

## PyInstaller Compatibility

The daemon mode is designed to work with PyInstaller-bundled Puya. All paths are resolved relative to the executable, and the daemon creates its PID file in a user-specific location by default.

When using the PyInstaller-bundled version, the same command-line interface is available:

```bash
puya --daemon
puya --daemon-stop
```

## Performance Considerations

-   The first compilation after starting the daemon may be slightly slower as the daemon initializes
-   Subsequent compilations will be much faster as the Python interpreter and Puya compiler are already loaded
-   The daemon uses a small amount of memory while idle (~50-100MB), but this is typically much less overhead than starting Python for each compilation

## Security Considerations

By default, the daemon only listens on localhost (127.0.0.1) which restricts access to the local machine. If you need to expose the daemon to other machines:

1. Use the `--host` parameter to specify the network interface
2. Consider setting up appropriate network security (firewall rules, etc.)
3. Be aware that anyone with access to the daemon can trigger compilations and potentially access files on the server

## Example Usage

See the `examples/using_daemon.py` file for complete examples of using the daemon mode.
