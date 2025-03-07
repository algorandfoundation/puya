import io
import os
import sys

# Set environment variables
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONLEGACYWINDOWSSTDIO"] = "0"
os.environ["NO_COLOR"] = "1"
# Direct stdout/stderr patching for Windows
if sys.platform == "win32":
    try:
        import colorama

        colorama.deinit()  # Ensure colorama doesn't attempt to initialize
    except ImportError:
        pass
    # Force UTF-8 for stdout and stderr
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="backslashreplace", line_buffering=True
    )
    sys.stderr = io.TextIOWrapper(
        sys.stderr.buffer, encoding="utf-8", errors="backslashreplace", line_buffering=True
    )
