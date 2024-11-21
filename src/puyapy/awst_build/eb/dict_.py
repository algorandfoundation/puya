import typing
from collections.abc import Mapping

from puya import log
from puya.errors import CodeError
from puya.parse import SourceLocation
from puyapy.awst_build.eb._utils import constant_bool_and_error
from puyapy.awst_build.eb.interface import (
    InstanceBuilder,
    NodeBuilder,
)

logger = log.get_logger(__name__)


class DictLiteralBuilder(NodeBuilder):
    def __init__(self, mapping: Mapping[str, InstanceBuilder], location: SourceLocation):
        super().__init__(location)
        self._mapping = mapping

    @typing.override
    @property
    def pytype(self) -> None:
        return None

    @property
    def mapping(self) -> Mapping[str, InstanceBuilder]:
        return self._mapping

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> typing.Never:
        if name in dir(dict()):  # noqa: C408
            raise CodeError("method is not currently supported", location)
        raise CodeError("unrecognised member access", location)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        return constant_bool_and_error(value=bool(self._mapping), location=location, negate=negate)
