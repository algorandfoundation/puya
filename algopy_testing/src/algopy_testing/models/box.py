from __future__ import annotations

from typing import TYPE_CHECKING

from algopy_testing.context import get_test_context

if TYPE_CHECKING:
    import algopy


class Box:
    @staticmethod
    def create(a: algopy.Bytes | bytes, b: algopy.UInt64 | int, /) -> bool:
        import algopy

        context = get_test_context()
        name_bytes = a.value if isinstance(a, algopy.Bytes) else a
        size = int(b)
        if not name_bytes or size > 32768:
            raise ValueError("Invalid box name or size")
        if context.get_box(name_bytes):
            return False
        context.set_box(name_bytes, b"\x00" * size)
        return True

    @staticmethod
    def delete(a: algopy.Bytes | bytes, /) -> bool:
        import algopy

        context = get_test_context()
        name_bytes = a.value if isinstance(a, algopy.Bytes) else a
        if context.get_box(name_bytes):
            context.clear_box(name_bytes)
            return True
        return False

    @staticmethod
    def extract(
        a: algopy.Bytes | bytes, b: algopy.UInt64 | int, c: algopy.UInt64 | int, /
    ) -> algopy.Bytes:
        import algopy

        context = get_test_context()
        name_bytes = a.value if isinstance(a, algopy.Bytes) else a
        start = int(b)
        length = int(c)
        box_content = context.get_box(name_bytes)
        if not box_content:
            raise ValueError("Box does not exist")
        return box_content[start : start + length]

    @staticmethod
    def get(a: algopy.Bytes | bytes, /) -> tuple[algopy.Bytes, bool]:
        import algopy

        context = get_test_context()
        name_bytes = a.value if isinstance(a, algopy.Bytes) else a
        box_content = context.get_box(name_bytes)
        return box_content, bool(box_content)

    @staticmethod
    def length(a: algopy.Bytes | bytes, /) -> tuple[algopy.UInt64, bool]:
        import algopy

        context = get_test_context()
        name_bytes = a.value if isinstance(a, algopy.Bytes) else a
        box_content = context.get_box(name_bytes)
        return algopy.UInt64(len(box_content)), bool(box_content)

    @staticmethod
    def put(a: algopy.Bytes | bytes, b: algopy.Bytes | bytes, /) -> None:
        import algopy

        context = get_test_context()
        name_bytes = a.value if isinstance(a, algopy.Bytes) else a
        content = b.value if isinstance(b, algopy.Bytes) else b
        existing_content = context.get_box(name_bytes)
        if existing_content and len(existing_content) != len(content):
            raise ValueError("New content length does not match existing box length")
        context.set_box(name_bytes, content)

    @staticmethod
    def replace(
        a: algopy.Bytes | bytes, b: algopy.UInt64 | int, c: algopy.Bytes | bytes, /
    ) -> None:
        import algopy

        context = get_test_context()
        name_bytes = a.value if isinstance(a, algopy.Bytes) else a
        start = int(b)
        new_content = c.value if isinstance(c, algopy.Bytes) else c
        box_content = context.get_box(name_bytes)
        if not box_content:
            raise ValueError("Box does not exist")
        if start + len(new_content) > len(box_content):
            raise ValueError("Replacement content exceeds box size")
        updated_content = (
            box_content[:start] + new_content + box_content[start + len(new_content) :]
        )
        context.set_box(name_bytes, updated_content)

    @staticmethod
    def resize(a: algopy.Bytes | bytes, b: algopy.UInt64 | int, /) -> None:
        import algopy

        context = get_test_context()
        name_bytes = a.value if isinstance(a, algopy.Bytes) else a
        new_size = int(b)
        if not name_bytes or new_size > 32768:
            raise ValueError("Invalid box name or size")
        box_content = context.get_box(name_bytes)
        if not box_content:
            raise ValueError("Box does not exist")
        if new_size > len(box_content):
            updated_content = box_content + b"\x00" * (new_size - len(box_content))
        else:
            updated_content = box_content[:new_size]
        context.set_box(name_bytes, updated_content)

    @staticmethod
    def splice(
        a: algopy.Bytes | bytes,
        b: algopy.UInt64 | int,
        c: algopy.UInt64 | int,
        d: algopy.Bytes | bytes,
        /,
    ) -> None:
        import algopy

        context = get_test_context()
        name_bytes = a.value if isinstance(a, algopy.Bytes) else a
        start = int(b)
        delete_count = int(c)
        insert_content = d.value if isinstance(d, algopy.Bytes) else d
        box_content = context.get_box(name_bytes)

        if not box_content:
            raise ValueError("Box does not exist")

        if start > len(box_content):
            raise ValueError("Start index exceeds box size")

        # Calculate the end index for deletion
        end = min(start + delete_count, len(box_content))

        # Construct the new content
        new_content = box_content[:start] + insert_content + box_content[end:]

        # Adjust the size if necessary
        if len(new_content) > len(box_content):
            # Truncate if the new content is too long
            new_content = new_content[: len(box_content)]
        elif len(new_content) < len(box_content):
            # Pad with zeros if the new content is too short
            new_content += b"\x00" * (len(box_content) - len(new_content))

        # Update the box with the new content
        context.set_box(name_bytes, new_content)
