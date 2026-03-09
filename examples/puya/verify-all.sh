#!/usr/bin/env bash
set -uo pipefail

cd "$(dirname "$0")"

EXAMPLES=(
    01-counter
    02-greeter
    03-logic-sig-gate
    04-type-explorer
    05-membership-registry
    06-key-value-store
    07-array-playground
    08-object-tuples
    09-token-manager
    10-multi-txn-distributor
    11-contract-factory
    12-event-logger
    13-inheritance-showcase
    14-crypto-vault
    15-dex-pool
    16-governance-dao
)

passed=0
failed=0
failures=()

echo "Running ${#EXAMPLES[@]} examples..."
echo

for example in "${EXAMPLES[@]}"; do
    printf "%-35s" "$example"
    if uv run python "$example/index.py" > /dev/null 2>&1; then
        echo "PASS"
        ((passed++))
    else
        echo "FAIL"
        ((failed++))
        failures+=("$example")
    fi
done

echo
echo "================================"
echo "Results: $passed passed, $failed failed"
echo "================================"

if [ "$failed" -gt 0 ]; then
    echo
    echo "Failures:"
    for f in "${failures[@]}"; do
        echo "  - $f"
    done
    exit 1
fi
