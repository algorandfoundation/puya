from collections.abc import Iterator, Mapping

import mypy.nodes
import mypy.types

from wyvern.awst.nodes import (
    ABIMethodConfig,
    AppStateDefinition,
    AppStateKind,
    BytesEncoding,
    ContractFragment,
    ContractMethod,
    ContractReference,
)
from wyvern.awst_build import constants
from wyvern.awst_build.base_mypy_visitor import BaseMyPyStatementVisitor
from wyvern.awst_build.context import ASTConversionModuleContext
from wyvern.awst_build.subroutine import ContractMethodInfo, FunctionASTConverter
from wyvern.awst_build.utils import (
    extract_docstring,
    get_decorators_by_fullname,
    iterate_user_bases,
    qualified_class_name,
)
from wyvern.errors import CodeError, InternalError


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
        # TODO: valid decorator ordering?
        dec_by_fullname.pop("abc.abstractmethod", None)
        for unknown_dec_fullname in dec_by_fullname.keys() - frozenset(
            constants.KNOWN_METHOD_DECORATORS
        ):
            dec = dec_by_fullname.pop(unknown_dec_fullname)
            self._error(f'Unsupported decorator "{unknown_dec_fullname}"', dec)

        if not keep_going:
            pass  # unrecoverable error in prior validation,
        # TODO: handle difference of subroutine vs abimethod and overrrides???
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

            abimethod_config: ABIMethodConfig | None = None
            if abimethod_dec is not None:
                if not self._is_arc4:
                    self._error(
                        f"abimethod decorator is only for subclasses"
                        f" of {constants.ARC4_CONTRACT_BASE_ALIAS}",
                        abimethod_dec,
                    )
                if subroutine_dec is not None:
                    self._error("cannot be both a subroutine and an abimethod", subroutine_dec)
                abimethod_config = ABIMethodConfig(
                    name_override=None,  # TODO
                    source_location=self._location(abimethod_dec),
                )
                self.context.warning("TODO: @abimethod config handling", location=func_def)
                # TODO: validate arg types are all ABI
                # TODO: validate against super-class configs??
            elif subroutine_dec is None:
                self._error(
                    f"member functions (other than __init__ or approval / clear program methods)"
                    f" must be annotated with exactly one of @{constants.SUBROUTINE_HINT_ALIAS} or"
                    f" @{constants.ABIMETHOD_DECORATOR_ALIAS}",
                    func_loc,
                )
            sub = self._handle_method(
                func_def, extra_decorators=dec_by_fullname, abimethod_config=abimethod_config
            )
            if sub is not None:
                self._subroutines.append(sub)

    def _handle_method(
        self,
        func_def: mypy.nodes.FuncDef,
        extra_decorators: Mapping[str, mypy.nodes.Expression],
        abimethod_config: ABIMethodConfig | None,
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
                        abimethod_config=abimethod_config,
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
