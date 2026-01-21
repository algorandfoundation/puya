import subprocess
from pathlib import Path

from tests import FROM_AWST_DIR


def test_compile() -> None:
    # testing compilation of an AWST (based off of test_cases/loop_else/loop_else.py),
    # manually edited to have Blocks with repeat labels and Goto nodes targetting
    # nonexistant labels

    this_dir = Path(__file__).parent
    result = subprocess.run(
        [
            "puya",
            f"--awst={FROM_AWST_DIR / 'label_validation' / 'module.awst.json'}",
            "--options=options.json",
        ],
        check=False,
        text=True,
        capture_output=True,
        cwd=this_dir,
    )
    assert result.returncode != 0, "compilation should fail"

    # reason of failure must be label validation
    assert (
        "block has duplicate label repeat_label" in result.stdout
    ), "repeated block labels not caught during AWST validation"
    assert (
        "label target nonexistent_label does not exist" in result.stdout
    ), "a Goto targetting a nonexistent label was not caught during AWST validation"
