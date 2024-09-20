import typing
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path

import attrs
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

from puyapy.awst_build import constants, intrinsic_factory, pytypes
from puyapy.awst_build.arc4_utils import (
    get_arc4_abimethod_data,
    get_arc4_baremethod_data,
)
from puyapy.awst_build.base_mypy_visitor import BaseMyPyStatementVisitor
from puyapy.awst_build.context import ASTConversionModuleContext
from puyapy.awst_build.subroutine import ContractMethodInfo, FunctionASTConverter
from puyapy.awst_build.utils import get_decorators_by_fullname
from puyapy.models import (
    AppStorageDeclaration,
    ARC4BareMethodData,
    ARC4MethodData,
    ContractClassOptions,
    ContractFragment,
    ContractFragmentMethod,
)

logger = log.get_logger(__name__)

_ContractMethodBuilder: typing.TypeAlias = Callable[
    [ASTConversionModuleContext], awst_nodes.ContractMethod
]

_INIT_METHOD = "__init__"
_ARC4_CONTRACT_BASE_CREF = ContractReference(constants.ARC4_CONTRACT_BASE)
_SYNTHETIC_LOCATION = SourceLocation(file=Path("/puyapy/awst_build/contract.py"), line=1)


class ContractASTConverter(BaseMyPyStatementVisitor[None]):
    def __init__(
        self,
        context: ASTConversionModuleContext,
        class_def: mypy.nodes.ClassDef,
        class_options: ContractClassOptions,
        typ: pytypes.ContractType,
    ):
        super().__init__(context=context)
        class_loc = self._location(class_def)
        fragment_mro = _build_resolved_mro(context, typ)
        self._is_abstract: typing.Final = _check_class_abstractness(context, class_def)
        self.fragment: typing.Final = ContractFragment(
            id=typ.name,
            source_location=class_loc,
            pytype=typ,
            mro=fragment_mro,
        )

        context.add_contract_fragment(self.fragment)
        for defn in _gather_global_direct_storages(context, class_def.info):
            self.fragment.add_state_def(defn)

        self.class_def = class_def
        self.typ = typ

        self._deferred_methods = list[tuple[ContractFragmentMethod, _ContractMethodBuilder]]()
        self.class_options: typing.Final = class_options

        # if the class has an __init__ method, we need to visit it first, so any storage
        # fields cane be resolved to a (static) key
        match class_def.info.names.get(_INIT_METHOD):
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

        if (
            self._is_arc4
            and not self._is_abstract
            and not any(self.fragment.find_arc4_method_metadata(can_create=True))
        ):
            if any(
                self.fragment.find_arc4_method_metadata(bare=True, oca=OnCompletionAction.NoOp)
            ):
                logger.error(
                    "Non-abstract ARC4 contract has no methods that can be called"
                    " to create the contract, but does have a NoOp bare method,"
                    " so one couldn't be inserted."
                    " In order to allow creating the contract add either"
                    " an @abimethod or @baremethod"
                    ' decorated method with create="require" or create="allow"',
                    location=class_loc,
                )
            else:
                default_create_name = "__algopy_default_create"  # TODO: ensure this is unique
                default_create_config = ARC4BareMethodConfig(
                    create=ARC4CreateOption.require,
                    source_location=_SYNTHETIC_LOCATION,
                )
                self.fragment.add_method(
                    ContractFragmentMethod(
                        member_name=default_create_name,
                        source_location=_SYNTHETIC_LOCATION,
                        metadata=ARC4BareMethodData(
                            member_name=default_create_name, config=default_create_config
                        ),
                        is_trivial=False,
                        synthetic=True,
                        inheritable=False,
                        implementation=awst_nodes.ContractMethod(
                            cref=self.fragment.id,
                            member_name=default_create_name,
                            args=[],
                            return_type=wtypes.void_wtype,
                            body=awst_nodes.Block(
                                body=[],
                                source_location=_SYNTHETIC_LOCATION,
                            ),
                            documentation=awst_nodes.MethodDocumentation(),
                            arc4_method_config=default_create_config,
                            source_location=_SYNTHETIC_LOCATION,
                        ),
                    )
                )

    @property
    def _is_arc4(self) -> bool:
        return pytypes.ARC4ContractBaseType in self.fragment.pytype.mro

    def build(self, context: ASTConversionModuleContext) -> awst_nodes.Contract | None:
        for method_fragment, method_builder in self._deferred_methods:
            with context.log_exceptions(fallback_location=method_fragment.source_location):
                method_fragment.implementation = method_builder(context)

        self.fragment.finalize()
        if self._is_abstract:
            return None

        methods = []
        for cm in self.fragment.collect_method_implementations():
            if cm is None:
                return None
            methods.append(cm)

        approval_method = self.fragment.resolve_method(constants.APPROVAL_METHOD)
        if approval_method is None or approval_method.implementation is None:  # TODO
            logger.error(
                "non-abstract contract class missing approval program",
                location=self.fragment.source_location,
            )
            approval_program = None
        else:
            init_method = self.fragment.resolve_method(_INIT_METHOD)
            if init_method is None:
                approval_program = approval_method.implementation
            else:
                approval_program = attrs.evolve(
                    approval_method.implementation,
                    cref=self.fragment.id,
                    # member_name="__algopy_approval_main", # TODO: uncomment
                    source_location=_SYNTHETIC_LOCATION,
                    body=attrs.evolve(
                        approval_method.implementation.body,
                        source_location=_SYNTHETIC_LOCATION,
                        body=[
                            awst_nodes.IfElse(
                                source_location=_SYNTHETIC_LOCATION,
                                condition=awst_nodes.Not(
                                    _SYNTHETIC_LOCATION,
                                    intrinsic_factory.txn(
                                        "ApplicationID", wtypes.bool_wtype, _SYNTHETIC_LOCATION
                                    ),
                                ),
                                if_branch=awst_nodes.Block(
                                    body=[
                                        awst_nodes.ExpressionStatement(
                                            expr=awst_nodes.SubroutineCallExpression(
                                                wtype=wtypes.void_wtype,
                                                source_location=_SYNTHETIC_LOCATION,
                                                args=[],
                                                target=awst_nodes.InstanceMethodTarget(
                                                    member_name=_INIT_METHOD
                                                ),
                                            )
                                        )
                                    ],
                                    comment="call __init__",
                                    source_location=_SYNTHETIC_LOCATION,
                                ),
                                else_branch=None,
                            ),
                            *approval_method.implementation.body.body,
                        ],
                    ),
                )

        clear_method = self.fragment.resolve_method(constants.CLEAR_STATE_METHOD)
        if clear_method is None or clear_method.implementation is None:  # TODO
            logger.error(
                "non-abstract contract class missing clear-state program",
                location=self.fragment.source_location,
            )
            clear_program = None
        else:
            clear_program = clear_method.implementation

        if approval_program is None or clear_program is None:
            return None

        return awst_nodes.Contract(
            id=self.fragment.id,
            name=self.class_options.name_override or self.class_def.name,
            method_resolution_order=[ancestor.id for ancestor in self.fragment.mro],
            approval_program=approval_program,
            clear_program=clear_program,
            methods=tuple(methods),
            app_state=tuple(
                state_decl.definition for state_decl in self.fragment.state_defs.values()
            ),
            description=self.class_def.docstring,
            source_location=self.fragment.source_location,
            reserved_scratch_space=self.class_options.scratch_slot_reservations,
            state_totals=self.class_options.state_totals,
        )

    def empty_statement(self, _stmt: mypy.nodes.Statement) -> None:
        return None

    def visit_function(
        self, func_def: mypy.nodes.FuncDef, decorator: mypy.nodes.Decorator | None
    ) -> None:
        func_loc = self._location(func_def)
        method_name = func_def.name

        if func_def.is_class:
            raise CodeError("@classmethod not supported", func_loc)
        if func_def.is_static:
            raise CodeError(
                "@staticmethod not supported, use a module level function instead", func_loc
            )
        if len(func_def.arguments) < 1:
            # since we checked we're only handling instance methods, should be at least one
            # argument to function - ie self
            logger.error(f"{method_name} should take a self parameter", location=func_loc)

        dec_by_fullname = get_decorators_by_fullname(self.context, decorator) if decorator else {}
        dec_by_fullname.pop("abc.abstractmethod", None)  # TODO: does this appear?
        subroutine_dec = dec_by_fullname.pop(constants.SUBROUTINE_HINT, None)
        abimethod_dec = dec_by_fullname.pop(constants.ABIMETHOD_DECORATOR, None)
        baremethod_dec = dec_by_fullname.pop(constants.BAREMETHOD_DECORATOR, None)

        for unknown_dec_fullname, dec in dec_by_fullname.items():
            self._error(f'unsupported decorator "{unknown_dec_fullname}"', dec)

        # TODO: handle difference of subroutine vs abimethod and overrides???

        arc4_method_data: ARC4MethodData | None = None
        if method_name in (_INIT_METHOD, constants.APPROVAL_METHOD, constants.CLEAR_STATE_METHOD):
            for invalid_dec in (subroutine_dec, abimethod_dec, baremethod_dec):
                if invalid_dec is not None:
                    self._error("method should not be decorated", location=invalid_dec)
        elif method_name.startswith("__") and method_name.endswith("__"):
            raise CodeError(
                "methods starting and ending with a double underscore"
                ' (aka "dunder" methods) are reserved for the Python data model'
                " (https://docs.python.org/3/reference/datamodel.html)."
                " Of these methods, only __init__ is supported in contract classes",
                func_loc,
            )
        elif not self._is_arc4:
            if subroutine_dec is None:
                logger.error(
                    f"missing @{constants.SUBROUTINE_HINT_ALIAS} decorator", location=func_loc
                )
            for invalid_dec in (abimethod_dec, baremethod_dec):
                if invalid_dec is not None:
                    self._error(
                        f"decorator is only valid in subclasses of {pytypes.ARC4ContractBaseType}",
                        invalid_dec,
                    )
        else:
            if len(list(filter(None, (subroutine_dec, abimethod_dec, baremethod_dec)))) != 1:
                logger.error(
                    f"ARC-4 contract member functions"
                    f" (other than __init__ or approval / clear program methods)"
                    f" must be annotated with exactly one of"
                    f" @{constants.SUBROUTINE_HINT_ALIAS},"
                    f" @{constants.ABIMETHOD_DECORATOR_ALIAS},"
                    f" or @{constants.BAREMETHOD_DECORATOR_ALIAS}",
                    location=func_loc,
                )

            if abimethod_dec:
                arc4_method_data = get_arc4_abimethod_data(self.context, abimethod_dec, func_def)
            elif baremethod_dec:
                arc4_method_data = get_arc4_baremethod_data(self.context, baremethod_dec, func_def)
            else:
                arc4_method_data = None
            # TODO: validate against super-class configs??

        source_location = self._location(decorator or func_def)
        obj = ContractFragmentMethod(
            member_name=method_name,
            source_location=source_location,
            metadata=arc4_method_data,
            is_trivial=func_def.is_trivial_body,
            synthetic=False,
            inheritable=True,
            implementation=None,
        )
        self.fragment.add_method(obj)
        if obj.is_trivial:
            logger.debug(f"skipping trivial method {method_name}", location=func_loc)
        else:
            self._deferred_methods.append(
                (
                    obj,
                    lambda ctx: FunctionASTConverter.convert(
                        ctx,
                        func_def=func_def,
                        source_location=source_location,
                        contract_method_info=ContractMethodInfo(
                            contract_type=self.typ,
                            type_info=self.class_def.info,
                            arc4_method_data=arc4_method_data,
                            cref=self.fragment.id,
                        ),
                    ),
                )
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


def _build_resolved_mro(
    context: ASTConversionModuleContext, contract_type: pytypes.ContractType
) -> list[ContractFragment]:
    class_def_loc = contract_type.source_location
    contract_bases_mro = list[ContractFragment]()
    for ancestor in contract_type.mro:
        if ancestor == pytypes.ContractBaseType:
            pass
        elif ancestor == pytypes.ARC4ContractBaseType:
            contract_bases_mro.append(_arc4_contract_fragment())
        elif isinstance(ancestor, pytypes.ContractType):
            contract_bases_mro.append(context.contract_fragments[ancestor.name])
        else:
            raise CodeError(f"base class {ancestor} is not a contract subclass", class_def_loc)
    return contract_bases_mro


def _arc4_contract_fragment() -> ContractFragment:

    fragment = ContractFragment(
        id=_ARC4_CONTRACT_BASE_CREF,
        source_location=_SYNTHETIC_LOCATION,
        mro=[],
        pytype=pytypes.ARC4ContractBaseType,
    )
    approval_program = _build_program_method(
        cref=_ARC4_CONTRACT_BASE_CREF,
        name=constants.APPROVAL_METHOD,
        location=_SYNTHETIC_LOCATION,
        body=[
            awst_nodes.ReturnStatement(
                value=awst_nodes.ARC4Router(source_location=_SYNTHETIC_LOCATION),
                source_location=_SYNTHETIC_LOCATION,
            )
        ],
    )
    clear_program = _build_program_method(
        cref=_ARC4_CONTRACT_BASE_CREF,
        name=constants.CLEAR_STATE_METHOD,
        location=_SYNTHETIC_LOCATION,
        body=[
            awst_nodes.ReturnStatement(
                value=awst_nodes.BoolConstant(value=True, source_location=_SYNTHETIC_LOCATION),
                source_location=_SYNTHETIC_LOCATION,
            )
        ],
    )
    fragment.add_method(
        ContractFragmentMethod(
            member_name=approval_program.member_name,
            source_location=approval_program.source_location,
            metadata=None,
            implementation=approval_program,
            is_trivial=False,
            synthetic=True,
            inheritable=True,
        )
    )
    fragment.add_method(
        ContractFragmentMethod(
            member_name=clear_program.member_name,
            source_location=clear_program.source_location,
            metadata=None,
            implementation=clear_program,
            is_trivial=False,
            synthetic=True,
            inheritable=True,
        )
    )
    return fragment


def _gather_app_storage_recursive(
    context: ASTConversionModuleContext,
    class_def: mypy.nodes.ClassDef,
    mro: Sequence[ContractReference],
) -> dict[str, AppStorageDeclaration]:
    this_global_directs = {
        defn.member_name: defn for defn in _gather_global_direct_storages(context, class_def.info)
    }
    combined_app_state = this_global_directs.copy()
    for base_cref in mro:
        base_app_state = {
            name: defn
            for name, defn in context.contract_fragments[base_cref].state_defs.items()
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
                # TODO: set these up but leave key
                continue

            if pytyp is pytypes.NoneType:
                logger.error(
                    "None is not supported as a value, only a return type", location=var_loc
                )
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


def _build_program_method(
    cref: ContractReference,
    name: str,
    location: SourceLocation,
    body: Sequence[awst_nodes.Statement],
    *,
    return_type: wtypes.WType = wtypes.bool_wtype,
) -> awst_nodes.ContractMethod:

    return awst_nodes.ContractMethod(
        cref=cref,
        member_name=name,
        source_location=location,
        args=[],
        arc4_method_config=None,
        return_type=return_type,
        documentation=awst_nodes.MethodDocumentation(),
        body=awst_nodes.Block(body=body, source_location=location),
    )
