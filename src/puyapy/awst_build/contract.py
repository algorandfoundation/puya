import abc
import contextlib
import typing
from collections.abc import Callable, Iterator, Sequence, Set

import attrs
import mypy.nodes
import mypy.types
import mypy.visitor

from puya import log
from puya.avm import OnCompletionAction
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.errors import CodeError, InternalError
from puya.parse import SourceLocation
from puya.program_refs import ContractReference
from puya.utils import StableSet, set_add, unique
from puyapy.awst_build import constants, intrinsic_factory, pytypes
from puyapy.awst_build.arc4_decorators import get_arc4_abimethod_data, get_arc4_baremethod_data
from puyapy.awst_build.base_mypy_visitor import BaseMyPyStatementVisitor
from puyapy.awst_build.context import ASTConversionModuleContext
from puyapy.awst_build.subroutine import ContractMethodInfo, FunctionASTConverter
from puyapy.awst_build.utils import get_decorators_by_fullname, get_subroutine_decorator_inline_arg
from puyapy.models import (
    ARC4BareMethodData,
    ARC4MethodData,
    ContractClassOptions,
    ContractFragmentBase,
    ContractFragmentMethod,
    ContractFragmentStorage,
)

logger = log.get_logger(__name__)

_ContractMethodBuilder: typing.TypeAlias = Callable[
    [ASTConversionModuleContext], awst_nodes.ContractMethod
]

