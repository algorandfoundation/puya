import typing
from collections.abc import Iterator, Mapping
from typing import Never

import mypy.nodes
import mypy.types
import mypy.visitor

import puya.metadata
from puya.awst import wtypes
from puya.awst.nodes import (
    AppStateDefinition,
    AppStateKind,
    BytesEncoding,
    ContractFragment,
    ContractMethod,
    ContractReference,
)
from puya.awst_build import constants
from puya.awst_build.base_mypy_visitor import BaseMyPyStatementVisitor
from puya.awst_build.context import ASTConversionModuleContext
from puya.awst_build.subroutine import ContractMethodInfo, FunctionASTConverter
from puya.awst_build.utils import (
    extract_bytes_literal_from_mypy,
    extract_docstring,
    get_decorators_by_fullname,
    iterate_user_bases,
    qualified_class_name,
)
from puya.errors import CodeError, InternalError
from puya.ir.arc4_util import wtype_to_arc4
from puya.metadata import ARC4DefaultArgument, ARC4MethodConfig, ARC32StructDef
from puya.parse import SourceLocation


class ContractASTConverter(BaseMyPyStatementVisitor[None]):
    def __init__(
        self,
        context: ASTConversionModuleContext,
        class_def: mypy.nodes.ClassDef,
        name_override: str | None,
    ):
        super().__init__(context=context)
        self.class_def = class_def
        self.cref = qualified_class_name(class_def.info)
        self._is_arc4 = class_def.info.has_base(constants.ARC4_CONTRACT_BASE)
        docstring = extract_docstring(class_def)
        self._is_abstract = class_def.info.is_abstract  # TODO: is this sufficient?
        self._approval_program: ContractMethod | None = None
        self._clear_program: ContractMethod | None = None
        self._init_method: ContractMethod | None = None
        self._subroutines = list[ContractMethod]()
        this_app_state = list(_gather_app_state(context, class_def.info))
        combined_app_state = {defn.member_name: defn for defn in this_app_state}
        for base in iterate_user_bases(class_def.info):
            base_app_state = {
                defn.member_name: defn
                # NOTE: we don't report errors for the decls themselves here,
                #       they should already have been reported when analysing the base type
                for defn in _gather_app_state(context, base, report_errors=False)
            }
            for redefined_member in combined_app_state.keys() & base_app_state.keys():
                member_redef = combined_app_state[redefined_member]
                member_orig = base_app_state[redefined_member]
                self.context.note(
                    f"Previous definition of {redefined_member} was here",
                    member_orig.source_location,
                )
                self.context.error(
                    f"Redefinition of {redefined_member}",
                    member_redef.source_location,
                )
            # we do it this way around so that we keep combined_app_state with the most-derived
            # definition in case of redefinitions
            combined_app_state = base_app_state | combined_app_state
        self.app_state: dict[str, AppStateDefinition] = combined_app_state

        # note: we iterate directly and catch+log code errors here,
        #       since each statement should be somewhat independent given
        #       the constraints we place (e.g. if one function fails to convert,
        #       we can still keep trying to convert other functions to produce more valid errors)
        for stmt in class_def.defs.body:
            with context.log_exceptions(fallback_location=stmt):
                stmt.accept(self)

        self.result_ = ContractFragment(
            module_name=self.cref.module_name,
            name=self.cref.class_name,
            name_override=name_override,
            is_abstract=self._is_abstract,
            bases=_gather_bases(context, class_def),
            is_arc4=self._is_arc4,
            init=self._init_method,
            approval_program=self._approval_program,
            clear_program=self._clear_program,
            subroutines=self._subroutines,
            app_state=this_app_state,
            docstring=docstring,
            source_location=self._location(class_def),
        )

    @classmethod
    def convert(
        cls,
        context: ASTConversionModuleContext,
        class_def: mypy.nodes.ClassDef,
        name_override: str | None,
    ) -> ContractFragment:
        return cls(context, class_def, name_override).result_

    def empty_statement(self, _stmt: mypy.nodes.Statement) -> None:
        return None

    def visit_function(
        self,
        func_def: mypy.nodes.FuncDef,
        decorator: mypy.nodes.Decorator | None,
    ) -> None:
        func_loc = self._location(func_def)
        self._precondition(
            self._is_abstract or func_def.abstract_status == mypy.nodes.NOT_ABSTRACT,
            "class abstract method(s) but was not detected as abstract by mypy",
            func_loc,
        )

        keep_going = True
        if func_def.is_class:
            self._error("@classmethod not supported", func_loc)
            keep_going = False
        if func_def.is_static:
            self._error(
                "@staticmethod not supported, use a module level function instead", func_loc
            )
            keep_going = False

        dec_by_fullname = get_decorators_by_fullname(self.context, decorator) if decorator else {}
        # TODO: validate decorator ordering?
        dec_by_fullname.pop("abc.abstractmethod", None)
        for unknown_dec_fullname in dec_by_fullname.keys() - frozenset(
            constants.KNOWN_METHOD_DECORATORS
        ):
            dec = dec_by_fullname.pop(unknown_dec_fullname)
            self._error(f'Unsupported decorator "{unknown_dec_fullname}"', dec)

        if not keep_going:
            pass  # unrecoverable error in prior validation,
        # TODO: handle difference of subroutine vs abimethod and overrides???
        elif func_def.name == "__init__":
            sub = self._handle_method(
                func_def, extra_decorators=dec_by_fullname, abimethod_config=None
            )
            if sub is not None:
                self._init_method = sub
        elif func_def.name.startswith("__") and func_def.name.endswith("__"):
            self._error(
                "methods starting and ending with a double underscore"
                ' (aka "dunder" methods) are reserved for the Python data model'
                " (https://docs.python.org/3/reference/datamodel.html)."
                " Of these methods, only __init__ is supported in contract classes",
                func_loc,
            )
        elif (
            is_approval := func_def.name == constants.APPROVAL_METHOD
        ) or func_def.name == constants.CLEAR_STATE_METHOD:
            if is_approval and self._is_arc4:
                self.context.warning(
                    "ARC4 contract compliance may be violated"
                    f" when a custom {func_def.name} function is used",
                    func_loc,
                )
            sub = self._handle_method(
                func_def, extra_decorators=dec_by_fullname, abimethod_config=None
            )
            if sub is not None:
                if is_approval:
                    self._approval_program = sub
                else:
                    self._clear_program = sub
        else:
            subroutine_dec = dec_by_fullname.pop(constants.SUBROUTINE_HINT, None)
            abimethod_dec = dec_by_fullname.pop(constants.ABIMETHOD_DECORATOR, None)
            baremethod_dec = dec_by_fullname.pop(constants.BAREMETHOD_DECORATOR, None)

            if not (subroutine_dec or abimethod_dec or baremethod_dec):
                self._error(
                    f"member functions (other than __init__ or approval / clear program methods)"
                    f" must be annotated with exactly one of @{constants.SUBROUTINE_HINT_ALIAS} or"
                    f" @{constants.ABIMETHOD_DECORATOR_ALIAS}",
                    func_loc,
                )

            arc4_method_config = None
            arc4_decorator = abimethod_dec or baremethod_dec
            if arc4_decorator is not None:
                arc4_decorator_name = (
                    constants.ABIMETHOD_DECORATOR_ALIAS
                    if abimethod_dec
                    else constants.BAREMETHOD_DECORATOR_ALIAS
                )

                arc4_decorator_loc = self._location(arc4_decorator)
                if not self._is_arc4:
                    self._error(
                        f"{arc4_decorator_name} decorator is only for subclasses"
                        f" of {constants.ARC4_CONTRACT_BASE_ALIAS}",
                        arc4_decorator_loc,
                    )
                if abimethod_dec and baremethod_dec:
                    self._error("cannot be both an abimethod and a baremethod", arc4_decorator_loc)
                if subroutine_dec is not None:
                    self._error(
                        f"cannot be both a subroutine and {arc4_decorator_name}", subroutine_dec
                    )
                *arg_wtypes, ret_wtype = get_func_types(
                    self.context, func_def, location=arc4_decorator_loc
                ).values()
                arc4_method_config = _get_arc4_method_config(
                    self.context, arc4_decorator, func_def
                )
                if arc4_method_config.is_bare:
                    if arg_wtypes or (ret_wtype is not wtypes.void_wtype):
                        self._error(
                            "bare methods should have no arguments or return values",
                            arc4_decorator_loc,
                        )
                else:
                    for arg_wtype in arg_wtypes:
                        if not wtypes.is_arc4_argument_type(arg_wtype):
                            self._error(
                                f"Invalid argument type for an ARC4 method: {arg_wtype}",
                                arc4_decorator_loc,
                            )
                    if not (
                        ret_wtype is wtypes.void_wtype or wtypes.is_arc4_encoded_type(ret_wtype)
                    ):
                        self._error(
                            f"Invalid return type for an ARC4 method: {ret_wtype}",
                            arc4_decorator_loc,
                        )
                # TODO: validate against super-class configs??
            sub = self._handle_method(
                func_def, extra_decorators=dec_by_fullname, abimethod_config=arc4_method_config
            )
            if sub is not None:
                self._subroutines.append(sub)

    def _handle_method(
        self,
        func_def: mypy.nodes.FuncDef,
        extra_decorators: Mapping[str, mypy.nodes.Expression],
        abimethod_config: ARC4MethodConfig | None,
    ) -> ContractMethod | None:
        func_loc = self._location(func_def)
        self._precondition(
            not (func_def.is_static or func_def.is_class),
            "only instance methods should have made it to this point",
            func_loc,
        )
        for dec_fullname, dec in extra_decorators.items():
            self._error(f'Unsupported decorator "{dec_fullname}"', dec)
        if len(func_def.arguments) < 1:
            # since we checked we're only handling instance methods, should be at least one
            # argument to function - ie self
            self._error(f"{func_def.name} should take a self parameter", func_loc)
        match func_def.abstract_status:
            case mypy.nodes.NOT_ABSTRACT:
                return FunctionASTConverter.convert(
                    self.context,
                    func_def=func_def,
                    contract_method_info=ContractMethodInfo(
                        type_info=self.class_def.info,
                        arc4_method_config=abimethod_config,
                        app_state=self.app_state,
                        cref=self.cref,
                    ),
                )
            case mypy.nodes.IMPLICITLY_ABSTRACT:
                # TODO: should we have a placeholder item instead? need to handle via super() if so
                self.context.note(
                    f"Skipping (implicitly) abstract method {func_def.name}",
                    func_loc,
                )
                return None
            case mypy.nodes.IS_ABSTRACT:
                # TODO: should we have a placeholder item instead? need to handle via super() if so
                self.context.note(
                    f"Skipping abstract method {func_def.name}",
                    func_loc,
                )
                return None
            case _ as unknown_value:
                raise InternalError(
                    f"Unknown value for abstract_status: {unknown_value}", func_loc
                )

    def visit_block(self, o: mypy.nodes.Block) -> None:
        raise InternalError("shouldn't get here", self._location(o))

    def visit_return_stmt(self, stmt: mypy.nodes.ReturnStmt) -> None:
        self._error("illegal Python syntax, return in class body", location=stmt)

    def visit_class_def(self, cdef: mypy.nodes.ClassDef) -> None:
        self._error("nested classes are not supported", location=cdef)

    def _unsupported(self, kind: str, stmt: mypy.nodes.Statement) -> None:
        self._error(f"{kind} statements are not supported in the class body", location=stmt)

    def visit_assignment_stmt(self, stmt: mypy.nodes.AssignmentStmt) -> None:
        if isinstance(stmt.rvalue, mypy.nodes.TempNode):
            # silently allow state declarations, these will be picked up by gather state
            return
        self._unsupported("assignment", stmt)

    def visit_operator_assignment_stmt(self, stmt: mypy.nodes.OperatorAssignmentStmt) -> None:
        self._unsupported("operator assignment", stmt)

    def visit_expression_stmt(self, stmt: mypy.nodes.ExpressionStmt) -> None:
        self._unsupported("expression statement", stmt)

    def visit_if_stmt(self, stmt: mypy.nodes.IfStmt) -> None:
        self._unsupported("if", stmt)

    def visit_while_stmt(self, stmt: mypy.nodes.WhileStmt) -> None:
        self._unsupported("while", stmt)

    def visit_for_stmt(self, stmt: mypy.nodes.ForStmt) -> None:
        self._unsupported("for", stmt)

    def visit_break_stmt(self, stmt: mypy.nodes.BreakStmt) -> None:
        self._unsupported("break", stmt)

    def visit_continue_stmt(self, stmt: mypy.nodes.ContinueStmt) -> None:
        self._unsupported("continue", stmt)

    def visit_assert_stmt(self, stmt: mypy.nodes.AssertStmt) -> None:
        self._unsupported("assert", stmt)

    def visit_del_stmt(self, stmt: mypy.nodes.DelStmt) -> None:
        self._unsupported("del", stmt)

    def visit_match_stmt(self, stmt: mypy.nodes.MatchStmt) -> None:
        self._unsupported("match", stmt)

    def visit_nonlocal_decl(self, stmt: mypy.nodes.NonlocalDecl) -> None:
        self._unsupported("nonlocal", stmt)


