import pathlib
import sys

_VENDOR_PATH = pathlib.Path(__file__).parent / "_vendor"

sys.path.insert(0, str(_VENDOR_PATH))
