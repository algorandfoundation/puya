import algokit_utils as au

from tests import EXAMPLES_DIR
from tests.utils.deployer import Deployer
from tests.utils.merkle_tree import MerkleTree, sha_256_raw


def test_merkle(deployer: Deployer) -> None:
    test_tree = MerkleTree(
        [
            b"a",
            b"b",
            b"c",
            b"d",
            b"e",
        ]
    )

    result = deployer.create(
        EXAMPLES_DIR / "merkle",
        method="create",
        args={"root": test_tree.root},
    )
    client = result.client

    # proof comes first according to method signature
    proof = [list(h) for h in test_tree.get_proof(b"a")]
    leaf = list(sha_256_raw(b"a"))
    verify_result = client.send.call(
        au.AppClientMethodCallParams(
            method="verify",
            args=[proof, leaf],
        )
    )
    assert verify_result.abi_return is True
