import itertools
import typing
from collections import Counter

from puya.errors import CodeError, InternalError
from puya.ir.types_ import AVMBytesEncoding
from puya.parse import SourceLocation
from puya.teal import models
from puya.utils import Address, coalesce, method_selector_hash, unique

_T = typing.TypeVar("_T")


def gather_program_constants(program: models.TealProgram) -> None:
    # collect constants & template vars
    all_ints = list[int | str]()
    all_bytes = list[bytes | str]()
    bytes_encodings = dict[bytes | str, AVMBytesEncoding]()
    tmpl_locs = dict[bytes | int | str, SourceLocation | None]()

    # collect constants
    for block in itertools.chain.from_iterable(sub.blocks for sub in program.all_subroutines):
        for idx, op in enumerate(block.ops):
            # replace Method & Address constants with Byte before gathering
            match op:
                case models.Method(value=method_value):
                    op = block.ops[idx] = models.Byte(
                        value=method_selector_hash(method_value),
                        encoding=AVMBytesEncoding.base16,
                        comment=op.teal(),
                        stack_manipulations=op.stack_manipulations,
                        source_location=op.source_location,
                    )
                case models.Address(value=address_value, source_location=loc):
                    address = Address.parse(address_value)
                    if not address.is_valid:
                        raise InternalError(f"Invalid address literal: {address_value}", loc)
                    op = block.ops[idx] = models.Byte(
                        value=address.public_key,
                        encoding=AVMBytesEncoding.base32,
                        comment=op.teal(),
                        stack_manipulations=op.stack_manipulations,
                        source_location=op.source_location,
                    )
            match op:
                case models.Int(value=int_or_alias):
                    all_ints.append(_resolve_teal_alias(int_or_alias))
                case models.Byte(value=bytes_value) as byte:
                    all_bytes.append(bytes_value)
                    # preserve bytes encoding if it matches
                    if bytes_encodings.setdefault(bytes_value, byte.encoding) != byte.encoding:
                        bytes_encodings[bytes_value] = AVMBytesEncoding.base16
                # put template vars in constant blocks regardless of optimization level
                case models.TemplateVar(name=name, op_code=op_code):
                    # capture first defined tmpl location
                    tmpl_locs[name] = tmpl_locs.get(name) or op.source_location
                    match op_code:
                        case "int":
                            all_ints.append(name)
                        case "byte":
                            all_bytes.append(name)
                            bytes_encodings[name] = AVMBytesEncoding.base16
                        case _:
                            typing.assert_never(op_code)

    all_templates = unique(val for val in (*all_ints, *all_bytes) if isinstance(val, str))
    int_block = _sort_and_filter_constants(all_ints)
    byte_block = _sort_and_filter_constants(all_bytes)

    assert all(
        t in int_block or t in byte_block for t in all_templates
    ), "expected all template variables to be in constant block"
    # insert constant blocks
    entry_block = program.main.blocks[0]
    if byte_block:
        entry_block.ops.insert(
            0,
            models.BytesBlock(
                constants={b: (bytes_encodings[b], tmpl_locs.get(b)) for b in byte_block},
                source_location=None,
            ),
        )
    if int_block:
        entry_block.ops.insert(
            0,
            models.IntBlock(
                constants={i: tmpl_locs.get(i) for i in int_block}, source_location=None
            ),
        )

    # replace constants and template vars with constant load ops
    for block in itertools.chain.from_iterable(sub.blocks for sub in program.all_subroutines):
        for idx, op in enumerate(block.ops):
            match op:
                case models.Int(value=int_value):
                    comment = coalesce(
                        op.comment,
                        int_value if isinstance(int_value, str) else None,
                        str(int_value),
                    )
                    int_value = _resolve_teal_alias(int_value)
                    try:
                        const_index = int_block[int_value]
                    except KeyError:
                        block.ops[idx] = models.PushInt(
                            value=int_value,
                            stack_manipulations=op.stack_manipulations,
                            source_location=op.source_location,
                            comment=comment,
                        )
                    else:
                        block.ops[idx] = models.IntC(
                            index=const_index,
                            stack_manipulations=op.stack_manipulations,
                            source_location=op.source_location,
                            comment=comment,
                        )
                case models.Byte(value=bytes_value) as byte_op:
                    try:
                        const_index = byte_block[bytes_value]
                    except KeyError:
                        block.ops[idx] = models.PushBytes(
                            value=bytes_value,
                            encoding=byte_op.encoding,
                            stack_manipulations=op.stack_manipulations,
                            source_location=op.source_location,
                            comment=op.comment,
                        )
                    else:
                        block.ops[idx] = models.BytesC(
                            index=const_index,
                            stack_manipulations=op.stack_manipulations,
                            source_location=op.source_location,
                            comment=op.comment or " ".join(map(str, op.immediates)),
                        )
                case models.TemplateVar(name=name, op_code=op_code):
                    match op_code:
                        case "int":
                            block.ops[idx] = models.IntC(
                                index=int_block[name],
                                stack_manipulations=op.stack_manipulations,
                                source_location=op.source_location,
                                comment=op.comment or name,
                            )
                        case "byte":
                            block.ops[idx] = models.BytesC(
                                index=byte_block[name],
                                stack_manipulations=op.stack_manipulations,
                                source_location=op.source_location,
                                comment=op.comment or name,
                            )
                        case _:
                            typing.assert_never(op_code)


