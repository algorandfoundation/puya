#!/bin/bash

CMD="pyinstaller --clean --onedir --name puya --noconfirm src/puya/__main__.py --add-data './src/puya/ir/_puya_lib.awst.json:puya/ir/' --exclude-module puyapy --exclude-module colorama --exclude-module mypy_extensions --optimize=2"

if [ ! -z "$APPLE_BUNDLE_ID" ]; then
    CMD="$CMD --osx-bundle-identifier \"$APPLE_BUNDLE_ID\""
fi

if [ ! -z "$APPLE_CERT_ID" ]; then
    CMD="$CMD --codesign-identity \"$APPLE_CERT_ID\""
fi

if [ -f "./entitlements.xml" ]; then
    CMD="$CMD --osx-entitlements-file './entitlements.xml'"
fi

eval $CMD 
