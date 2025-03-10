#!/bin/bash
set -e

PACKAGE_NAME=$1
ARTIFACTS_DIR=$2

ARCH=$(uname -m)
echo "Building Linux binary for $PACKAGE_NAME on $ARCH architecture"
echo "Artifacts will be saved to $ARTIFACTS_DIR"

# Install project dependencies
cd ${GITHUB_WORKSPACE}
poetry config virtualenvs.create false
poetry install --no-interaction --without=dev --with=cicd

# Build the binary
poetry run pyinstaller \
    --clean \
    --onedir \
    --name puya \
    --noconfirm src/puya/__main__.py \
    --add-data './src/puya/ir/_puya_lib.awst.json:puya/ir/' \
    --exclude-module colorama \
    --exclude-module mypy_extensions \
    --optimize=2

echo "Build completed successfully for $ARCH architecture"
