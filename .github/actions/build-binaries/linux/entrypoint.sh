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
poetry install --no-interaction

# Build the binary
poetry run poe package_unix
echo "Build completed successfully for $ARCH architecture" 
