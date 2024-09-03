import enum
import typing
from collections.abc import Callable, Iterator, Mapping, Sequence

import mypy.nodes
import mypy.types
import mypy.visitor
from puya import log
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.errors import CodeError, InternalError
from puya.models import (
    ARC4BareMethodConfig,
    ARC4CreateOption,
    ContractReference,
    OnCompletionAction,
)
from puya.parse import SourceLocation
from puya.utils import unique

from puyapy.awst_build import constants, pytypes
from puyapy.awst_build.arc4_utils import (
    ARC4BareMethodData,
    ARC4MethodData,
    get_arc4_abimethod_data,
    get_arc4_baremethod_data,
)
from puyapy.awst_build.base_mypy_visitor import BaseMyPyStatementVisitor
from puyapy.awst_build.context import ASTConversionModuleContext
from puyapy.awst_build.contract_data import AppStorageDeclaration, ContractClassOptions
from puyapy.awst_build.subroutine import ContractMethodInfo, FunctionASTConverter
from puyapy.awst_build.utils import get_decorators_by_fullname

logger = log.get_logger(__name__)


DeferredContractMethod: typing.TypeAlias = Callable[
    [ASTConversionModuleContext], awst_nodes.ContractMethod
]


class SpecialMethod(enum.Enum):
    init = enum.auto()
    approval_program = enum.auto()
    clear_state_program = enum.auto()


