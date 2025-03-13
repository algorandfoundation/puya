import io
import sys

# Force UTF-8 for stdout and stderr
sys.stdout = io.TextIOWrapper(
    sys.stdout.buffer, encoding="utf-8", errors="backslashreplace", line_buffering=True
)
sys.stderr = io.TextIOWrapper(
    sys.stderr.buffer, encoding="utf-8", errors="backslashreplace", line_buffering=True
)