def _gather_app_state(
    context: ASTConversionModuleContext,
    class_info: mypy.nodes.TypeInfo,
    *,
    report_errors: bool = True,
) -> Iterator[AppStateDefinition]:
    for name, sym in class_info.names.items():
        if isinstance(sym.node, mypy.nodes.Var):
            var_loc = context.node_location(sym.node)
            typ = mypy.types.get_proper_type(sym.type)
            if typ is None:
                raise InternalError(
                    f"symbol table for class {class_info.fullname}"
                    f" contains Var node entry for {name} without type",
                    var_loc,
                )
            match typ:
                case mypy.types.Instance(
                    type=mypy.nodes.TypeInfo(fullname=constants.LOCAL_PROXY_CLS), args=args
                ):
                    kind = AppStateKind.account_local
                    try:
                        (storage_type,) = args
                    except ValueError:
                        if report_errors:
                            context.error(
                                "Local storage requires exactly one type parameter", var_loc
                            )
                        continue
                case _:
                    kind = AppStateKind.app_global
                    storage_type = typ
            storage_wtype = context.type_to_wtype(storage_type, source_location=var_loc)
            if not storage_wtype.lvalue:
                if report_errors:
                    context.error(
                        f"Invalid type for Local storage - must be assignable,"
                        f" which type {storage_wtype} is not",
                        var_loc,
                    )
            else:
                yield AppStateDefinition(
                    source_location=var_loc,
                    member_name=name,
                    storage_wtype=storage_wtype,
                    key=name.encode(),  # TODO: encode name -> key with source file encoding?
                    key_encoding=BytesEncoding.utf8,
                    kind=kind,
                )