class ContractASTConverter(BaseMyPyStatementVisitor[None]):
    def __init__(
        self,
        context: ASTConversionModuleContext,
        class_def: mypy.nodes.ClassDef,
        class_options: ContractClassOptions,
        typ: pytypes.ContractType,
    ):
        super().__init__(context=context)
        self.class_def = class_def
        self.typ = typ
        self.cref = cref = typ.name
        self.is_arc4 = pytypes.ARC4ContractBaseType in typ.mro
        self.is_abstract = _check_class_abstractness(context, class_def)
        if self.is_abstract:
            context.abstract_contracts.add(cref)
        self._methods = list[tuple[DeferredContractMethod, SourceLocation, SpecialMethod | None]]()
        self.class_options: typing.Final = class_options
        self.source_location: typing.Final = self._location(class_def)
        self.bases = bases = _gather_bases(typ)
        self._synthetic_methods = list[awst_nodes.ContractMethod]()

        if self.is_arc4:
            base_arc4_method_info = dict[str, ARC4MethodData]()
            for base_cref in bases:
                base_arc4_method_info = {
                    **{
                        name: method_data
                        for name, method_data in context.arc4_method_data(base_cref).items()
                        if not method_data.is_synthetic_create
                    },
                    **base_arc4_method_info,
                }
            for func_name, method_data in base_arc4_method_info.items():
                context.add_arc4_method_data(cref, func_name, method_data)

        # if the class has an __init__ method, we need to visit it first, so any storage
        # fields cane be resolved to a (static) key
        match class_def.info.names.get("__init__"):
            case mypy.nodes.SymbolTableNode(node=mypy.nodes.Statement() as init_node):
                stmts = unique((init_node, *class_def.defs.body))
            case _:
                stmts = class_def.defs.body
        # note: we iterate directly and catch+log code errors here,
        #       since each statement should be somewhat independent given
        #       the constraints we place (e.g. if one function fails to convert,
        #       we can still keep trying to convert other functions to produce more valid errors)
        for stmt in stmts:
            with context.log_exceptions(fallback_location=stmt):
                stmt.accept(self)
        # TODO: validation for state proxies being non-conditional

        if self.is_arc4 and not self.is_abstract:
            has_create = False
            has_bare_no_op = False
            for hierarchy_cref in (cref, *bases):
                for arc4_method_data in context.arc4_method_data(hierarchy_cref).values():
                    if arc4_method_data.is_synthetic_create:
                        pass
                    elif arc4_method_data.config.create in (
                        ARC4CreateOption.allow,
                        ARC4CreateOption.require,
                    ):
                        has_create = True
                    elif (
                        OnCompletionAction.NoOp in arc4_method_data.config.allowed_completion_types
                    ) and arc4_method_data.is_bare:
                        has_bare_no_op = True

            if not has_create:
                if has_bare_no_op:
                    logger.error(
                        "Non-abstract ARC4 contract has no methods that can be called"
                        " to create the contract, but does have a NoOp bare method,"
                        " so one couldn't be inserted."
                        " In order to allow creating the contract add either"
                        " an @abimethod or @baremethod"
                        ' decorated method with create="require" or create="allow"',
                        location=self.source_location,
                    )
                else:
                    default_create_config = ARC4BareMethodConfig(
                        create=ARC4CreateOption.require,
                        source_location=self.source_location,
                    )
                    default_create_name = "__algopy_default_create"  # TODO: ensure this is unique
                    context.add_arc4_method_data(
                        cref,
                        default_create_name,
                        ARC4BareMethodData(config=default_create_config, is_synthetic_create=True),
                    )
                    self._synthetic_methods.append(
                        awst_nodes.ContractMethod(
                            cref=cref,
                            member_name=default_create_name,
                            synthetic=True,
                            inheritable=False,
                            args=[],
                            return_type=wtypes.void_wtype,
                            body=awst_nodes.Block(
                                body=[],
                                source_location=self.source_location,
                            ),
                            documentation=awst_nodes.MethodDocumentation(),
                            arc4_method_config=default_create_config,
                            source_location=self.source_location,
                        )
                    )

    def build(self, context: ASTConversionModuleContext) -> awst_nodes.ContractFragment:
        class_def = self.class_def
        cref = self.cref
        inherited_and_direct_storage = _gather_app_storage_recursive(
            context, class_def, self.bases
        )
        context.set_state_defs(cref, inherited_and_direct_storage)
        approval_program: awst_nodes.ContractMethod | None = None
        clear_program: awst_nodes.ContractMethod | None = None
        init_method: awst_nodes.ContractMethod | None = None
        subroutines = self._synthetic_methods.copy()
        for method_builder, method_loc, special_kind in self._methods:
            with context.log_exceptions(fallback_location=method_loc):
                sub = method_builder(context)
                match special_kind:
                    case SpecialMethod.init:
                        init_method = sub
                    case SpecialMethod.approval_program:
                        approval_program = sub
                    case SpecialMethod.clear_state_program:
                        clear_program = sub
                    case None:
                        subroutines.append(sub)
                    case unexpected:
                        typing.assert_never(unexpected)

        app_state = {
            name: state_decl.definition
            for name, state_decl in context.state_defs(cref).items()
            if state_decl.defined_in == cref
        }
        class_options = self.class_options
        return awst_nodes.ContractFragment(
            id=cref,
            name=class_options.name_override or class_def.name,
            bases=self.bases,
            init=init_method,
            approval_program=approval_program,
            clear_program=clear_program,
            subroutines=subroutines,
            app_state=app_state,
            docstring=class_def.docstring,
            source_location=self.source_location,
            reserved_scratch_space=class_options.scratch_slot_reservations,
            state_totals=class_options.state_totals,
        )

    def empty_statement(self, _stmt: mypy.nodes.Statement) -> None:
        return None

    def visit_function(
        self,
        func_def: mypy.nodes.FuncDef,
        decorator: mypy.nodes.Decorator | None,
    ) -> None:
        func_loc = self._location(func_def)
        self._precondition(
            self.is_abstract or func_def.abstract_status == mypy.nodes.NOT_ABSTRACT,
            "class abstract method(s) but was not detected as abstract by mypy",
            func_loc,
        )
        source_location = self._location(decorator or func_def)

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
                func_def,
                extra_decorators=dec_by_fullname,
                arc4_method_data=None,
                source_location=source_location,
            )
            if sub is not None:
                self._methods.append((sub, source_location, SpecialMethod.init))
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
            sub = self._handle_method(
                func_def,
                extra_decorators=dec_by_fullname,
                arc4_method_data=None,
                source_location=source_location,
            )
            if sub is not None:
                kind = (
                    SpecialMethod.approval_program
                    if is_approval
                    else SpecialMethod.clear_state_program
                )
                self._methods.append((sub, source_location, kind))
        elif not self.is_arc4:
            for arc4_only_dec_name in (
                constants.ABIMETHOD_DECORATOR,
                constants.BAREMETHOD_DECORATOR,
            ):
                if invalid_dec := dec_by_fullname.pop(arc4_only_dec_name, None):
                    self._error(
                        f"decorator is only valid in subclasses of"
                        f" {pytypes.ARC4ContractBaseType}",
                        invalid_dec,
                    )
            if not dec_by_fullname.pop(constants.SUBROUTINE_HINT, None):
                self._error(f"missing @{constants.SUBROUTINE_HINT_ALIAS} decorator", func_loc)
            sub = self._handle_method(
                func_def,
                extra_decorators=dec_by_fullname,
                arc4_method_data=None,
                source_location=source_location,
            )
            if sub is not None:
                self._methods.append((sub, source_location, None))
        else:
            subroutine_dec = dec_by_fullname.pop(constants.SUBROUTINE_HINT, None)
            abimethod_dec = dec_by_fullname.pop(constants.ABIMETHOD_DECORATOR, None)
            baremethod_dec = dec_by_fullname.pop(constants.BAREMETHOD_DECORATOR, None)

            if len(list(filter(None, (subroutine_dec, abimethod_dec, baremethod_dec)))) != 1:
                self._error(
                    f"ARC-4 contract member functions"
                    f" (other than __init__ or approval / clear program methods)"
                    f" must be annotated with exactly one of"
                    f" @{constants.SUBROUTINE_HINT_ALIAS},"
                    f" @{constants.ABIMETHOD_DECORATOR_ALIAS},"
                    f" or @{constants.BAREMETHOD_DECORATOR_ALIAS}",
                    func_loc,
                )

            arc4_method_data: ARC4MethodData | None
            if abimethod_dec:
                arc4_method_data = get_arc4_abimethod_data(self.context, abimethod_dec, func_def)
            elif baremethod_dec:
                arc4_method_data = get_arc4_baremethod_data(self.context, baremethod_dec, func_def)
            else:
                arc4_method_data = None
            # TODO: validate against super-class configs??
            sub = self._handle_method(
                func_def,
                extra_decorators=dec_by_fullname,
                arc4_method_data=arc4_method_data,
                source_location=source_location,
            )
            if sub is not None:
                self._methods.append((sub, source_location, None))

    def _handle_method(
        self,
        func_def: mypy.nodes.FuncDef,
        extra_decorators: Mapping[str, mypy.nodes.Expression],
        arc4_method_data: ARC4MethodData | None,
        source_location: SourceLocation,
    ) -> DeferredContractMethod | None:
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
        if func_def.is_trivial_body:
            logger.debug(f"skipping trivial method {func_def.name}", location=func_loc)
            return None
        if arc4_method_data is not None:
            self.context.add_arc4_method_data(self.cref, func_def.name, arc4_method_data)
        return lambda ctx: FunctionASTConverter.convert(
            ctx,
            func_def=func_def,
            source_location=source_location,
            contract_method_info=ContractMethodInfo(
                contract_type=self.typ,
                type_info=self.class_def.info,
                arc4_method_data=arc4_method_data,
                cref=self.cref,
            ),
        )

    def visit_block(self, o: mypy.nodes.Block) -> None:
        raise InternalError("shouldn't get here", self._location(o))

    def visit_return_stmt(self, stmt: mypy.nodes.ReturnStmt) -> None:
        self._error("illegal Python syntax, return in class body", location=stmt)

    def visit_class_def(self, cdef: mypy.nodes.ClassDef) -> None:
        self._error("nested classes are not supported", location=cdef)

    def _unsupported_stmt(self, kind: str, stmt: mypy.nodes.Statement) -> None:
        self._error(f"{kind} statements are not supported in the class body", location=stmt)

    def visit_assignment_stmt(self, stmt: mypy.nodes.AssignmentStmt) -> None:
        # just pass on state forward-declarations, these will be picked up by gather state
        # everything else (ie any _actual_ assignments) is unsupported
        if not isinstance(stmt.rvalue, mypy.nodes.TempNode):
            self._unsupported_stmt("assignment", stmt)

    def visit_operator_assignment_stmt(self, stmt: mypy.nodes.OperatorAssignmentStmt) -> None:
        self._unsupported_stmt("operator assignment", stmt)

    def visit_expression_stmt(self, stmt: mypy.nodes.ExpressionStmt) -> None:
        if isinstance(stmt.expr, mypy.nodes.StrExpr):
            # ignore class docstring, already extracted
            # TODO: should we capture field "docstrings"?
            pass
        else:
            self._unsupported_stmt("expression statement", stmt)

    def visit_if_stmt(self, stmt: mypy.nodes.IfStmt) -> None:
        self._unsupported_stmt("if", stmt)

    def visit_while_stmt(self, stmt: mypy.nodes.WhileStmt) -> None:
        self._unsupported_stmt("while", stmt)

    def visit_for_stmt(self, stmt: mypy.nodes.ForStmt) -> None:
        self._unsupported_stmt("for", stmt)

    def visit_break_stmt(self, stmt: mypy.nodes.BreakStmt) -> None:
        self._unsupported_stmt("break", stmt)

    def visit_continue_stmt(self, stmt: mypy.nodes.ContinueStmt) -> None:
        self._unsupported_stmt("continue", stmt)

    def visit_assert_stmt(self, stmt: mypy.nodes.AssertStmt) -> None:
        self._unsupported_stmt("assert", stmt)

    def visit_del_stmt(self, stmt: mypy.nodes.DelStmt) -> None:
        self._unsupported_stmt("del", stmt)

    def visit_match_stmt(self, stmt: mypy.nodes.MatchStmt) -> None:
        self._unsupported_stmt("match", stmt)

    def visit_type_alias_stmt(self, stmt: mypy.nodes.TypeAliasStmt) -> None:
        self._unsupported_stmt("type", stmt)