_INIT_METHOD = "__init__"
_CONTRACT_BASE_CREF = ContractReference(constants.CONTRACT_BASE)
_ARC4_CONTRACT_BASE_CREF = ContractReference(constants.ARC4_CONTRACT_BASE)
_SYNTHETIC_LOCATION = SourceLocation(file=None, line=1)


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
        if class_options.state_totals is None:
            base_with_defined = next(
                (b for b in fragment_mro if b.options and (b.options.state_totals is not None)),
                None,
            )
            if base_with_defined:
                logger.warning(
                    f"Contract extends base contract {base_with_defined.id} "
                    "with explicit state_totals, but does not define its own state_totals. "
                    "This could result in insufficient reserved state at run time.",
                    location=class_loc,
                )

        self.fragment: typing.Final = _ContractFragment(
            id=typ.name,
            source_location=class_loc,
            pytype=typ,
            mro=fragment_mro,
            is_abstract=_check_class_abstractness(context, class_def),
            options=class_options,
            docstring=class_def.docstring,
        )

        # TODO: validation for state proxies being non-conditional
        _build_symbols_and_state(context, self.fragment, class_def.info.names)

        self._deferred_methods = list[tuple[ContractFragmentMethod, _ContractMethodBuilder]]()
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

        if (
            self.fragment.is_arc4
            and not self.fragment.is_abstract
            and not any(self.fragment.find_arc4_method_metadata(can_create=True))
        ):
            self._insert_default_arc4_create(self.fragment)
        context.add_contract_fragment(self.fragment)

    @staticmethod
    def _insert_default_arc4_create(fragment: "_ContractFragment") -> None:
        if any(fragment.find_arc4_method_metadata(bare=True, oca=OnCompletionAction.NoOp)):
            logger.error(
                "Non-abstract ARC-4 contract has no methods that can be called"
                " to create the contract, but does have a NoOp bare method,"
                " so one couldn't be inserted."
                " In order to allow creating the contract add either"
                " an @abimethod or @baremethod"
                ' decorated method with create="require" or create="allow"',
                location=fragment.source_location,
            )
        else:
            default_create_name = "__algopy_default_create"
            while fragment.resolve_symbol(default_create_name):  # ensure uniqueness
                default_create_name = f"_{default_create_name}"
            default_create_config = awst_nodes.ARC4BareMethodConfig(
                create=awst_nodes.ARC4CreateOption.require,
                source_location=_SYNTHETIC_LOCATION,
            )
            fragment.add_method(
                ContractFragmentMethod(
                    member_name=default_create_name,
                    source_location=_SYNTHETIC_LOCATION,
                    metadata=ARC4BareMethodData(
                        member_name=default_create_name,
                        pytype=(
                            pytypes.FuncType(
                                name=".".join((fragment.id, default_create_name)),
                                args=(),
                                ret_type=pytypes.NoneType,
                            )
                        ),
                        config=default_create_config,
                        source_location=_SYNTHETIC_LOCATION,
                    ),
                    is_trivial=False,
                    synthetic=True,
                    inheritable=False,
                    implementation=awst_nodes.ContractMethod(
                        cref=fragment.id,
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
                        inline=True,
                    ),
                )
            )

    def build(self, context: ASTConversionModuleContext) -> awst_nodes.Contract | None:
        for method_fragment, method_builder in self._deferred_methods:
            with context.log_exceptions(fallback_location=method_fragment.source_location):
                method_fragment.implementation = method_builder(context)

        if self.fragment.is_abstract:
            return None

        approval_program = None
        approval_method = self.fragment.resolve_method(constants.APPROVAL_METHOD)
        if approval_method is None or approval_method.is_trivial:
            logger.error(
                "non-abstract contract class missing approval program",
                location=self.fragment.source_location,
            )
        elif approval_method.implementation is None:
            pass  # error during method construction, already logged
        else:
            approval_program = approval_method.implementation
            match self.fragment.resolve_method(_INIT_METHOD):
                case None:
                    # we expect _at least_ algopy.Contract.__init__ to be resolved
                    raise InternalError(
                        "failed to resolve any __init__ method", self.fragment.source_location
                    )
                case ContractFragmentMethod(
                    implementation=awst_nodes.ContractMethod(body=awst_nodes.Block(body=[])),
                    synthetic=True,
                ):
                    # in the case where algopy.Contract.__init__ is the only method,
                    # don't insert call-on-create as it can have deleterious effects on
                    # optimisation, particularly in subroutine inlining
                    pass
                case _:
                    approval_program = _insert_init_call_on_create(
                        current_contract=self.fragment.id,
                        approval_method_return_type=approval_program.return_type,
                    )

        clear_method = self.fragment.resolve_method(constants.CLEAR_STATE_METHOD)
        if clear_method is None or clear_method.is_trivial:
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
            name=self.fragment.options.name_override or self.fragment.pytype.class_name,
            method_resolution_order=[ancestor.id for ancestor in self.fragment.mro],
            approval_program=approval_program,
            clear_program=clear_program,
            methods=tuple(
                cm.implementation
                for cm in self.fragment.methods(include_overridden=True)
                if cm.implementation is not None
            ),
            app_state=tuple(
                state_decl.definition
                for state_decl in self.fragment.state()
                if state_decl.definition is not None
            ),
            description=self.fragment.docstring,
            source_location=self.fragment.source_location,
            reserved_scratch_space=self.fragment.reserved_scratch_space,
            state_totals=self.fragment.options.state_totals,
            avm_version=self.fragment.options.avm_version,
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
        if func_def.type is None:
            raise CodeError("function is untyped", func_loc)
        if len(func_def.arguments) < 1:
            # since we checked we're only handling instance methods, should be at least one
            # argument to function - ie self
            logger.error(f"{method_name} should take a self parameter", location=func_loc)

        dec_by_fullname = get_decorators_by_fullname(self.context, decorator) if decorator else {}
        subroutine_dec = dec_by_fullname.pop(constants.SUBROUTINE_HINT, None)
        abimethod_dec = dec_by_fullname.pop(constants.ABIMETHOD_DECORATOR, None)
        baremethod_dec = dec_by_fullname.pop(constants.BAREMETHOD_DECORATOR, None)

        for unknown_dec_fullname, dec in dec_by_fullname.items():
            self._error(f'unsupported decorator "{unknown_dec_fullname}"', dec)

        # TODO: handle difference of subroutine vs abimethod and overrides???

        inline = None
        if subroutine_dec is not None:
            inline = get_subroutine_decorator_inline_arg(self.context, subroutine_dec)

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
        elif not self.fragment.is_arc4:
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
                        inline=inline,
                        contract_method_info=ContractMethodInfo(
                            fragment=self.fragment,
                            contract_type=self.fragment.pytype,
                            arc4_method_config=(
                                arc4_method_data.config if arc4_method_data else None
                            ),
                            is_abstract=self.fragment.is_abstract,
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


class _UserContractBase(ContractFragmentBase, abc.ABC):
    @property
    @abc.abstractmethod
    def options(self) -> ContractClassOptions | None: ...


@attrs.frozen
class _StaticContractBase(_UserContractBase):
    id: ContractReference
    methods_: dict[str, ContractFragmentMethod]
    mro: Sequence[ContractFragmentBase]
    symbols: dict[str, pytypes.PyType]
    options: None = None

    @typing.override
    def resolve_method(
        self, name: str, *, include_inherited: bool = True
    ) -> ContractFragmentMethod | None:
        return self.methods_.get(name)

    @typing.override
    def methods(
        self, *, include_inherited: bool = True, include_overridden: bool = False
    ) -> Iterator[ContractFragmentMethod]:
        yield from self.methods_.values()

    @typing.override
    def resolve_storage(
        self, name: str, *, include_inherited: bool = True
    ) -> ContractFragmentStorage | None:
        return None

    @typing.override
    def state(self, *, include_inherited: bool = True) -> Iterator[ContractFragmentStorage]:
        yield from ()

    def add_stub_method(
        self,
        name: str,
        body: Sequence[awst_nodes.Statement],
        *,
        return_type: pytypes.RuntimeType = pytypes.BoolType,
    ) -> None:
        self.symbols[name] = pytypes.FuncType(
            name=".".join((self.id, name)),
            args=(),
            ret_type=return_type,
        )
        implementation = awst_nodes.ContractMethod(
            cref=self.id,
            member_name=name,
            source_location=_SYNTHETIC_LOCATION,
            args=[],
            arc4_method_config=None,
            return_type=return_type.wtype,
            documentation=awst_nodes.MethodDocumentation(),
            body=awst_nodes.Block(body=body, source_location=_SYNTHETIC_LOCATION),
            inline=None,
        )
        self.methods_[name] = ContractFragmentMethod(
            member_name=name,
            source_location=_SYNTHETIC_LOCATION,
            metadata=None,
            is_trivial=False,
            synthetic=True,
            inheritable=True,
            implementation=implementation,
        )


@attrs.frozen(kw_only=True)
class _ContractFragment(_UserContractBase):
    id: ContractReference
    source_location: SourceLocation
    pytype: pytypes.ContractType
    mro: Sequence[_UserContractBase]
    is_abstract: bool
    options: ContractClassOptions
    docstring: str | None
    _methods: dict[str, ContractFragmentMethod] = attrs.field(factory=dict, init=False)
    _state_defs: dict[str, ContractFragmentStorage] = attrs.field(factory=dict, init=False)
    symbols: dict[str, pytypes.PyType | None] = attrs.field(factory=dict, init=False)

    @property
    def is_arc4(self) -> bool:
        return pytypes.ARC4ContractBaseType in self.pytype.mro

    def add_method(self, method: ContractFragmentMethod) -> None:
        set_result = self._methods.setdefault(method.member_name, method)
        if set_result is not method:
            logger.info(
                f"previous definition of {method.member_name} was here",
                location=set_result.source_location,
            )
            logger.error(
                f"redefinition of {method.member_name}",
                location=method.source_location,
            )

    @typing.override
    def resolve_method(
        self, name: str, *, include_inherited: bool = True
    ) -> ContractFragmentMethod | None:
        with contextlib.suppress(KeyError):
            return self._methods[name]
        if include_inherited:
            for fragment in self.mro:
                method = fragment.resolve_method(name, include_inherited=False)
                if method and method.inheritable:
                    return method
        return None

    @typing.override
    def methods(
        self, *, include_inherited: bool = True, include_overridden: bool = False
    ) -> Iterator[ContractFragmentMethod]:
        yield from self._methods.values()
        if include_inherited:
            seen_names = set(self._methods.keys())
            for fragment in self.mro:
                for method in fragment.methods(include_inherited=False):
                    if method.inheritable and (
                        include_overridden or set_add(seen_names, method.member_name)
                    ):
                        yield method

    @typing.override
    def resolve_storage(
        self, name: str, *, include_inherited: bool = True
    ) -> ContractFragmentStorage | None:
        with contextlib.suppress(KeyError):
            return self._state_defs[name]
        if include_inherited:
            for fragment in self.mro:
                result = fragment.resolve_storage(name, include_inherited=False)
                if result is not None:
                    return result
        return None

    def add_state(self, decl: ContractFragmentStorage) -> None:
        existing = self.resolve_storage(decl.member_name)
        self._state_defs.setdefault(decl.member_name, decl)
        if existing is not None:
            logger.info(
                f"previous definition of {decl.member_name} was here",
                location=existing.source_location,
            )
            logger.error(
                f"redefinition of {decl.member_name}",
                location=decl.source_location,
            )

    @typing.override
    def state(self, *, include_inherited: bool = True) -> Iterator[ContractFragmentStorage]:
        result = self._state_defs
        if include_inherited:
            for ancestor in self.mro:
                result = {
                    s.member_name: s for s in ancestor.state(include_inherited=False)
                } | result
        yield from result.values()

    @property
    def reserved_scratch_space(self) -> Set[int]:
        return StableSet[int].from_iter(
            num
            for c in (self, *self.mro)
            if c.options and c.options.scratch_slot_reservations
            for num in c.options.scratch_slot_reservations
        )


def _insert_init_call_on_create(
    current_contract: ContractReference, *, approval_method_return_type: wtypes.WType
) -> awst_nodes.ContractMethod:
    call_init = awst_nodes.Block(
        comment="call __init__",
        body=[
            awst_nodes.ExpressionStatement(
                expr=awst_nodes.SubroutineCallExpression(
                    target=awst_nodes.InstanceMethodTarget(member_name=_INIT_METHOD),
                    args=[],
                    wtype=wtypes.void_wtype,
                    source_location=_SYNTHETIC_LOCATION,
                )
            )
        ],
        source_location=_SYNTHETIC_LOCATION,
    )
    call_init_on_create = awst_nodes.IfElse(
        condition=awst_nodes.Not(
            expr=intrinsic_factory.txn("ApplicationID", wtypes.bool_wtype, _SYNTHETIC_LOCATION),
            source_location=_SYNTHETIC_LOCATION,
        ),
        if_branch=call_init,
        else_branch=None,
        source_location=_SYNTHETIC_LOCATION,
    )
    return awst_nodes.ContractMethod(
        cref=current_contract,
        member_name="__algopy_entrypoint_with_init",
        args=[],
        arc4_method_config=None,
        return_type=approval_method_return_type,
        documentation=awst_nodes.MethodDocumentation(),
        body=awst_nodes.Block(
            body=[
                call_init_on_create,
                awst_nodes.ReturnStatement(
                    value=awst_nodes.SubroutineCallExpression(
                        target=awst_nodes.InstanceMethodTarget(
                            member_name=constants.APPROVAL_METHOD,
                        ),
                        args=[],
                        wtype=approval_method_return_type,
                        source_location=_SYNTHETIC_LOCATION,
                    ),
                    source_location=_SYNTHETIC_LOCATION,
                ),
            ],
            source_location=_SYNTHETIC_LOCATION,
        ),
        source_location=_SYNTHETIC_LOCATION,
    )


def _build_resolved_mro(
    context: ASTConversionModuleContext, contract_type: pytypes.ContractType
) -> list[_UserContractBase]:
    class_def_loc = contract_type.source_location
    contract_bases_mro = list[_UserContractBase]()
    for ancestor in contract_type.mro:
        if ancestor == pytypes.ContractBaseType:
            contract_bases_mro.append(_base_contract_fragment())
        elif ancestor == pytypes.ARC4ContractBaseType:
            contract_bases_mro.append(_arc4_contract_fragment())
        elif isinstance(ancestor, pytypes.ContractType):
            ancestor_fragment = context.contract_fragments.get(ancestor.name)
            if isinstance(ancestor_fragment, _ContractFragment):
                contract_bases_mro.append(ancestor_fragment)
            else:
                raise CodeError(
                    f"contract type has non-contract base {ancestor.name}", class_def_loc
                )
        else:
            raise CodeError(f"base class {ancestor} is not a contract subclass", class_def_loc)
    return contract_bases_mro


def _base_contract_fragment() -> _UserContractBase:
    result = _StaticContractBase(
        id=_CONTRACT_BASE_CREF,
        mro=(),
        methods_={},
        symbols={},
    )
    result.add_stub_method(
        name=_INIT_METHOD,
        body=[],
        return_type=pytypes.NoneType,
    )
    return result


def _arc4_contract_fragment() -> _UserContractBase:
    result = _StaticContractBase(
        id=_ARC4_CONTRACT_BASE_CREF,
        mro=(_base_contract_fragment(),),
        methods_={},
        symbols={},
    )
    result.add_stub_method(
        name=constants.APPROVAL_METHOD,
        body=[
            awst_nodes.ReturnStatement(
                value=awst_nodes.ARC4Router(source_location=_SYNTHETIC_LOCATION),
                source_location=_SYNTHETIC_LOCATION,
            )
        ],
    )
    result.add_stub_method(
        name=constants.CLEAR_STATE_METHOD,
        body=[
            awst_nodes.ReturnStatement(
                value=awst_nodes.BoolConstant(value=True, source_location=_SYNTHETIC_LOCATION),
                source_location=_SYNTHETIC_LOCATION,
            )
        ],
    )
    return result


def _build_symbols_and_state(
    context: ASTConversionModuleContext,
    fragment: _ContractFragment,
    symtable: mypy.nodes.SymbolTable,
) -> None:
    cref = fragment.id
    for name, sym in symtable.items():
        node = sym.node
        assert node, f"mypy cross reference remains unresolved: member {name!r} of {cref!r}"
        node_loc = context.node_location(node)
        if isinstance(node, mypy.nodes.OverloadedFuncDef):
            node = node.impl
        if isinstance(node, mypy.nodes.Decorator):
            # we don't support any decorators that would change signature
            node = node.func
        pytyp = None
        if isinstance(node, mypy.nodes.Var | mypy.nodes.FuncDef) and node.type:
            with contextlib.suppress(CodeError):
                pytyp = context.type_to_pytype(node.type, source_location=node_loc)

        fragment.symbols[name] = pytyp
        if pytyp and not isinstance(pytyp, pytypes.FuncType):
            definition = None
            if isinstance(pytyp, pytypes.StorageProxyType):
                match pytyp.generic:
                    case pytypes.GenericLocalStateType:
                        kind = awst_nodes.AppStorageKind.account_local
                    case pytypes.GenericGlobalStateType:
                        kind = awst_nodes.AppStorageKind.app_global
                    case pytypes.GenericBoxType:
                        kind = awst_nodes.AppStorageKind.box
                    case None if pytyp == pytypes.BoxRefType:
                        kind = awst_nodes.AppStorageKind.box
                    case _:
                        raise InternalError(f"unhandled StorageProxyType: {pytyp}", node_loc)
            elif isinstance(pytyp, pytypes.StorageMapProxyType):
                if pytyp.generic != pytypes.GenericBoxMapType:
                    raise InternalError(f"unhandled StorageMapProxyType: {pytyp}", node_loc)
                kind = awst_nodes.AppStorageKind.box
            else:  # global state, direct
                wtype = pytyp.checked_wtype(node_loc)
                key = awst_nodes.BytesConstant(
                    value=name.encode("utf8"),
                    encoding=awst_nodes.BytesEncoding.utf8,
                    source_location=node_loc,
                    wtype=wtypes.state_key,
                )
                kind = awst_nodes.AppStorageKind.app_global
                definition = awst_nodes.AppStorageDefinition(
                    source_location=node_loc,
                    member_name=name,
                    kind=kind,
                    storage_wtype=wtype,
                    key_wtype=None,
                    key=key,
                    description=None,
                )
            fragment.add_state(
                ContractFragmentStorage(
                    member_name=name,
                    kind=kind,
                    definition=definition,
                    source_location=node_loc,
                )
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