def get_func_types(
    context: ASTConversionModuleContext, func_def: mypy.nodes.FuncDef, location: SourceLocation
) -> dict[str, wtypes.WType]:
    skip_first = (
        1
        if func_def.arguments
        and (func_def.arguments[0].variable.is_self or func_def.arguments[0].variable.is_cls)
        else 0
    )
    in_var_names = [arg.variable.name for arg in func_def.arguments[skip_first:]]
    if "output" in in_var_names:
        # https://github.com/algorandfoundation/ARCs/blob/main/assets/arc-0032/application.schema.json
        raise CodeError(
            "For compatibility with ARC-32, ARC-4 methods cannot have an argument named output",
            location,
        )
    names = [*in_var_names, "output"]
    match func_def.type:
        case mypy.types.CallableType(arg_types=arg_types, ret_type=ret_type):
            types = arg_types[skip_first:] + [ret_type]
            wtypes_ = (context.type_to_wtype(t, source_location=location) for t in types)
            return dict(zip(names, wtypes_, strict=True))
    raise InternalError("Unexpected FuncDef type")


def _get_arc4_method_config(
    context: ASTConversionModuleContext,
    decorator: mypy.nodes.Expression,
    func_def: mypy.nodes.FuncDef,
) -> ARC4MethodConfig:
    dec_loc = context.node_location(decorator)
    match decorator:
        case mypy.nodes.RefExpr(fullname=fullname):
            return ARC4MethodConfig(
                name=func_def.name,
                source_location=dec_loc,
                is_bare=fullname == constants.BAREMETHOD_DECORATOR,
            )
        case mypy.nodes.CallExpr(
            args=args,
            arg_names=arg_names,
            callee=mypy.nodes.RefExpr(fullname=fullname),
        ):
            visitor = _DecoratorArgEvaluator()
            abi_hints = typing.cast(
                _AbiHints,
                {n: a.accept(visitor) for n, a in zip(filter(None, arg_names), args, strict=True)},
            )
            name = abi_hints.get("name", func_def.name)
            allow_actions = abi_hints.get("allow_actions", ["NoOp"])
            if len(set(allow_actions)) != len(allow_actions):
                context.error("Cannot have duplicate allow_actions", dec_loc)
            if not allow_actions:
                context.error("Must have at least one allow_actions", dec_loc)
            create = abi_hints.get("create", False)
            readonly = abi_hints.get("readonly", False)
            default_args = abi_hints.get("default_args", {})
            all_args = [
                a.variable.name for a in (func_def.arguments or []) if not a.variable.is_self
            ]
            for parameter in default_args:
                if parameter not in all_args:
                    context.error(
                        f"'{parameter}' is not a parameter of {func_def.fullname}", dec_loc
                    )
                # TODO: validate source here as well?
                #       Deferring it allows for more flexibility in contract composition

            structs = [
                (n, _wtype_to_struct_def(t))
                for n, t in get_func_types(context, func_def, dec_loc).items()
                if isinstance(t, wtypes.ARC4Struct)
            ]

            return ARC4MethodConfig(
                source_location=dec_loc,
                name=name,
                allowed_completion_types=[
                    puya.metadata.OnCompletionAction[a] for a in allow_actions
                ],
                allow_create=create == "allow",
                require_create=create is True,
                readonly=readonly,
                is_bare=fullname == constants.BAREMETHOD_DECORATOR,
                default_args=[
                    ARC4DefaultArgument(parameter=p, source=s) for p, s in default_args.items()
                ],
                structs=structs,
            )
        case _:
            raise InternalError("Unexpected ARC4 decorator", dec_loc)