def _gather_bases(contract_type: pytypes.ContractType) -> list[ContractReference]:
    class_def_loc = contract_type.source_location
    contract_bases_mro = list[ContractReference]()
    for ancestor in contract_type.mro:
        if ancestor is pytypes.ContractBaseType:
            pass
        elif ancestor is pytypes.ARC4ContractBaseType:  # TODO: merge branches?
            contract_bases_mro.append(ContractReference(ancestor.name))
        elif isinstance(ancestor, pytypes.ContractType):
            contract_bases_mro.append(ancestor.name)
        else:
            raise CodeError(f"base class {ancestor} is not a contract subclass", class_def_loc)

    return contract_bases_mro


def _gather_app_storage_recursive(
    context: ASTConversionModuleContext,
    class_def: mypy.nodes.ClassDef,
    bases: Sequence[ContractReference],
) -> dict[str, AppStorageDeclaration]:
    this_global_directs = {
        defn.member_name: defn for defn in _gather_global_direct_storages(context, class_def.info)
    }
    combined_app_state = this_global_directs.copy()
    for base_cref in bases:
        base_app_state = {
            name: defn
            for name, defn in context.state_defs(base_cref).items()
            if defn.defined_in == base_cref
        }
        for redefined_member in combined_app_state.keys() & base_app_state.keys():
            # only handle producing errors for direct globals here,
            # proxies get handled on insert
            if this_member_redef := combined_app_state.get(redefined_member):
                member_orig = base_app_state[redefined_member]
                context.info(
                    f"Previous definition of {redefined_member} was here",
                    member_orig.source_location,
                )
                context.error(
                    f"Redefinition of {redefined_member}",
                    this_member_redef.source_location,
                )
        # we do it this way around so that we keep combined_app_state with the most-derived
        # definition in case of redefinitions
        combined_app_state = base_app_state | combined_app_state
    return combined_app_state


