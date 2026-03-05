import base64
from pathlib import Path
from random import randbytes

import algokit_utils as au

from shared import (
    assert_equal,
    compile_contract,
    load_app_spec,
    print_header,
    print_info,
    print_step,
    print_success,
    shorten_address,
)

print_header("Example 16 — Governance DAO")

# Step 1: Compile the contract
print_step(1, "Compiling contract...")
example_dir = Path(__file__).parent
out_dir = compile_contract(example_dir)
print_success("Contract compiled")

# Step 2: Load app spec
print_step(2, "Loading app spec...")
app_spec = load_app_spec(out_dir, "GovernanceDAO")
print_success("App spec loaded")

# Step 3: Connect to LocalNet
print_step(3, "Connecting to LocalNet...")
algod_config = au.ClientManager.get_default_localnet_config("algod")
algod = au.ClientManager.get_algod_client(algod_config)
algorand = au.AlgorandClient(au.AlgoSdkClients(algod=algod))
print_success("Connected to LocalNet")

# Step 4: Fund deployer account
print_step(4, "Funding deployer account...")
creator = algorand.account.localnet_dispenser()
algorand.account.set_signer_from_account(creator)
print_success(f"Deployer funded: {shorten_address(creator.addr)}")

# Step 5: Deploy the contract
print_step(5, "Deploying GovernanceDAO...")
factory = au.AppFactory(
    au.AppFactoryParams(
        algorand=algorand,
        app_spec=app_spec,
        default_sender=creator.addr,
        default_signer=creator.signer,
    )
)
client, _ = factory.send.create(
    au.AppFactoryCreateMethodCallParams(
        method="create(uint64)void",
        args=[3],  # quorum = 3
        note=randbytes(8),
    )
)
print_success(f"Contract deployed — App ID: {client.app_id}, quorum=3")

# Step 6: Fund app for box storage MBR
print_step(6, "Funding app for box storage MBR...")
algorand.account.ensure_funded(
    account_to_fund=client.app_address,
    dispenser_account=creator,
    min_spending_balance=au.AlgoAmount.from_micro_algo(1_000_000),
)
print_success(f"Funded app {shorten_address(client.app_address)}")


# --- Helpers ---
def addr_to_bytes(addr: str) -> bytes:
    return base64.b32decode(addr + "======")[:32]


def proposal_box_key(pid: int) -> bytes:
    return b"p_" + pid.to_bytes(8, "big")


def vote_box_key(pid: int, addr: str) -> bytes:
    return b"v" + pid.to_bytes(8, "big") + addr_to_bytes(addr)


ITXN_FEE = au.AlgoAmount.from_micro_algo(1000)

# Step 7: Create first proposal
print_step(7, "Creating proposal: 'Increase staking rewards by 5%'")
resp = client.send.call(
    au.AppClientMethodCallParams(
        method="create_proposal(string)uint64",
        args=["Increase staking rewards by 5%"],
        box_references=[proposal_box_key(0), "active"],
        extra_fee=ITXN_FEE * 3,
        note=randbytes(8),
    )
)
assert_equal(resp.abi_return, 0, "first proposal id")
print_success("Proposal created — ID: 0")

# Step 8: Create voter accounts
print_step(8, "Creating 4 voter accounts...")
voters = []
for i in range(4):
    voter = algorand.account.random()
    algorand.account.ensure_funded(
        account_to_fund=voter.addr,
        dispenser_account=creator,
        min_spending_balance=au.AlgoAmount.from_algo(1),
    )
    algorand.account.set_signer_from_account(voter)
    voters.append(voter)
    print_info(f"Voter {i}: {shorten_address(voter.addr)}")
print_success("4 voter accounts created and funded")

# Step 9: Vote on proposal 0 (3 yes, 1 no)
print_step(9, "Voting on proposal 0 (3 yes, 1 no)...")
votes = [True, True, True, False]
for i, (voter, in_favor) in enumerate(zip(voters, votes)):
    client.send.call(
        au.AppClientMethodCallParams(
            method="vote(uint64,bool)void",
            args=[0, in_favor],
            sender=voter.addr,
            box_references=[
                proposal_box_key(0),
                vote_box_key(0, voter.addr),
            ],
            extra_fee=ITXN_FEE * 3,
            note=randbytes(8),
        )
    )
    label = "YES" if in_favor else "NO"
    print_info(f"Voter {i} voted {label}")
print_success("All 4 votes cast on proposal 0")