class _AbiHints(typing.TypedDict, total=False):
    name: str
    allow_actions: list[str]
    create: bool | typing.Literal["allow"]
    readonly: bool
    default_args: dict[str, str]


class _DecoratorArgEvaluator(mypy.visitor.NodeVisitor[typing.Any]):
    def __getattribute__(self, name: str) -> object:
        attr = super().__getattribute__(name)
        if name.startswith("visit_") and not attr.__module__.startswith("puya."):
            return self._not_supported
        return attr

    def _not_supported(self, o: mypy.nodes.Context) -> Never:
        raise CodeError(f"Cannot evaluate expression {o}")

    def visit_int_expr(self, o: mypy.nodes.IntExpr) -> int:
        return o.value

    def visit_str_expr(self, o: mypy.nodes.StrExpr) -> str:
        return o.value

    def visit_bytes_expr(self, o: mypy.nodes.BytesExpr) -> bytes:
        return extract_bytes_literal_from_mypy(o)

    def visit_float_expr(self, o: mypy.nodes.FloatExpr) -> float:
        return o.value

    def visit_complex_expr(self, o: mypy.nodes.ComplexExpr) -> object:
        return o.value

    def visit_ellipsis(self, _: mypy.nodes.EllipsisExpr) -> object:
        return Ellipsis

    def visit_name_expr(self, o: mypy.nodes.NameExpr) -> object:
        if o.name == "True":
            return True
        elif o.name == "False":
            return False
        elif o.name == "None":
            return None
        else:
            return o.name

    def visit_member_expr(self, o: mypy.nodes.MemberExpr) -> object:
        return o.name

    def visit_cast_expr(self, o: mypy.nodes.CastExpr) -> object:
        return o.expr.accept(self)

    def visit_assert_type_expr(self, o: mypy.nodes.AssertTypeExpr) -> object:
        return o.expr.accept(self)

    def visit_unary_expr(self, o: mypy.nodes.UnaryExpr) -> object:
        operand: object = o.expr.accept(self)
        if o.op == "-":
            if isinstance(operand, (int, float, complex)):
                return -operand
        elif o.op == "+":
            if isinstance(operand, (int, float, complex)):
                return +operand
        elif o.op == "~":
            if isinstance(operand, int):
                return ~operand
        elif o.op == "not" and isinstance(operand, (bool, int, float, str, bytes)):
            return not operand
        self._not_supported(o)

    def visit_assignment_expr(self, o: mypy.nodes.AssignmentExpr) -> object:
        return o.value.accept(self)

    def visit_list_expr(self, o: mypy.nodes.ListExpr) -> list[object]:
        return [item.accept(self) for item in o.items]

    def visit_dict_expr(self, o: mypy.nodes.DictExpr) -> dict[object, object]:
        return {key.accept(self) if key else None: value.accept(self) for key, value in o.items}

    def visit_tuple_expr(self, o: mypy.nodes.TupleExpr) -> tuple[object, ...]:
        return tuple(item.accept(self) for item in o.items)

    def visit_set_expr(self, o: mypy.nodes.SetExpr) -> set[object]:
        return {item.accept(self) for item in o.items}


