import typing

_T_co = typing.TypeVar("_T_co", covariant=True)

class _TemplateVarMethod(typing.Protocol[_T_co]):
    def __call__(self, variable_name: str, /, *, prefix: str = "TMPL_") -> _T_co: ...

class _TemplateVarGeneric(typing.Protocol):
    def __getitem__(self, _: type[_T_co]) -> _TemplateVarMethod[_T_co]: ...

TemplateVar: _TemplateVarGeneric = ...
"""Template variables can be used to represent a placeholder for a deploy-time provided value."""
