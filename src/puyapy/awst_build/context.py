import ast
import contextlib
import functools
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path

import attrs
import mypy.nodes
import mypy.options
import mypy.types

from puya import log
from puya.context import try_get_source
from puya.errors import CodeError, InternalError, log_exceptions
from puya.parse import SourceLocation
from puya.program_refs import ContractReference
from puya.utils import attrs_extend, coalesce, unique
from puyapy.awst_build import pytypes
from puyapy.models import ConstantValue, ContractFragmentBase
from puyapy.parse import ParseResult

logger = log.get_logger(__name__)


@attrs.frozen(kw_only=True)
class ASTConversionContext:
    _parse_result: ParseResult
    constants: dict[str, ConstantValue] = attrs.field(factory=dict)
    _pytypes: dict[str, pytypes.PyType] = attrs.field(factory=pytypes.builtins_registry)
    _contract_fragments: dict[ContractReference, ContractFragmentBase] = attrs.field(factory=dict)

    @property
    def mypy_options(self) -> mypy.options.Options:
        return self._parse_result.mypy_options

    @property
    def contract_fragments(self) -> Mapping[ContractReference, ContractFragmentBase]:
        return self._contract_fragments

    def add_contract_fragment(self, fragment: ContractFragmentBase) -> None:
        assert (
            fragment.id not in self._contract_fragments
        ), "attempted to add contract fragment twice"
        self._contract_fragments[fragment.id] = fragment

    def for_module(self, module_path: Path) -> "ASTConversionModuleContext":
        return attrs_extend(ASTConversionModuleContext, self, module_path=module_path)

    def register_pytype(self, typ: pytypes.PyType, *, alias: str | None = None) -> None:
        name = alias or typ.name
        existing_entry = self._pytypes.get(name)

        if existing_entry is typ:
            logger.debug(f"Duplicate registration of {typ}")
        else:
            if existing_entry is not None:
                logger.error(f"Redefinition of type {name}")
            self._pytypes[name] = typ

    def lookup_pytype(self, name: str) -> pytypes.PyType | None:
        """Lookup type by the canonical fully qualified name"""
        return self._pytypes.get(name)

    def require_ptype(self, name: str, source_location: SourceLocation) -> pytypes.PyType:
        try:
            return self._pytypes[name]
        except KeyError:
            raise CodeError(f"Unknown type {name}", source_location) from None


@attrs.frozen(kw_only=True)
class ASTConversionModuleContext(ASTConversionContext):
    module_path: Path

    def node_location(
        self,
        node: mypy.nodes.Context,
        module_src: mypy.nodes.TypeInfo | None = None,
    ) -> SourceLocation:
        if not module_src:
            module_path = self.module_path
        else:
            module_name = module_src.module_name
            try:
                module_path = self._parse_result.ordered_modules[module_name].path
            except KeyError as ex:
                raise CodeError(f"could not find module '{module_name}'") from ex
        loc = _source_location_from_mypy(file=module_path, node=node)
        # if not at start of file, try and expand to preceding comment lines,
        if loc.line > 1:
            prior_code = try_get_source(
                self._parse_result.sources_by_path,
                SourceLocation(file=module_path, line=1, end_line=loc.line - 1),
            )
            comment_lines_count = 0
            for line in reversed(prior_code or []):
                if not line.strip().startswith("#"):
                    break
                comment_lines_count += 1
            if comment_lines_count:
                loc = attrs.evolve(loc, comment_lines=comment_lines_count)
        # if multi-line, strip trailing blank/comment lines
        if loc.end_line != loc.line:
            lines = try_get_source(self._parse_result.sources_by_path, loc)
            if lines is not None:
                chop = 0
                for line in reversed(lines):
                    l_stripped = line.lstrip()
                    if l_stripped and not l_stripped.startswith("#"):
                        break
                    chop += 1
                if chop:
                    loc = attrs.evolve(loc, end_line=loc.end_line - chop, end_column=None)
        return loc

    def _maybe_convert_location(
        self, location: mypy.nodes.Context | SourceLocation
    ) -> SourceLocation:
        if isinstance(location, mypy.nodes.Context):
            return self.node_location(location)
        return location

    def error(self, msg: str, location: mypy.nodes.Context | SourceLocation) -> None:
        logger.error(msg, location=self._maybe_convert_location(location))

    def info(self, msg: str, location: mypy.nodes.Context | SourceLocation) -> None:
        logger.info(msg, location=self._maybe_convert_location(location))

    def warning(self, msg: str, location: mypy.nodes.Context | SourceLocation) -> None:
        logger.warning(msg, location=self._maybe_convert_location(location))

    @contextlib.contextmanager
    def log_exceptions(
        self, fallback_location: mypy.nodes.Context | SourceLocation
    ) -> Iterator[None]:
        with log_exceptions(self._maybe_convert_location(fallback_location)):
            yield

    def type_to_pytype(
        self,
        mypy_type: mypy.types.Type,
        *,
        source_location: mypy.nodes.Context | SourceLocation,
        in_type_args: bool = False,
    ) -> pytypes.PyType:
        return type_to_pytype(
            self._pytypes,
            mypy_type,
            source_location=self._maybe_convert_location(source_location),
            in_type_args=in_type_args,
        )


