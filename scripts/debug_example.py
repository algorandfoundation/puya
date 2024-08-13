import sys
from pathlib import Path

from puya import log
from puya.options import PuyaOptions
from puyapy.compile import compile_to_teal


def main(example: str) -> None:
    log.configure_logging(min_log_level=log.LogLevel.warning)
    options = PuyaOptions()

    options.paths = [Path(example).resolve()]
    options.debug_level = 1
    options.optimization_level = 1
    options.output_teal = True
    options.output_awst = True
    options.output_ssa_ir = True
    options.output_destructured_ir = True
    options.output_optimization_ir = True
    options.output_memory_ir = True
    options.output_arc32 = True
    options.out_dir = Path("out")
    options.output_client = True

    compile_to_teal(options)


if __name__ == "__main__":
    main(sys.argv[1])
