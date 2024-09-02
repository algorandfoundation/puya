from pathlib import Path

from puyapy.options import PuyaPyOptions


def determine_out_dir(contract_path: Path, options: PuyaPyOptions) -> Path:
    if not options.out_dir:
        out_dir = contract_path
    else:
        # find input path the contract is relative to
        for src_path in options.paths:
            src_path = src_path.resolve()
            src_path = src_path if src_path.is_dir() else src_path.parent
            try:
                relative_path = contract_path.relative_to(src_path)
            except ValueError:
                continue
            # construct a path that maintains a hierarchy to src_path
            out_dir = options.out_dir / relative_path
            if not options.out_dir.is_absolute():
                out_dir = src_path / out_dir
            break
        else:
            # if not relative to any input path
            if options.out_dir.is_absolute():
                out_dir = options.out_dir / contract_path
            else:
                out_dir = contract_path / options.out_dir

    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir
