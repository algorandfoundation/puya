#!/bin/bash
set -e

# PyInstaller options
CMD="pyinstaller --clean --onedir --name puya --noconfirm src/puya/__main__.py --add-data './src/puya/ir/_puya_lib.awst.json:puya/ir/' --exclude-module puyapy --exclude-module colorama --exclude-module mypy_extensions --optimize=2"

# Print the command for debugging
echo "Executing: $CMD"

# Run PyInstaller
eval $CMD

echo "PyInstaller build completed successfully"