def _gather_global_direct_storages(
    context: ASTConversionModuleContext, class_info: mypy.nodes.TypeInfo
) -> Iterator[AppStorageDeclaration]:
    cref = ContractReference(class_info.fullname)
    for name, sym in class_info.names.items():
        if isinstance(sym.node, mypy.nodes.Var):
            var_loc = context.node_location(sym.node)
            if sym.type is None:
                raise InternalError(
                    f"symbol table for class {class_info.fullname}"
                    f" contains Var node entry for {name} without type",
                    var_loc,
                )
            pytyp = context.type_to_pytype(sym.type, source_location=var_loc)

            if isinstance(pytyp, pytypes.StorageProxyType | pytypes.StorageMapProxyType):
                # these are handled on declaration, need to collect constructor arguments too
                continue

            if pytyp is pytypes.NoneType:
                context.error("None is not supported as a value, only a return type", var_loc)
            yield AppStorageDeclaration(
                member_name=name,
                typ=pytyp,
                source_location=var_loc,
                defined_in=cref,
                key_override=None,
                description=None,
            )


def _check_class_abstractness(
    context: ASTConversionModuleContext, class_def: mypy.nodes.ClassDef
) -> bool:
    is_abstract = class_def.info.is_abstract
    # note: we don't support the metaclass= option, so we only need to check for
    # inheritance of abc.ABC and not  metaclass=abc.ABCMeta
    if is_abstract and not any(
        base.fullname == "abc.ABC" for base in class_def.info.direct_base_classes()
    ):
        context.warning(f"Class {class_def.fullname} is implicitly abstract", class_def)
    return is_abstract
