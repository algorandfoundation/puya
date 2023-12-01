import typing as t

_P = t.ParamSpec("_P")

_R = t.TypeVar("_R")

def subroutine(sub: t.Callable[_P, _R], /) -> t.Callable[_P, _R]: ...

# one day maybe we support inlining functions explicitly so the types can be a bit more lax,
# but that day is not today... e.g maybe there's a sort() function that acts more like a "macro",
# where you pass in the comparator (which is a function object so obviously not easy to support in
# a normal teal subroutine)
# def inline(sub: t.Callable[_P, _R], /) -> t.Callable[_P, _R]: ...
