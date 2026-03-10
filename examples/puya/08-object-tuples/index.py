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
)

print_header("Example 08 — Object Tuples")

# Step 1: Compile the contract
print_step(1, "Compiling contract...")
example_dir = Path(__file__).parent
out_dir = compile_contract(example_dir)
print_success("Contract compiled")

# Step 2: Load app spec
print_step(2, "Loading app spec...")
app_spec = load_app_spec(out_dir, "ObjectTuples")
print_success("App spec loaded")

# Step 3: Connect to LocalNet
print_step(3, "Connecting to LocalNet...")
algod_config = au.ClientManager.get_default_localnet_config("algod")
algod = au.ClientManager.get_algod_client(algod_config)
algorand = au.AlgorandClient(au.AlgoSdkClients(algod=algod))
print_success("Connected to LocalNet")

# Step 4: Fund deployer account
print_step(4, "Funding deployer account...")
account = algorand.account.localnet_dispenser()
algorand.account.set_signer_from_account(account)
print_success(f"Deployer funded: {account.addr}")

# Step 5: Deploy the contract
print_step(5, "Deploying contract...")
factory = au.AppFactory(
    au.AppFactoryParams(
        algorand=algorand,
        app_spec=app_spec,
        default_sender=account.addr,
        default_signer=account.signer,
    )
)
client, result = factory.send.bare.create(au.AppFactoryCreateParams(note=randbytes(8)))
print_success(f"Contract deployed — App ID: {client.app_id}")


def call(method: str, args: list[object] | None = None) -> object:
    resp = client.send.call(
        au.AppClientMethodCallParams(
            method=method,
            args=args or [],
            note=randbytes(8),
        )
    )
    return resp.abi_return


# Step 6: Struct as params/returns — add_points
print_step(6, "Calling add_points((10,20), (30,40))...")
result = call("add_points((uint64,uint64),(uint64,uint64))(uint64,uint64)", [(10, 20), (30, 40)])
assert_equal(result, {"x": 40, "y": 60}, "add_points((10,20),(30,40))")
print_success("add_points returned { x: 40, y: 60 }")

# Step 7: GlobalState — set_point and get_point
print_step(7, "Calling set_point(5, 15) + get_point()...")
call("set_point(uint64,uint64)void", [5, 15])
result = call("get_point()(uint64,uint64)")
assert_equal(result, {"x": 5, "y": 15}, "get_point after set_point(5,15)")
print_success("set_point + get_point returned { x: 5, y: 15 }")

# Step 8: _replace() — translate_point
print_step(8, "Calling translate_point(10, 20)...")
result = call("translate_point(uint64,uint64)(uint64,uint64)", [10, 20])
assert_equal(result, {"x": 15, "y": 35}, "translate(5+10, 15+20)")
result = call("get_point()(uint64,uint64)")
assert_equal(result, {"x": 15, "y": 35}, "get_point after translate")
print_success("translate_point returned { x: 15, y: 35 }")

# Step 9: copy() — copy_and_scale
print_step(9, "Calling copy_and_scale(3)...")
result = call("copy_and_scale(uint64)(uint64,uint64)", [3])
assert_equal(result, {"x": 45, "y": 105}, "scale(15*3, 35*3)")
result = call("get_point()(uint64,uint64)")
assert_equal(result, {"x": 45, "y": 105}, "get_point after scale")
print_success("copy_and_scale returned { x: 45, y: 105 }")

# Step 10: Struct with String field — set_profile + get_profile
print_step(10, "Calling set_profile + get_profile...")
call("set_profile(string,uint64,uint64)void", ["Alice", 30, 100])
result = call("get_profile()(string,uint64,uint64)")
assert_equal(result, {"name": "Alice", "age": 30, "score": 100}, "get_profile(Alice)")
print_success("set_profile + get_profile returned Alice profile")

# Step 11: _replace preserves unchanged fields — update_score
print_step(11, "Calling update_score(500)...")
result = call("update_score(uint64)(string,uint64,uint64)", [500])
assert_equal(result, {"name": "Alice", "age": 30, "score": 500}, "update_score(500)")
print_info("  name and age preserved, only score updated")
result = call("get_profile()(string,uint64,uint64)")
assert_equal(result, {"name": "Alice", "age": 30, "score": 500}, "get_profile after update_score")
print_success("update_score preserved name/age, updated score to 500")

print_header("All assertions passed!")
