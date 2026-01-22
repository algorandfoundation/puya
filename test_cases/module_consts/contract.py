# ruff: noqa: T201, F403, F405, PLR0133

import typing

from algopy import Contract, Txn

import test_cases.module_consts.constants as consts
from test_cases.module_consts import constants, constants4
from test_cases.module_consts.constants import BANNED, EXT_ONE, EXT_ZERO
from test_cases.module_consts.constants2 import *
from test_cases.module_consts.constants3 import *

T = True and (1 == 1)


if typing.TYPE_CHECKING:
    TruthyType = bool | typing.Literal[0, 1]
    _T = typing.TypeVar("_T")

    def identity(x: _T) -> _T:
        return x

elif False:
    print("HOW DO I GET HERE")
elif 0 > 1:
    print("please sir can I have some more consistency")
else:
    SNEAKY_CONST = "so sneak"


NO = b'"no'
NOO = b"no'"
ZERO = ZER0 = 0  # lol
ZEROS = f"{ZERO:.3f}"
ONE = ZERO + (ZER0 * 2) + (2 - 1) // EXT_ONE
YES = "y" + "es"
AAAAAAAAAA = EXT_ZERO or "a" * 48
MAYBE = f"""{YES}
    or
        nooo
"""
BANNED_F = f"{BANNED!r}"
BANNED_F2 = f"{BANNED:2s}"
F_CODE = f"{'lol' if EXT_ONE else 'no'}"
MAYBE1 = f"{MAYBE}"
MAYBE2 = f'{MAYBE}"'
MAYBE3 = f"""{MAYBE}"""
MAYBE4 = f'''{MAYBE}"'''
MAYBE6 = rf"{MAYBE}"
MAYBE8 = rf'{MAYBE}"'
# fmt: off
MAYBE5 = fr"{MAYBE}"
MAYBE7 = fr'{MAYBE}"'
# fmt: on
MAYBE_MORE = f"{MAYBE} \
 maybe not"
TWO = consts.EXT_ONE + constants.EXT_ONE + consts.EXT_ZERO
EXT_NAME_REF_F_STR = f"{consts.BANNED}"
YES_TWICE_AND_NO = 2 * f"2{YES}" + f"1{NO!r}"
SHOULD_BE_1 = EXT_ONE if not typing.TYPE_CHECKING else EXT_ZERO
SHOULD_BE_0 = EXT_ONE if False else EXT_ZERO

STAR1 = USE_CONSTANTS2
STAR2 = USED_CONSTANTS3
# STAR3: str = USED_UNLISTED_CONSTANT3  # type: ignore[name-defined]
FOOOO = constants4.constants3.USED_CONSTANTS3

JOINED = ", ".join(["1", ZEROS])


yes_votes = 42_572_654
no_votes = 43_132_495
percentage = (100 * yes_votes) // (yes_votes + no_votes)
FORMATTED = f"{yes_votes:-9} YES votes  {percentage:2.2%}"


class MyContract(Contract):
    def approval_program(self) -> bool:
        assert Txn.num_app_args == 0, MAYBE_MORE
        assert Txn.sender != consts.HACKER, consts.HACKER
        return True

    def clear_state_program(self) -> bool:
        return True