def _wtype_to_struct_def(wtype: wtypes.ARC4Struct) -> ARC32StructDef:
    return ARC32StructDef(
        name=wtype.name, elements=[(n, wtype_to_arc4(t)) for n, t in wtype.fields.items()]
    )


def _gather_bases(
    context: ASTConversionModuleContext, class_def: mypy.nodes.ClassDef
) -> list[ContractReference]:
    class_def_loc = context.node_location(class_def)
    contract_bases_mro = list[ContractReference]()
    for base_type in iterate_user_bases(class_def.info):
        base_cref = qualified_class_name(base_type)
        if "." in base_cref.class_name:
            raise CodeError(
                f"Reference to base class {base_type.fullname},"
                f" which is nested inside another class",
                class_def_loc,
            )

        try:
            base_symbol = context.parse_result.manager.modules[base_cref.module_name].names[
                base_cref.class_name
            ]
        except KeyError as ex:
            raise InternalError(
                f"Couldn't resolve reference to class {base_cref.class_name}"
                f" in module {base_cref.module_name}",
                class_def_loc,
            ) from ex
        base_class_info = base_symbol.node
        if not isinstance(base_class_info, mypy.nodes.TypeInfo):
            raise CodeError(
                f"Base class {base_type.fullname} is not a class,"
                f" node type is {type(base_class_info).__name__}",
                class_def_loc,
            )
        if not base_class_info.has_base(constants.CONTRACT_BASE):
            raise CodeError(
                f"Base class {base_type.fullname} is not a contract subclass", class_def_loc
            )
        contract_bases_mro.append(base_cref)

    return contract_bases_mro
