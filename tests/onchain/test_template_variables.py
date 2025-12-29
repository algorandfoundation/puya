import random

import algokit_utils as au
import pytest
from algokit_abi.abi import ABIType

from tests import TEST_CASES_DIR
from tests.utils.compile import compile_arc56


def test_template_variables(localnet: au.AlgorandClient, account: au.AddressWithSigners) -> None:
    app_spec = compile_arc56(TEST_CASES_DIR / "template_variables")

    tuple_bytes = _encode_arc4("(uint64,uint64)", [1, 2])
    named_tuple_bytes = _encode_arc4("(uint64,uint64)", [3, 4])
    struct_bytes = _encode_arc4("(uint64,uint64)", [5, 6])

    # Create factory and compile with template values
    factory = au.AppFactory(
        au.AppFactoryParams(
            algorand=localnet,
            app_spec=app_spec,
            default_sender=account.addr,
            default_signer=account.signer,
        )
    )

    # Create app with template values
    client, _ = factory.send.bare.create(
        au.AppFactoryCreateParams(note=random.randbytes(8)),
        compilation_params=au.AppClientCompilationParams(
            deploy_time_params={
                "TMPL_SOME_BYTES": b"Hello I'm a variable",
                "TMPL_SOME_BIG_UINT": (1337).to_bytes(length=2),
                "TMPL_TUPLE": tuple_bytes,
                "TMPL_NAMED_TUPLE": named_tuple_bytes,
                "TMPL_STRUCT": struct_bytes,
            },
            updatable=True,
            deletable=True,
        ),
    )

    def call(method: str) -> au.ABIValue:
        result = client.send.call(
            au.AppClientMethodCallParams(method=method, note=random.randbytes(8))
        )
        return result.abi_return

    # Verify initial template values
    get_bytes = call("get_bytes")
    assert get_bytes == b"Hello I'm a variable"

    get_uint = call("get_big_uint")
    assert get_uint == 1337

    get_tuple = call("get_a_tuple")
    assert get_tuple == (1, 2), "expected correct tuple template var"

    get_named_tuple = call("get_a_named_tuple")
    # Named tuple returns as dict due to ARC-56 struct handling
    assert get_named_tuple == {"a": 3, "b": 4}, "expected correct named tuple template var"

    get_struct = call("get_a_struct")
    # Struct returns as dict
    assert get_struct == {"a": 5, "b": 6}, "expected correct struct template var"

    client.send.bare.update(
        compilation_params=au.AppClientCompilationParams(
            deploy_time_params={
                "TMPL_SOME_BYTES": b"Updated variable",
                "TMPL_SOME_BIG_UINT": (0).to_bytes(length=2),
                "TMPL_TUPLE": tuple_bytes,
                "TMPL_NAMED_TUPLE": named_tuple_bytes,
                "TMPL_STRUCT": struct_bytes,
            },
            updatable=False,
            deletable=True,
        ),
    )

    # Verify updated template values
    get_bytes = call("get_bytes")
    assert get_bytes == b"Updated variable"

    get_uint = call("get_big_uint")
    assert get_uint == 0

    # Test that update fails when contract was previously marked as not updatable
    with pytest.raises(au.LogicError, match=r"// TMPL_UPDATABLE\s+assert\s+<-- Error"):
        client.send.bare.update(
            compilation_params=au.AppClientCompilationParams(
                deploy_time_params={
                    "TMPL_SOME_BYTES": b"Updated variable",
                    "TMPL_SOME_BIG_UINT": (0).to_bytes(length=2),
                    "TMPL_TUPLE": tuple_bytes,
                    "TMPL_NAMED_TUPLE": named_tuple_bytes,
                    "TMPL_STRUCT": struct_bytes,
                },
                updatable=True,
                deletable=True,
            )
        )

    # Delete the app
    client.send.bare.delete(
        au.AppClientBareCallParams(note=random.randbytes(8)),
    )


def _encode_arc4(arc4_type: str, value: object) -> bytes:
    return ABIType.from_string(arc4_type).encode(value)
