from pathlib import Path

import algokit_utils as au
import pytest

from tests import FROM_AWST_DIR
from tests.from_awst.util import compile_contract_and_clients


@pytest.mark.localnet
def test_compile_and_run(
    localnet: au.AlgorandClient,
    account: au.AddressWithSigners,
) -> None:
    test_dir = Path(__file__).parent
    out_dir = test_dir / "out"

    compile_contract_and_clients(
        algorand=localnet,
        account=account,
        awst_path=FROM_AWST_DIR / "emit" / "module.awst.json",
        compilation_set={
            "tests/approvals/arc-28-events.algo.ts::EventEmitter": out_dir,
        },
    )
