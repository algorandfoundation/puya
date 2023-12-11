import sys
from pathlib import Path

from puya.compile import compile_to_teal
from puya.logging_config import LogLevel, configure_logging
from puya.options import PuyaOptions


def main(example: str) -> None:
    configure_logging(min_log_level=LogLevel.debug)
    options = PuyaOptions()

    options.paths = [Path(example).resolve()]
    options.debug_level = 1
    options.optimization_level = 1
    options.output_teal = True
    options.output_awst = True
    options.output_ssa_ir = True
    options.output_final_ir = True
    options.output_optimization_ir = True
    options.output_cssa_ir = True
    options.output_parallel_copies_ir = True
    options.output_post_ssa_ir = True
    options.out_dir = Path("out")

    compile_to_teal(options)


if __name__ == "__main__":
    main(sys.argv[1])
