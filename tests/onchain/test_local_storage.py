import random

import algokit_utils as au

from tests import EXAMPLES_DIR
from tests.utils import get_local_state_delta_as_dict
from tests.utils.deployer import Deployer

_LOCAL_STATE_DIR = EXAMPLES_DIR / "local_state"


def test_local_storage(deployer_o: Deployer) -> None:
    result = deployer_o.create_with_op_up(
        _LOCAL_STATE_DIR / "local_state_contract.py",
        num_op_ups=0,
        on_complete=au.OnApplicationComplete.OptIn,
    )
    client = result.client
    sender = deployer_o.account.addr

    default_value = b"this is a default"
    stored_value = b"testing 123"

    # get_data_with_default returns default when no data set
    get_data_with_default_result_1 = client.send.bare.call(
        _bare_args_rand_note(args=[b"get_data_with_default", default_value])
    )
    assert get_data_with_default_result_1.confirmation.logs == [default_value]

    # set_data stores the value
    set_data_result = client.send.bare.call(_bare_args_rand_note(args=[b"set_data", stored_value]))
    local_state_delta = get_local_state_delta_as_dict(
        set_data_result.confirmation.local_state_delta
    )
    assert local_state_delta == {sender: {b"local": stored_value}}

    # get_data_with_default now returns stored value
    get_data_with_default_result_2 = client.send.bare.call(
        _bare_args_rand_note(args=[b"get_data_with_default", default_value])
    )
    assert get_data_with_default_result_2.confirmation.logs == [stored_value]

    # get_guaranteed_data returns stored value
    get_guaranteed_data_result = client.send.bare.call(
        _bare_args_rand_note(args=[b"get_guaranteed_data"])
    )
    assert get_guaranteed_data_result.confirmation.logs == [stored_value]

    # get_data_or_assert returns stored value
    get_data_or_assert_result = client.send.bare.call(
        _bare_args_rand_note(args=[b"get_data_or_assert"])
    )
    assert get_data_or_assert_result.confirmation.logs == [stored_value]

    # delete_data removes the value
    delete_data_result = client.send.bare.call(au.AppClientBareCallParams(args=[b"delete_data"]))
    local_state_delta = get_local_state_delta_as_dict(
        delete_data_result.confirmation.local_state_delta
    )
    # action 3 = delete, value is None
    assert local_state_delta == {sender: {b"local": None}}


def test_local_storage_with_offsets(deployer_o: Deployer) -> None:
    result = deployer_o.create_with_op_up(
        _LOCAL_STATE_DIR / "local_state_with_offsets.py",
        num_op_ups=0,
        on_complete=au.OnApplicationComplete.OptIn,
    )
    client = result.client
    sender = deployer_o.account.addr

    index_one = (1).to_bytes(8, "big")
    default_value = b"this is a default"
    stored_value = b"testing 123"

    # get_data_with_default returns default when no data set
    get_data_with_default_result_1 = client.send.bare.call(
        _bare_args_rand_note(
            args=[index_one, b"get_data_with_default", default_value],
            account_references=[sender],
        )
    )
    assert get_data_with_default_result_1.confirmation.logs == [default_value]

    # set_data stores the value
    set_data_result = client.send.bare.call(
        _bare_args_rand_note(
            args=[index_one, b"set_data", stored_value],
            account_references=[sender],
        )
    )
    local_state_delta = get_local_state_delta_as_dict(
        set_data_result.confirmation.local_state_delta
    )
    assert local_state_delta == {sender: {b"local": stored_value}}

    # get_data_with_default now returns stored value
    get_data_with_default_result_2 = client.send.bare.call(
        _bare_args_rand_note(
            args=[index_one, b"get_data_with_default", default_value],
            account_references=[sender],
        )
    )
    assert get_data_with_default_result_2.confirmation.logs == [stored_value]

    # get_guaranteed_data returns stored value
    get_guaranteed_data_result = client.send.bare.call(
        _bare_args_rand_note(
            args=[index_one, b"get_guaranteed_data"],
            account_references=[sender],
        )
    )
    assert get_guaranteed_data_result.confirmation.logs == [stored_value]

    # get_data_or_assert returns stored value
    get_data_or_assert_result = client.send.bare.call(
        _bare_args_rand_note(
            args=[index_one, b"get_data_or_assert"],
            account_references=[sender],
        )
    )
    assert get_data_or_assert_result.confirmation.logs == [stored_value]

    # delete_data removes the value
    delete_data_result = client.send.bare.call(
        _bare_args_rand_note(
            args=[index_one, b"delete_data"],
            account_references=[sender],
        )
    )
    local_state_delta = get_local_state_delta_as_dict(
        delete_data_result.confirmation.local_state_delta
    )
    # action 3 = delete, value is None
    assert local_state_delta == {sender: {b"local": None}}


def _bare_args_rand_note(
    *, args: list[bytes], account_references: list[str] | None = None
) -> au.AppClientBareCallParams:
    return au.AppClientBareCallParams(
        args=args, account_references=account_references, note=random.randbytes(8)
    )