def type_to_pytype(
    registry: Mapping[str, pytypes.PyType],
    mypy_type: mypy.types.Type,
    *,
    source_location: SourceLocation,
    in_type_args: bool = False,
    in_func_sig: bool = False,
) -> pytypes.PyType:
    loc = (
        source_location
        if mypy_type.line is None or mypy_type.line < 1
        else _source_location_from_mypy(source_location.file, mypy_type)
    )
    proper_type_or_alias: mypy.types.ProperType | mypy.types.TypeAliasType
    if isinstance(mypy_type, mypy.types.TypeAliasType):
        proper_type_or_alias = mypy_type
    else:
        proper_type_or_alias = mypy.types.get_proper_type(mypy_type)
    recurse = functools.partial(
        type_to_pytype,
        registry,
        source_location=loc,
        in_type_args=in_type_args,
        in_func_sig=in_func_sig,
    )
    match proper_type_or_alias:
        case mypy.types.TypeAliasType(alias=alias, args=args):
            if alias is None:
                raise InternalError("mypy type alias type missing alias reference", loc)
            result = registry.get(alias.fullname)
            if result is None:
                return recurse(mypy.types.get_proper_type(proper_type_or_alias))
            return _maybe_parameterise_pytype(registry, result, args, loc)
        # this is how variadic tuples are represented in mypy types...
        case mypy.types.Instance(type=mypy.nodes.TypeInfo(fullname="builtins.tuple"), args=args):
            try:
                (arg,) = args
            except ValueError:
                raise InternalError(
                    f"mypy tuple type as instance had unrecognised args: {args}", loc
                ) from None
            if not in_func_sig:
                raise CodeError("variadic tuples are not supported", loc)
            return pytypes.VariadicTupleType(items=recurse(arg))
        case mypy.types.Instance(args=args) as inst:
            fullname = inst.type.fullname
            result = registry.get(fullname)
            if result is None:
                if fullname.startswith("builtins."):
                    msg = f"Unsupported builtin type: {fullname.removeprefix('builtins.')}"
                else:
                    msg = f"Unknown type: {fullname}"
                raise CodeError(msg, loc)
            return _maybe_parameterise_pytype(registry, result, args, loc)
        case mypy.types.TupleType(items=items, partial_fallback=fallback):
            if not fallback.args:
                return recurse(fallback)
            generic = registry.get(fallback.type.fullname)
            if generic is None:
                raise CodeError(f"unknown tuple base type: {fallback.type.fullname}", loc)
            return _maybe_parameterise_pytype(registry, generic, items, loc)
        case mypy.types.LiteralType(fallback=fallback, value=literal_value) as mypy_literal_type:
            if not in_type_args:
                # this is a bit clumsy, but exists because for some reason, bool types
                # can be "narrowed" down to a typing.Literal. e.g. in the case of:
                #   assert a
                #   assert a or b
                # then the type of `a or b` becomes typing.Literal[True]
                return recurse(fallback)
            if mypy_literal_type.is_enum_literal():
                raise CodeError("typing literals of enum are not supported", loc)
            our_literal_value: pytypes.TypingLiteralValue
            if fallback.type.fullname == "builtins.bytes":  # WHY^2
                bytes_literal_value = ast.literal_eval("b" + repr(literal_value))
                assert isinstance(bytes_literal_value, bytes)
                our_literal_value = bytes_literal_value
            elif isinstance(literal_value, float):  # WHY
                raise CodeError("typing literals with float values are not supported", loc)
            else:
                our_literal_value = literal_value
            return pytypes.TypingLiteralType(value=our_literal_value, source_location=loc)
        case mypy.types.UnionType(items=items):
            types = unique(recurse(it) for it in items)
            if not types:
                return pytypes.NeverType
            elif len(types) == 1:
                return types[0]
            else:
                return pytypes.UnionType(types, loc)
        case mypy.types.NoneType() | mypy.types.PartialType(type=None):
            return pytypes.NoneType
        case mypy.types.UninhabitedType():
            return pytypes.NeverType
        case mypy.types.AnyType(type_of_any=type_of_any):
            msg = _type_of_any_to_error_message(type_of_any, loc)
            raise CodeError(msg, loc)
        case mypy.types.TypeType(item=inner_type):
            inner_pytype = recurse(inner_type)
            return pytypes.TypeType(inner_pytype)
        case mypy.types.FunctionLike() as func_like:
            if func_like.is_type_obj():
                # note sure if this will always work for overloads, but the only overloaded
                # constructor we have is arc4.StaticArray, so...
                ret_type = func_like.items[0].ret_type
                cls_typ = recurse(ret_type)
                return pytypes.TypeType(cls_typ)
            else:
                if not isinstance(func_like, mypy.types.CallableType):  # vs Overloaded
                    raise CodeError("references to overloaded functions are not supported", loc)
                ret_pytype = recurse(func_like.ret_type)
                func_args = []
                for at, name, kind in zip(
                    func_like.arg_types, func_like.arg_names, func_like.arg_kinds, strict=True
                ):
                    arg_pytype = type_to_pytype(
                        registry,
                        at,
                        source_location=loc,
                        in_type_args=in_type_args,
                        in_func_sig=True,
                    )
                    func_args.append(pytypes.FuncArg(type=arg_pytype, kind=kind, name=name))
                if func_like.bound_args:
                    logger.error("function type has bound arguments", location=loc)
                if func_like.definition is not None:
                    name = func_like.definition.fullname
                else:
                    name = repr(func_like)
                if func_like.def_extras.get("first_arg"):
                    _self_arg, *func_args = func_args
                return pytypes.FuncType(
                    name=name,
                    args=func_args,
                    ret_type=ret_pytype,
                )
        case _:
            raise CodeError(f"Unable to resolve mypy type {mypy_type!r} to known algopy type", loc)


