from pathlib import Path

import attrs
from algokit_algod_client import models as algod

from puyapy.parse import ParseResult, SourceDiscoveryMechanism
from puyapy.template import parse_template_key_value

SUFFIX_O0 = "_unoptimized"
SUFFIX_O1 = ""
SUFFIX_O2 = "_O2"


def narrowed_parse_result(parse_result: ParseResult, src_path: Path) -> ParseResult:
    filtered_ordered_modules = {
        name: sm
        for name, sm in parse_result.ordered_modules.items()
        if sm.path.resolve().is_relative_to(src_path.resolve())
        or sm.discovery_mechanism == SourceDiscoveryMechanism.dependency
    }
    return ParseResult(
        mypy_options=parse_result.mypy_options,
        ordered_modules=filtered_ordered_modules,
    )


@attrs.frozen
class PuyaTestCase:
    path: Path

    @property
    def root(self) -> Path:
        return self.path.parent

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def template_vars_path(self) -> Path | None:
        template_vars_path = self.path / "template.vars"
        return template_vars_path.resolve() if template_vars_path.exists() else None

    @property
    def id(self) -> str:
        return f"{self.root.stem}/{self.name}"


def load_template_vars(path: Path | None) -> tuple[str, dict[str, int | bytes]]:
    prefix = "TMPL_"
    prefix_prefix = "prefix="

    result = {}
    if path is not None:
        for line in path.read_text("utf8").splitlines():
            if line.startswith(prefix_prefix):
                prefix = line.removeprefix(prefix_prefix)
            else:
                key, value = parse_template_key_value(line)
                result[key] = value
    return prefix, result


def decode_logs(logs: list[bytes] | None, log_format: str) -> list[str | bytes | int]:
    logs = logs or []
    assert len(logs) == len(log_format)
    result = list[str | bytes | int]()

    for fmt, log in zip(log_format, logs, strict=True):
        match fmt:
            case "i":
                result.append(int.from_bytes(log, byteorder="big", signed=False))
            case "u":
                result.append(log.decode("utf-8"))
            case "b":
                result.append(log)
            case _:
                raise ValueError(f"Unexpected format: {fmt}")
    return result


def get_local_state_delta_as_dict(
    local_state_deltas: list[algod.AccountStateDelta] | None,
) -> dict[str, dict[bytes, bytes | int | None]]:
    return {lsd.address: get_state_delta_as_dict(lsd.delta) for lsd in local_state_deltas or []}


def get_state_delta_as_dict(
    state_deltas: list[algod.EvalDeltaKeyValue] | None,
) -> dict[bytes, bytes | int | None]:
    return {sd.key: _map_value(sd.value) for sd in state_deltas or []}


def _map_value(value: algod.EvalDelta) -> int | bytes | None:
    if value.action == 1:
        return value.bytes_
    elif value.action == 2:
        return value.uint
    elif value.action == 3:
        return None
    else:
        raise ValueError("unexpected EvalDelta action")
