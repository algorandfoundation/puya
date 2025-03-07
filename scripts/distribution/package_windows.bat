@echo off
echo import os, sys, io > hook-puya.py
echo # Set environment variables >> hook-puya.py
echo os.environ["PYTHONIOENCODING"] = "utf-8" >> hook-puya.py
echo os.environ["PYTHONUTF8"] = "1" >> hook-puya.py
echo os.environ["PYTHONLEGACYWINDOWSSTDIO"] = "0" >> hook-puya.py
echo os.environ["NO_COLOR"] = "1" >> hook-puya.py
echo # Direct stdout/stderr patching for Windows >> hook-puya.py
echo if sys.platform == 'win32': >> hook-puya.py
echo     try: >> hook-puya.py
echo         import colorama >> hook-puya.py
echo         colorama.deinit() # Ensure colorama doesn't attempt to initialize >> hook-puya.py
echo     except ImportError: >> hook-puya.py
echo         pass >> hook-puya.py
echo     # Force UTF-8 for stdout and stderr >> hook-puya.py
echo     sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='backslashreplace', line_buffering=True) >> hook-puya.py
echo     sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='backslashreplace', line_buffering=True) >> hook-puya.py

pyinstaller --clean --onedir --name puya --noconfirm src/puya/__main__.py --add-data ./src/puya/ir/_puya_lib.awst.json;puya/ir/ --exclude-module puyapy --exclude-module mypy_extensions --optimize=2 --hidden-import colorama --runtime-hook hook-puya.py

REM Clean up the hook file
del hook-puya.py