def _maybe_parameterise_pytype(
    registry: Mapping[str, pytypes.PyType],
    maybe_generic: pytypes.PyType,
    mypy_type_args: Sequence[mypy.types.Type],
    loc: SourceLocation,
) -> pytypes.PyType:
    if not mypy_type_args:
        return maybe_generic
    if all(isinstance(t, mypy.types.TypeVarType | mypy.types.UnpackType) for t in mypy_type_args):
        return maybe_generic
    type_args_resolved = [
        type_to_pytype(registry, mta, source_location=loc, in_type_args=True)
        for mta in mypy_type_args
    ]
    result = maybe_generic.parameterise(type_args_resolved, loc)
    return result


def _type_of_any_to_error_message(type_of_any: int, source_location: SourceLocation) -> str:
    from mypy.types import TypeOfAny

    match type_of_any:
        case TypeOfAny.unannotated:
            msg = "type annotation is required at this location"
        case TypeOfAny.explicit | TypeOfAny.from_another_any:
            msg = "Any type is not supported"
        case TypeOfAny.from_unimported_type:
            msg = "unknown type from import"
        case TypeOfAny.from_omitted_generics:
            msg = "type parameters are required at this location"
        case TypeOfAny.from_error:
            msg = "typing error prevents type resolution"
        case TypeOfAny.special_form:
            msg = "unsupported type form"
        case TypeOfAny.implementation_artifact | TypeOfAny.suggestion_engine:
            msg = "mypy cannot handle this type form, try providing an explicit annotation"
        case _:
            logger.debug(f"Unknown TypeOfAny value: {type_of_any}", location=source_location)
            msg = "Any type is not supported"
    return msg


