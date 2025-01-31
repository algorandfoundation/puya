import base64
import itertools
import typing
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from importlib.metadata import version as metadata_version

from cattrs.preconf.json import make_converter
from packaging import version

from puya import (
    arc56_models as models,
    log,
)
from puya.artifact_metadata import (
    ARC4ABIMethod,
    ARC4BareMethod,
    ARC4Struct,
    ContractMetaData,
    ContractState,
    MethodArgDefault,
    MethodArgDefaultConstant,
    MethodArgDefaultFromMethod,
    MethodArgDefaultFromState,
)
from puya.awst.nodes import (
    AppStorageKind,
    ARC4CreateOption,
)
from puya.compilation_artifacts import CompiledProgram, DebugInfo
from puya.utils import unique

# TODO: use puya once the backend is shipped as separate package
_ALGOPY_VERSION = version.parse(metadata_version("puyapy"))
logger = log.get_logger(__name__)


def create_arc56_json(
    *,
    metadata: ContractMetaData,
    approval_program: CompiledProgram,
    clear_program: CompiledProgram,
    template_prefix: str,
) -> str:
    assert approval_program.debug_info is not None
    assert clear_program.debug_info is not None

    converter = make_converter(omit_if_default=True)
    bare_methods = [m for m in metadata.arc4_methods if isinstance(m, ARC4BareMethod)]
    abi_methods = [m for m in metadata.arc4_methods if isinstance(m, ARC4ABIMethod)]

    # use shorter name for structs unless there is a collision
    aliases = _StructAliases(metadata.structs.values())

    schema = metadata.state_totals
    app_spec = models.Contract(
        arcs=(22, 28),
        name=metadata.name,
        desc=metadata.description,
        networks={},
        structs={
            aliases.resolve(n): [
                models.StructField(
                    name=e.name,
                    type=aliases.resolve(e.struct) or e.type,
                )
                for e in s.fields
            ]
            for n, s in metadata.structs.items()
        },
        methods=[
            models.Method(
                name=m.name,
                desc=m.desc,
                args=[
                    models.MethodArg(
                        type=a.type_,
                        name=a.name,
                        desc=a.desc,
                        struct=aliases.resolve(a.struct),
                        defaultValue=_encode_default_arg(a.client_default),
                    )
                    for a in m.args
                ],
                returns=models.MethodReturns(
                    type=m.returns.type_,
                    desc=m.returns.desc,
                    struct=aliases.resolve(m.returns.struct),
                ),
                actions=_method_actions(m),
                readonly=m.readonly,
                events=[_struct_to_event(aliases, struct) for struct in m.events],
                # left for users to fill in for now
                recommendations=models.MethodRecommendations(
                    innerTransactionCount=None,
                    boxes=None,
                    accounts=None,
                    apps=None,
                    assets=None,
                ),
            )
            for m in abi_methods
        ],
        state=models.ContractState(
            schema={
                "global": {"ints": schema.global_uints, "bytes": schema.global_bytes},
                "local": {"ints": schema.local_uints, "bytes": schema.local_bytes},
            },
            keys={
                "global": _storage_keys(aliases, metadata.global_state),
                "local": _storage_keys(aliases, metadata.local_state),
                "box": _storage_keys(aliases, metadata.boxes),
            },
            maps={
                # note: at present there is no way of defining global/local maps
                "global": _storage_maps(aliases, metadata.global_state),
                "local": _storage_maps(aliases, metadata.local_state),
                "box": _storage_maps(aliases, metadata.boxes),
            },
        ),
        bareActions=_combine_actions(list(map(_method_actions, bare_methods))),
        sourceInfo={
            "approval": models.ProgramSourceInfo(
                sourceInfo=_get_source_info(approval_program.debug_info),
                pcOffsetMethod="cblocks" if approval_program.debug_info.op_pc_offset else "none",
            ),
            "clear": models.ProgramSourceInfo(
                sourceInfo=_get_source_info(clear_program.debug_info),
                pcOffsetMethod="cblocks" if clear_program.debug_info.op_pc_offset else "none",
            ),
        },
        source={
            "approval": _encode_str(approval_program.teal_src),
            "clear": _encode_str(clear_program.teal_src),
        },
        byteCode=(
            {
                "approval": _encode_bytes(approval_program.bytecode),
                "clear": _encode_bytes(clear_program.bytecode),
            }
            if approval_program.bytecode and clear_program.bytecode
            else None
        ),
        compilerInfo=(
            _compiler_info() if approval_program.bytecode and clear_program.bytecode else None
        ),
        events=[
            _struct_to_event(aliases, struct)
            for struct in unique(
                e for m in metadata.arc4_methods if isinstance(m, ARC4ABIMethod) for e in m.events
            )
        ],
        templateVariables={
            name.removeprefix(template_prefix): models.TemplateVariable(
                type=aliases.resolve(metadata.template_variable_types[name]),
                value=(
                    _encode_bytes(value.to_bytes(length=8) if isinstance(value, int) else value)
                    if value is not None
                    else None
                ),
            )
            for program in (approval_program, clear_program)
            for name, value in program.template_variables.items()
        },
        # TODO: provide a way for contracts to declare "public" scratch vars
        scratchVariables=None,
    )
    return converter.dumps(app_spec, indent=4)


