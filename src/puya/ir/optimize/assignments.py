from puya import log
from puya.context import CompileContext
from puya.errors import InternalError
from puya.ir import encodings, models
from puya.ir.types_ import EncodedType, IRType, PrimitiveIRType, TupleIRType
from puya.ir.visitor_mem_replacer import MemoryReplacer

logger = log.get_logger(__name__)


def copy_propagation(_context: CompileContext, subroutine: models.Subroutine) -> bool:
    set_lookup = dict[models.Register, list[models.Register]]()
    all_equivalence_sets = list[list[models.Register]]()

    modified = False
    for block in subroutine.body:
        for op in block.ops.copy():
            match op:
                case models.Assignment(targets=[target], source=models.Register() as source):
                    try:
                        equiv_set = set_lookup[source]
                        assert source in equiv_set
                    except KeyError:
                        set_lookup[source] = equiv_set = [source]
                        all_equivalence_sets.append(equiv_set)
                    equiv_set.append(target)
                    set_lookup[target] = equiv_set
                    block.ops.remove(op)
                    modified = True

    replacements = dict[models.Register, models.Register]()
    for equivalence_set in all_equivalence_sets:
        assert len(equivalence_set) >= 2
        equiv_set_ids = ", ".join(x.local_id for x in equivalence_set)
        logger.debug(f"Found equivalence set: {equiv_set_ids}")

        parameters = [r for r in equivalence_set if r in subroutine.parameters]
        match parameters:
            case [param]:
                replacement = param
            case []:
                for reg in equivalence_set:
                    if models.TMP_VAR_INDICATOR not in reg.name:
                        replacement = reg
                        break
                else:  # fall back to first register if all are temp
                    replacement = equivalence_set[0]
            case _:
                raise InternalError("multiple parameters in the same equivalence set")
        logger.debug(f"selected {replacement} from equivalence set")
        for r in equivalence_set:
            if r is not replacement:
                replacements[r] = replacement

    for block in subroutine.body:
        for phi in block.phis.copy():
            # don't replace if phi.register is involved in an equivalence set
            if phi.register in set_lookup:
                continue
            try:
                (single_register,) = {replacements.get(arg.value, arg.value) for arg in phi.args}
            except ValueError:
                pass
            else:
                assert single_register not in replacements, "chained replacement detected"
                replacements[phi.register] = single_register
                block.phis.remove(phi)
                modified = True
    replaced = MemoryReplacer.apply(subroutine.body, replacements=replacements)
    if replaced:
        logger.debug(f"Copy propagation made {replaced} modifications")
        modified = True

    return modified


def encode_decode_pair_elimination(
    _context: CompileContext, subroutine: models.Subroutine
) -> bool:
    encodes_by_args = dict[
        tuple[models.Value, ...], list[tuple[models.Assignment, models.BytesEncode]]
    ]()
    encodes_by_target = dict[models.Register, models.BytesEncode]()
    decodes_by_arg = dict[models.Value, list[tuple[models.Assignment, models.DecodeBytes]]]()
    decodes_by_targets = dict[tuple[models.Register, ...], models.DecodeBytes]()
    modified = False
    for block in subroutine.body:
        for op in block.ops:
            if isinstance(op, models.Assignment):
                source = op.source
                if isinstance(source, models.BytesEncode):
                    encodes_by_args.setdefault(tuple(source.values), []).append((op, source))
                    (target,) = op.targets
                    encodes_by_target[target] = source
                elif isinstance(source, models.DecodeBytes):
                    decodes_by_arg.setdefault(source.value, []).append((op, source))
                    decodes_by_targets[tuple(op.targets)] = source

    # replace DecodeBytes(BytesEncode([*args])) with args where:
    #   - result IR type of decode is the input IR type of encode
    #   - encodings are equal (should always be true)
    #   - removing the round-trip won't result in the loss of any validation / asserts
    for encode_target, encode_op in encodes_by_target.items():
        encode_decodes = decodes_by_arg.get(encode_target, [])
        for encode_decode_assignment, encode_decode in encode_decodes:
            if (
                encode_decode.ir_type == encode_op.values_type
                and encode_decode.encoding == encode_op.encoding
                and _is_round_trip_safe(encode_decode.encoding, encode_decode.ir_type)
            ):
                logger.debug(
                    f"replacing redundant decode-of-encode with:"
                    f" {", ".join(map(str, encode_op.values))}"
                )
                modified = True
                if not isinstance(encode_decode.ir_type, TupleIRType):
                    (encode_decode_assignment.source,) = encode_op.values
                else:
                    encode_decode_assignment.source = models.ValueTuple(
                        values=encode_op.values,
                        ir_type=encode_decode.ir_type,
                        source_location=encode_decode_assignment.source_location,
                    )
    # replace BytesEncode(DecodeBytes(arg)) with arg where:
    #   - the result IR type of encode is in the input IR type of encode (should always be true)
    #   - the source encoding and target encoding are the same
    #   - removing the round-trip won't result in the loss of any validation / asserts
    for decode_targets, decode_op in decodes_by_targets.items():
        decode_encodes = encodes_by_args.get(decode_targets, [])
        for decode_encode_assignment, decode_encode in decode_encodes:
            if (
                decode_op.encoding == decode_encode.encoding
                and decode_op.ir_type == decode_encode.values_type
                and _is_round_trip_safe(decode_op.encoding, decode_op.ir_type)
            ):
                logger.debug(f"replacing redundant encode-of-decode with: {decode_op.value}")
                modified = True
                decode_encode_assignment.source = decode_op.value
    return modified


def _is_round_trip_safe(encoding: encodings.Encoding, native_type: IRType | TupleIRType) -> bool:
    match native_type:
        case EncodedType(encoding=ir_type_encoding):
            # TODO: maybe if both are encodings.BoolEncoding with different packings this
            #       would still be okay?
            return ir_type_encoding == encoding
        case PrimitiveIRType.bool:
            # there's only two valid bool values
            return True
        case PrimitiveIRType.string:
            # if the encoding has no length restrictions, this is fine,
            # there's no value validation here
            return (
                isinstance(encoding, encodings.ArrayEncoding)
                and encoding.size is None
                and encoding.element == encodings.UTF8Encoding()
            )
        case PrimitiveIRType.bytes:
            # if the encoding has no length restrictions, this is fine,
            # there's no value validation here
            return (
                isinstance(encoding, encodings.ArrayEncoding)
                and encoding.size is None
                and encoding.element == encodings.UIntEncoding(n=8)
            )
        case PrimitiveIRType.account:
            return (
                isinstance(encoding, encodings.ArrayEncoding)
                and encoding.size == 32
                and encoding.element == encodings.UIntEncoding(n=8)
            )
        case PrimitiveIRType.uint64:
            return isinstance(encoding, encodings.UIntEncoding) and encoding.n >= 64
        case TupleIRType(elements=native_elements):
            # okay if encoding is TupleEncoding and all elements are round-trip safe
            # when matched with the element IRType
            return isinstance(encoding, encodings.TupleEncoding) and all(
                _is_round_trip_safe(element_encoding, element_type)
                for element_encoding, element_type in zip(
                    encoding.elements, native_elements, strict=True
                )
            )
        case _:
            return False