def _sort_and_filter_constants(values: list[_T | str]) -> dict[_T | str, int]:
    value_frequencies = {
        value: freq
        for value, freq in Counter(values).most_common()
        if (freq > 1 or isinstance(value, str))
    }
    # filter constants based on their size * frequency when used as a constant vs inline
    freq_idx = 0
    ordered_values = list(value_frequencies)
    while freq_idx < len(ordered_values):
        value = ordered_values[freq_idx]
        if not isinstance(value, str):
            encoded_size = _encoded_size(value)
            const_usage_size = 1 if freq_idx < 4 else 2
            inline_usage_size = 1 + encoded_size
            freq = value_frequencies[value]
            # include constant block size in consideration if only one value
            block_size = 2 if len(ordered_values) == 1 else 0
            inline = inline_usage_size * freq
            const = const_usage_size * freq + encoded_size + block_size
            if inline <= const:
                ordered_values.pop(freq_idx)
                continue
        freq_idx += 1

    # ensure any template variables that sit beyond MAX_NUMBER_CONSTANTS are always included
    overflow_template_vars = [
        value for value in ordered_values[models.MAX_NUMBER_CONSTANTS :] if isinstance(value, str)
    ]
    if len(overflow_template_vars) > models.MAX_NUMBER_CONSTANTS:
        # this doesn't have to be an error as the only consequence of not having all template vars
        # in the constant block is that it breaks the debug mapping assumptions
        # however for now it is easier to just fail, as this many template variables is unlikely
        raise CodeError(f"cannot exceed {models.MAX_NUMBER_CONSTANTS} template values")
    constants = (
        *ordered_values[: models.MAX_NUMBER_CONSTANTS - len(overflow_template_vars)],
        *overflow_template_vars,
    )
    assert len(constants) <= models.MAX_NUMBER_CONSTANTS, "constant block size exceeded"
    return {value: index for index, value in enumerate(constants)}


def _encoded_size(value: object) -> int:
    # varuint encodes 7 bits per byte
    if isinstance(value, int):
        # max accounts for 0, which still requires at least 1 byte
        return max(1, (value.bit_length() + 6) // 7)
    elif isinstance(value, bytes):
        return _encoded_size(len(value)) + len(value)
    else:
        raise TypeError(f"unencodable type: {value!r}")


def _resolve_teal_alias(value: int | str) -> int:
    return models.TEAL_ALIASES[value] if isinstance(value, str) else value
