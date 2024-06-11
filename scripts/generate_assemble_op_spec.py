#!/usr/bin/env python3
import json
import subprocess
from pathlib import Path

from puya import log
from puya.ussemble.op_spec_models import ImmediateEnum, ImmediateKind, OpSpec

from scripts.transform_lang_spec import (
    LanguageSpec,
)

logger = log.get_logger(__name__)
VCS_ROOT = Path(__file__).parent.parent


def main() -> None:
    spec_path = VCS_ROOT / "langspec.puya.json"
    lang_spec_json = json.loads(spec_path.read_text(encoding="utf-8"))
    lang_spec = LanguageSpec.from_json(lang_spec_json)

    ops = build_op_spec(lang_spec)
    output_ops(ops)


def build_op_spec(lang_spec: LanguageSpec) -> dict[str, OpSpec]:
    ops = {}
    for op in sorted(lang_spec.ops.values(), key=lambda x: x.code):
        immediates = list[ImmediateKind | ImmediateEnum]()
        for imm in op.immediate_args:
            if imm.arg_enum is None:
                immediates.append(ImmediateKind[imm.immediate_type.name])
            else:
                immediates.append(
                    ImmediateEnum(
                        codes={e.name: e.value for e in lang_spec.arg_enums[imm.arg_enum]}
                    )
                )
        op_spec = OpSpec(name=op.name, code=op.code, immediates=immediates)
        ops[op_spec.name] = op_spec

    return ops


def output_ops(
    ops: dict[str, OpSpec],
) -> None:
    file: list[str] = [
        "from puya.ussemble.op_spec_models import ImmediateEnum, ImmediateKind, OpSpec",
        f"OP_SPECS = {ops!r}",
    ]

    output_path = VCS_ROOT / "src" / "puya" / "ussemble" / "op_spec.py"
    output_path.write_text("\n".join(file), encoding="utf-8")
    subprocess.run(["black", str(output_path)], check=True, cwd=VCS_ROOT)


if __name__ == "__main__":
    main()
