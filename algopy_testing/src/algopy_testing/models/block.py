from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import algopy


class Block:
    @staticmethod
    def blk_seed(a: algopy.UInt64 | int, /) -> algopy.Bytes:
        from algopy_testing import get_test_context, op

        context = get_test_context()

        try:
            index = int(a)
            return op.itob(context._blocks[index]["seed"])
        except KeyError as e:
            raise KeyError(f"Block {a} not set") from e

    @staticmethod
    def blk_timestamp(a: algopy.UInt64 | int, /) -> algopy.UInt64:
        import algopy

        from algopy_testing import get_test_context

        context = get_test_context()

        try:
            index = int(a)
            return algopy.UInt64(context._blocks[index]["timestamp"])
        except KeyError as e:
            raise KeyError(f"Block {a} not set") from e
