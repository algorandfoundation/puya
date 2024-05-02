import tomllib
import typing
from pathlib import Path

from hatchling.builders.config import BuilderConfigBound
from hatchling.builders.hooks.plugin.interface import BuildHookInterface
from packaging.version import Version

PROJECT_ROOT = Path(__file__).parent


class CustomBuildHook(BuildHookInterface[BuilderConfigBound]):
    def initialize(self, version: str, build_data: dict[str, typing.Any]) -> None:
        # only manipulate version during wheel builds
        if version != "standard":
            return
        algopy_version = _resolve_version_from_pyproject(
            PROJECT_ROOT / ".." / "stubs" / "pyproject.toml"
        )
        # determine the next version NOT supported by this package
        algopy_ex_version = Version(f"{algopy_version.major}.{algopy_version.minor + 1}.0")
        build_data["dependencies"] = [
            f"algorand-python>={algopy_version.major},<{algopy_ex_version}"
        ]


def _resolve_version_from_pyproject(pyproject_path: Path) -> Version:
    pyproject = tomllib.loads(pyproject_path.read_text())
    try:
        project = pyproject["project"]
    except KeyError:
        try:
            project = pyproject["tool"]["poetry"]
        except KeyError:
            project = {}

    try:
        version = project["version"]
    except KeyError as ex:
        raise ValueError(f"Could not determine version from {pyproject_path}") from ex

    return Version(version)