# Step 10: Test vote deduplication
print_step(10, "Testing vote deduplication...")
try:
    client.send.call(
        au.AppClientMethodCallParams(
            method="vote(uint64,bool)void",
            args=[0, True],
            sender=voters[0].addr,
            box_references=[
                proposal_box_key(0),
                vote_box_key(0, voters[0].addr),
            ],
            extra_fee=ITXN_FEE * 3,
            note=randbytes(8),
        )
    )
    raise AssertionError("Should have failed - duplicate vote")
except Exception as e:
    if "already voted" in str(e):
        print_success("Duplicate vote correctly rejected")
    else:
        raise

# Step 11: Read proposal and verify tallies
print_step(11, "Reading proposal tallies...")
resp = client.send.call(
    au.AppClientMethodCallParams(
        method="get_proposal(uint64)(string,address,uint64,uint64,bool,bool)",
        args=[0],
        box_references=[proposal_box_key(0)],
        note=randbytes(8),
    )
)
proposal = resp.abi_return
assert isinstance(proposal, dict)
assert_equal(proposal["yes_votes"], 3, "yes votes")
assert_equal(proposal["no_votes"], 1, "no votes")
assert_equal(proposal["executed"], False, "not yet executed")
assert_equal(proposal["rejected"], False, "not yet rejected")
print_info(f"Title: {proposal['title']}")
print_success("Proposal tallies verified (3 yes, 1 no)")

# Step 12: Execute proposal 0 (passes: 3 yes > 1 no, quorum=3 met)
print_step(12, "Executing proposal 0 (should pass)...")
resp = client.send.call(
    au.AppClientMethodCallParams(
        method="execute(uint64)bool",
        args=[0],
        box_references=[proposal_box_key(0)],
        extra_fee=ITXN_FEE * 3,
        note=randbytes(8),
    )
)
assert_equal(resp.abi_return, True, "proposal passed")

# Verify executed state
resp = client.send.call(
    au.AppClientMethodCallParams(
        method="get_proposal(uint64)(string,address,uint64,uint64,bool,bool)",
        args=[0],
        box_references=[proposal_box_key(0)],
        note=randbytes(8),
    )
)
proposal = resp.abi_return
assert isinstance(proposal, dict)
assert_equal(proposal["executed"], True, "proposal is now executed")
print_success("Proposal 0 executed and verified")

# Step 13: Create and reject a second proposal
print_step(13, "Creating and rejecting a second proposal...")
resp = client.send.call(
    au.AppClientMethodCallParams(
        method="create_proposal(string)uint64",
        args=["Reduce validator count"],
        box_references=[proposal_box_key(1), "active"],
        extra_fee=ITXN_FEE * 3,
        note=randbytes(8),
    )
)
assert_equal(resp.abi_return, 1, "second proposal id")
print_success("Proposal created — ID: 1")

# Vote 1 yes, 3 no on proposal 1
for i, (voter, in_favor) in enumerate(zip(voters, [False, False, False, True])):
    client.send.call(
        au.AppClientMethodCallParams(
            method="vote(uint64,bool)void",
            args=[1, in_favor],
            sender=voter.addr,
            box_references=[
                proposal_box_key(1),
                vote_box_key(1, voter.addr),
            ],
            extra_fee=ITXN_FEE * 3,
            note=randbytes(8),
        )
    )
print_success("All 4 voters voted on proposal 1 (1 yes, 3 no)")

# Execute proposal 1 (should reject: 1 yes < 3 no)
resp = client.send.call(
    au.AppClientMethodCallParams(
        method="execute(uint64)bool",
        args=[1],
        box_references=[proposal_box_key(1)],
        extra_fee=ITXN_FEE * 3,
        note=randbytes(8),
    )
)
assert_equal(resp.abi_return, False, "proposal rejected")

# Verify rejected state
resp = client.send.call(
    au.AppClientMethodCallParams(
        method="get_proposal(uint64)(string,address,uint64,uint64,bool,bool)",
        args=[1],
        box_references=[proposal_box_key(1)],
        note=randbytes(8),
    )
)
proposal = resp.abi_return
assert isinstance(proposal, dict)
assert_equal(proposal["rejected"], True, "proposal is now rejected")
print_success("Proposal 1 rejected and verified")

# Step 14: Verify active proposals list (DynamicArray)
print_step(14, "Verifying active proposals list (arc4.DynamicArray)...")
resp = client.send.call(
    au.AppClientMethodCallParams(
        method="get_active_proposals()uint64[]",
        args=[],
        box_references=["active"],
        note=randbytes(8),
    )
)
assert_equal(resp.abi_return, [0, 1], "active proposals list")
print_success("Active proposals list verified: [0, 1]")

print_header("All assertions passed!")