def _get_source_info(debug_info: DebugInfo) -> Sequence[models.SourceInfo]:
    errors = defaultdict[str, list[int]](list)
    for pc, event in debug_info.pc_events.items():
        if error := event.get("error"):
            errors[error].append(pc)
    return [
        models.SourceInfo(
            pc=errors[error],
            errorMessage=error,
        )
        for error in sorted(errors)
    ]


class _StructAliases:
    def __init__(self, structs: Iterable[ARC4Struct]) -> None:
        alias_to_fullname = dict[str, str]()
        for struct in structs:
            alias = (
                struct.fullname
                if struct.name in alias_to_fullname or struct.name in models.AVMType
                else struct.name
            )
            alias_to_fullname[alias] = struct.fullname
        self.aliases = {v: k for k, v in alias_to_fullname.items()}

    @typing.overload
    def resolve(self, struct: str) -> str: ...

    @typing.overload
    def resolve(self, struct: None) -> None: ...

    def resolve(self, struct: str | None) -> str | None:
        if struct is None:
            return None
        return self.aliases.get(struct, struct)


def _struct_to_event(structs: _StructAliases, struct: ARC4Struct) -> models.Event:
    return models.Event(
        name=structs.resolve(struct.name),
        desc=struct.desc,
        args=[
            models.EventArg(
                name=f.name,
                type=f.type,
                struct=structs.resolve(f.struct),
            )
            for f in struct.fields
        ],
    )


def _storage_keys(
    structs: _StructAliases, state: Mapping[str, ContractState]
) -> models.StorageKeys:
    return {
        n: models.StorageKey(
            desc=m.description,
            keyType=structs.resolve(m.arc56_key_type),
            valueType=structs.resolve(m.arc56_value_type),
            key=_encode_bytes(m.key_or_prefix),
        )
        for n, m in state.items()
        if not m.is_map
    }


def _storage_maps(
    structs: _StructAliases, state: Mapping[str, ContractState]
) -> models.StorageMaps:
    return {
        n: models.StorageMap(
            desc=m.description,
            keyType=structs.resolve(m.arc56_key_type),
            valueType=structs.resolve(m.arc56_value_type),
            prefix=_encode_bytes(m.key_or_prefix),
        )
        for n, m in state.items()
        if m.is_map
    }


def _method_actions(method: ARC4BareMethod | ARC4ABIMethod) -> models.MethodActions:
    return models.MethodActions(
        create=[
            oca.name
            for oca in method.allowed_completion_types
            if method.create != ARC4CreateOption.disallow and allowed_create_oca(oca.name)
        ],
        call=[
            oca.name
            for oca in method.allowed_completion_types
            if method.create != ARC4CreateOption.require and allowed_call_oca(oca.name)
        ],
    )


def _encode_default_arg(default: MethodArgDefault | None) -> models.MethodArgDefaultValue | None:
    match default:
        case None:
            return None
        case MethodArgDefaultConstant(data=data, type_=type_string):
            return models.MethodArgDefaultValue(
                data=_encode_bytes(data),
                type=type_string,
                source=models.DefaultValueSource.literal,
            )
        case MethodArgDefaultFromState(key=key, kind=kind, key_type=key_type):
            match kind:
                case AppStorageKind.account_local:
                    source = models.DefaultValueSource.local_
                case AppStorageKind.app_global:
                    source = models.DefaultValueSource.global_
                case AppStorageKind.box:
                    source = models.DefaultValueSource.box
                case unexpected:
                    typing.assert_never(unexpected)
            return models.MethodArgDefaultValue(
                data=_encode_bytes(key), type=key_type, source=source
            )
        case MethodArgDefaultFromMethod(signature=signature):
            return models.MethodArgDefaultValue(
                data=signature,
                source=models.DefaultValueSource.method,
            )
        case unexpected:
            typing.assert_never(unexpected)


def _combine_actions(actions: Sequence[models.MethodActions]) -> models.MethodActions:
    return models.MethodActions(
        create=sorted(set(itertools.chain.from_iterable(a.create for a in actions))),
        call=sorted(set(itertools.chain.from_iterable(a.call for a in actions))),
    )


def allowed_create_oca(
    oca: str,
) -> typing.TypeGuard[typing.Literal["NoOp", "OptIn", "DeleteApplication"]]:
    return oca in ("NoOp", "OptIn", "DeleteApplication")


def allowed_call_oca(
    oca: str,
) -> typing.TypeGuard[
    typing.Literal["NoOp", "OptIn", "CloseOut", "UpdateApplication", "DeleteApplication"]
]:
    return oca in ("NoOp", "OptIn", "CloseOut", "UpdateApplication", "DeleteApplication")


def _encode_str(value: str) -> str:
    return _encode_bytes(value.encode("utf8"))


def _encode_bytes(value: bytes) -> str:
    return base64.b64encode(value).decode("utf-8")


def _compiler_info() -> models.CompilerInfo:
    return models.CompilerInfo(
        compiler="puya",
        compilerVersion=models.CompilerVersion(
            major=_ALGOPY_VERSION.major,
            minor=_ALGOPY_VERSION.minor,
            patch=_ALGOPY_VERSION.micro,
            commitHash=None,
        ),
    )