def _source_location_from_mypy(file: Path | None, node: mypy.nodes.Context) -> SourceLocation:
    assert node.line is not None
    assert node.line >= 1

    match node:
        case (
            mypy.nodes.FuncDef(body=body)
            | mypy.nodes.Decorator(func=mypy.nodes.FuncDef(body=body))
        ):
            # end_line of a function node includes the entire body
            # try to get just the signature
            end_line = node.line
            # no body means the end_line is ok to use
            if body is None:
                end_line = max(end_line, node.end_line or node.line)
            # if there is a body, attempt to use the first line before the body as the end
            else:
                end_line = max(end_line, body.line - 1)
            return SourceLocation(
                file=file,
                line=node.line,
                end_line=end_line,
            )
        case mypy.nodes.ClassDef(decorators=class_decorators, defs=class_body):
            line = node.line
            for dec in class_decorators:
                line = min(dec.line, line)
            end_line = max(line, class_body.line - 1)
            return SourceLocation(
                file=file,
                line=line,
                end_line=end_line,
            )
        case mypy.nodes.WhileStmt(body=compound_body) | mypy.nodes.ForStmt(body=compound_body):
            return SourceLocation(
                file=file,
                line=node.line,
                end_line=compound_body.line - 1,
            )
        case mypy.nodes.IfStmt(body=[*bodies], else_body=else_body):
            body_start: int | None = None
            if else_body is not None:
                bodies.append(else_body)
            for body in bodies:
                if body_start is None:
                    body_start = body.line
                else:
                    body_start = min(body_start, body.line)
            if body_start is None:
                # this shouldn't happen, there should be at least one body in one branch,
                # but this serves okay as a fallback
                end_line = node.end_line or node.line
            else:
                end_line = body_start - 1
            return SourceLocation(
                file=file,
                line=node.line,
                end_line=end_line,
            )
        case mypy.types.Type():
            # mypy types seem to not have an end_column specified, which ends up implying to
            # end of line, so instead make end_column end after column so it is just a
            # single character reference

            if node.column < 0:
                typ_column: int | None = None
                typ_end_column: int | None = None
            else:
                typ_column = node.column
                typ_end_column = coalesce(node.end_column, typ_column + 1)
            return SourceLocation(
                file=file,
                line=node.line,
                end_line=(
                    node.end_line
                    if (node.end_line is not None and node.end_line >= 1)
                    else node.line
                ),
                column=typ_column,
                end_column=typ_end_column,
            )
    return SourceLocation(
        file=file,
        line=node.line,
        end_line=(
            node.end_line if (node.end_line is not None and node.end_line >= 1) else node.line
        ),
        column=node.column if (node.column is not None and node.column >= 0) else 0,
        end_column=(
            node.end_column if (node.end_column is not None and node.end_column >= 0) else None
        ),
    )
