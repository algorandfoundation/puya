@echo off
pyinstaller --clean --onedir --name puya --noconfirm src/puya/__main__.py --add-data ./src/puya/ir/_puya_lib.awst.json;puya/ir/ --exclude-module puyapy --exclude-module mypy_extensions --optimize=2 --hidden-import colorama --runtime-hook scripts/distribution/hook_puya.py
