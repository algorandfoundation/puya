# type: ignore
# ruff: noqa
import inspect
import typing
from textwrap import dedent

import mypy.build
import mypy.find_sources
import mypy.fscache
import mypy.nodes
import mypy.options
import mypy.types
import pytest

from puya.compile import get_mypy_options


def get_assignment_var_named(mypy_file: mypy.nodes.MypyFile, name: str) -> mypy.nodes.Var:
    for assignment in [
        stmt for stmt in mypy_file.defs if isinstance(stmt, mypy.nodes.AssignmentStmt)
    ]:
        for lvalue in assignment.lvalues:
            if isinstance(lvalue, mypy.nodes.NameExpr) and lvalue.name == name:
                assert isinstance(lvalue.node, mypy.nodes.Var)
                return lvalue.node
    raise Exception(f"Assignment to '{name}' not found")


def get_class_by_name(mypy_file: mypy.nodes.MypyFile, name: str) -> mypy.nodes.ClassDef:
    for cls_def in (stmt for stmt in mypy_file.defs if isinstance(stmt, mypy.nodes.ClassDef)):
        if cls_def.name == name:
            return cls_def
    raise Exception(f"Assignment to '{name}' not found")


def decompile(function: typing.Callable) -> str:
    source = inspect.getsource(function)
    return dedent("\n".join(source.splitlines()[1:]))


TEST_MODULE = "__test__"


def mypy_parse_and_type_check(source: str | typing.Callable) -> mypy.build.BuildResult:
    code = source if isinstance(source, str) else decompile(source)
    options = get_mypy_options()

    sources = [mypy.build.BuildSource(None, TEST_MODULE, text=dedent(code))]

    return mypy.build.build(sources=sources, options=options)


def strip_error_prefixes(br: mypy.build.BuildResult) -> list[str]:
    return [e.split(":", maxsplit=2)[-1].strip() for e in br.errors]


def get_revealed_types(br: mypy.build.BuildResult, tree: mypy.nodes.MypyFile) -> list[str]:
    types = []
    for stmt in tree.defs:
        match stmt:
            case mypy.nodes.ExpressionStmt(
                expr=mypy.nodes.CallExpr(analyzed=mypy.nodes.RevealExpr(expr=expr))
            ):
                et = br.types[expr]
                types.append(repr(et))
    return types


def test_ignore_assignment() -> None:
    def test():
        a_lie: int = "bar"  # type: ignore[assignment]

    result = mypy_parse_and_type_check(test)
    assert not result.errors
    module = result.graph[TEST_MODULE]
    assert module.tree
    assert module.tree.ignored_lines == {1: ["assignment"]}


def test_incorrect_assignment() -> None:
    def test():
        wrong: int = "bar"

    result = mypy_parse_and_type_check(test)
    assert result.errors
    assert result.errors[0].endswith("[assignment]")


def test_cast() -> None:
    def test():
        import typing

        wrong: int = typing.cast(int, "bar")

    result = mypy_parse_and_type_check(test)
    tree = result.graph[TEST_MODULE].tree
    assert tree
    var = get_assignment_var_named(tree, "wrong")
    assert str(var.type) == "builtins.int"


def test_implicit_cast() -> None:
    def test():
        import typing

        wrong_implicit = typing.cast(int, "bar")

    result = mypy_parse_and_type_check(test)
    tree = result.graph[TEST_MODULE].tree
    assert tree
    var = get_assignment_var_named(tree, "wrong_implicit")
    assert str(var.type) == "builtins.int"


@pytest.mark.xfail(reason="The observed behaviour here changed after updating mypy to 1.5.0")
def test_assert_isinstance_does_not_cast() -> None:
    def test():
        an_int: int = 123
        assert isinstance(an_int, str)

        another_int = an_int  # despite earlier assert, an_int is still seen as a int

    result = mypy_parse_and_type_check(test)
    tree = result.graph[TEST_MODULE].tree
    assert tree
    var = get_assignment_var_named(tree, "another_int")
    assert str(var.type) == "builtins.int"


def test_assert_isinstance_does_narrow() -> None:
    def test():
        import typing

        an_int: typing.Any = 123
        assert isinstance(an_int, str)

        another_int = an_int  # earlier assert narrows from Any to str

    result = mypy_parse_and_type_check(test)
    tree = result.graph[TEST_MODULE].tree
    assert tree
    var = get_assignment_var_named(tree, "another_int")
    assert str(var.type) == "builtins.str"


def test_name_defined():
    def test():
        error = missing + 2  # type: ignore[name-defined]

    result = mypy_parse_and_type_check(test)
    tree = result.graph[TEST_MODULE].tree
    match tree:
        case mypy.nodes.MypyFile(
            defs=[
                mypy.nodes.AssignmentStmt(
                    rvalue=mypy.nodes.OpExpr(left=mypy.nodes.NameExpr(name="missing") as missing),
                )
            ]
        ):
            assert missing.node is None
        case _:
            raise AssertionError


# TODO: override, what does the type information look like when call these?


def test_ignore_override() -> None:
    def test():
        class ABase:
            def method(self, x: int) -> int:
                return x

        class ADerived(ABase):
            def method(self, x: int) -> str:  # type: ignore[override]
                return str(x)

        class BBase:
            def call(self, o: ABase) -> int:
                result = o.method(42)
                return result

        class BDerived(BBase):
            def call(self, o: ADerived) -> str:  # type: ignore[override]
                result = o.method(42)
                return result

        base_base_result = BBase().call(ABase())
        base_derived_result = BBase().call(ADerived())
        derived_base_result = BDerived().call(ABase())
        derived_derived_result = BDerived().call(ADerived())

    result = mypy_parse_and_type_check(test)
    tree = result.graph[TEST_MODULE].tree
    assert tree

    test()


def test_super_no_args_outside_method() -> None:
    def test():
        def function() -> None:
            super().__init__()

            class Obj:
                pass

            print(super(Obj, Obj()).__str__())

    result = mypy_parse_and_type_check(test)
    assert result.errors == ['<string>:2: error: "super" used outside class  [misc]']


def test_aliased_import() -> None:
    def test():
        from collections import abc as xyz

        hmm = xyz

    result = mypy_parse_and_type_check(test)
    tree = result.graph[TEST_MODULE].tree
    assert tree.defs[-1].rvalue.fullname == "collections.abc"
    assert tree.names["xyz"].fullname == "collections.abc"


def test_function_redefinition() -> None:
    def test():
        def foo(x: int) -> int:
            return 2 * x

        def foo(x: str) -> str:
            return 2 * x

        bar = foo("1")

    result = mypy_parse_and_type_check(test)
    tree = result.graph[TEST_MODULE].tree
    assert result.errors == [
        '<string>:4: error: Name "foo" already defined on line 1  [no-redef]',
        '<string>:7: error: Argument 1 to "foo" has incompatible type "str"; expected "int"  [arg-type]',
    ]
    assert tree.defs[-1].rvalue.callee.node is tree.defs[0]


def test_class_members() -> None:
    def test():
        from typing import ClassVar, Final

        class Class:
            class_var: ClassVar = 1
            class_var_implicit = 2
            class_var_implicit_final: Final = 3

            decl_only: int
            decl_and_set_in_init: int
            decl_and_set_in_method: int
            decl_only_final: Final[int]

            def __init__(self) -> None:
                self.decl_and_set_in_init = 100
                self.new_var_in_init = 101
                self.new_final_var_in_init: Final = 102
                self.decl_only_final = 103

            def method(self) -> None:
                self.decl_and_set_in_method = 200
                self.new_var_in_method = 201
                self.new_final_far_in_method: Final = 202

        obj = Class()
        assert not hasattr(Class, "decl_only")
        assert not hasattr(Class, "decl_and_set_in_init")
        assert not hasattr(obj, "decl_only")
        assert hasattr(obj, "decl_and_set_in_init")

    test()
    result = mypy_parse_and_type_check(test)
    assert len(result.errors) == 1
    assert result.errors[0].endswith(
        "error: Can only declare a final attribute in class body or __init__  [misc]"
    )
    tree = result.graph[TEST_MODULE].tree
    assert tree
    cls_def = tree.defs[1]
    assert isinstance(cls_def, mypy.nodes.ClassDef)
    symtable = cls_def.info.names.copy()
    del symtable["__init__"]
    del symtable["method"]
    assert symtable.keys() == {
        "class_var",
        "class_var_implicit",
        "class_var_implicit_final",
        "decl_and_set_in_init",
        "decl_and_set_in_method",
        "decl_only",
        "decl_only_final",
        "new_final_far_in_method",
        "new_final_var_in_init",
        "new_var_in_init",
        "new_var_in_method",
    }
    vars_ = {}
    for name, sym in symtable.items():
        assert sym.kind == mypy.nodes.MDEF  # THE M STANDS FOR MEMBER.. REMEMBER... REMEMMMMBEERRR
        if name.startswith("new_"):
            assert sym.implicit
        else:
            assert not sym.implicit
        assert isinstance(sym.node, mypy.nodes.Var)
        # unfortunate that implicit class vars and not detected as such :(
        assert sym.node.is_classvar == (name == "class_var")
        # can't use is_initialized_in_class either, it is True even when it's just declared
        assert sym.node.is_initialized_in_class == (
            name.startswith("class_var") or name.startswith("decl_")
        )
        vars_[name] = sym.node
    # note this does nothing v
    typing.assert_type(vars_, dict[str, mypy.nodes.Var])


def test_abc() -> None:
    # TODO: FINISH THIS
    def test():
        from abc import ABC, abstractmethod
        import pytest

        class Base(ABC):
            def concrete(self) -> int:
                return id(self)

            @abstractmethod
            def explicit_abstract_ellipsis(self) -> int: ...

            @abstractmethod
            def explicit_abstract_raise_not_implemented(self) -> int:
                raise NotImplementedError

            @abstractmethod
            def explicit_abstract_pass(self) -> int:
                pass

            @abstractmethod
            def explicit_abstract_docstring_only(self) -> int:
                """This is a docstring"""

            @abstractmethod
            def explicit_abstract_with_impl(self, x: int) -> int:
                return x + 1

            def implicit_abstract_returning_int(self) -> int:
                raise NotImplementedError

        class DerivedPass(Base):
            pass

        class DerivedABCPass(Base, ABC):
            pass

        class DerivedPartial(Base):
            def explicit_abstract_ellipsis(self) -> int:
                return 42

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            base = Base()
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            derived_pass = DerivedPass()
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            derived_abc_pass = DerivedABCPass()
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            derived_partial = DerivedPartial()

    test()
    result = mypy_parse_and_type_check(test)
    # assert not result.errors
    tree = result.graph[TEST_MODULE].tree
    assert tree


# TODO: various member/class var decls, protocol handling, special decorators,
#       metaclass, generics, etc
#


# TODO: Protocol tests


def test_nested_class() -> None:
    def test() -> None:
        class Outer:
            outer_mem: int = 1

            class Inner:
                inner_mem: int = 2

            inner_inst = Inner()

        outer_inst = Outer()
        assert outer_inst

    test()
    result = mypy_parse_and_type_check(test)
    tree = result.graph[TEST_MODULE].tree
    assert tree


def test_final_method() -> None:
    def test() -> None:
        import typing

        class Class:
            @typing.final
            def meaning_of_life(self) -> int:
                return 42

    result = mypy_parse_and_type_check(test)
    tree = result.graph[TEST_MODULE].tree
    assert tree
    class_def = tree.defs[-1]
    assert isinstance(class_def, mypy.nodes.ClassDef)
    deco = class_def.defs.body[0]
    assert isinstance(deco, mypy.nodes.Decorator)
    assert deco.decorators == []
    assert deco.is_final
    assert deco.func.is_final


def test_notypecheck_func() -> None:
    def test() -> None:
        import typing

        @typing.no_type_check
        def my_func(x: dict):
            return x + "lol"

    result = mypy_parse_and_type_check(test)
    tree = result.graph[TEST_MODULE].tree
    assert tree
    deco = tree.defs[-1]
    assert isinstance(deco, mypy.nodes.Decorator)
    assert deco.decorators, "please don't strip the no_type_check decorator mypy..."


def test_chained_assignment_lvalue_order() -> None:
    def test():
        outer = inner = 0

    result = mypy_parse_and_type_check(test)
    assert not result.errors
    tree = result.graph[TEST_MODULE].tree
    assert tree
    assert len(tree.defs) == 1
    assignment_stmt = tree.defs[0]
    assert isinstance(assignment_stmt, mypy.nodes.AssignmentStmt)
    lvalues = assignment_stmt.lvalues
    assert len(lvalues) == 2
    first, second = lvalues
    assert isinstance(first, mypy.nodes.NameExpr) and first.name == "outer"
    assert isinstance(second, mypy.nodes.NameExpr) and second.name == "inner"


def test_list_expr_assignment_target() -> None:
    """MyPy translates assignment targets with list to tuple"""

    def test():
        [a, b] = 1, 2
        [head, *tail] = [1, 2, 3]

    result = mypy_parse_and_type_check(test)
    assert not result.errors
    tree = result.graph[TEST_MODULE].tree
    assert tree and len(tree.defs) == 2
    for stmt in tree.defs:
        assert isinstance(stmt, mypy.nodes.AssignmentStmt)
        lvalues = stmt.lvalues
        assert len(lvalues) == 1
        assert isinstance(lvalues[0], mypy.nodes.TupleExpr)


def test_assignment_statements() -> None:
    def test():
        class Base:
            var: str

        class Obj(Base):
            def __init__(self) -> None:
                self._tmp = "tmp"
                Obj._tmp = "WHY"
                self._tmp2: int
                self._tmp2 = 123
                self._tmp3: int = len(self._tmp)

            def method(self) -> None:
                self.x: int
                self.x = 2
                self.y = 3
                self.z: int

        lst = [1, 2]
        tup0, tup1 = lst
        star0, *star_rest = lst
        foo, (bar, *baz) = (tup0, (tup1, star0, *star_rest))
        x: int
        x = 0
        lst[2:] = [3, 4]
        o = Obj()
        o.var = "a"
        Obj().var = "b"
        super(Obj, o).var = "c"  # type: ignore[misc]
        d = dict[str, int]()
        d["key"] = x
        o.method()
        ox = o.x

    result = mypy_parse_and_type_check(test)
    assert not result.errors
    tree = result.graph[TEST_MODULE].tree
    assert tree

    import mypy.traverser

    class MyVisitor(mypy.traverser.TraverserVisitor):
        def visit_assignment_stmt(self, stmt: mypy.nodes.AssignmentStmt) -> None:
            (lval,) = stmt.lvalues
            assert isinstance(
                lval,
                mypy.nodes.MemberExpr
                | mypy.nodes.NameExpr
                | mypy.nodes.TupleExpr
                | mypy.nodes.SuperExpr
                | mypy.nodes.IndexExpr,
            )
            if isinstance(lval, mypy.nodes.MemberExpr) and lval.def_var is not None:
                assert lval.def_var is lval.node
            if isinstance(stmt.rvalue, mypy.nodes.TempNode) and stmt.rvalue.no_rhs:
                assert stmt.type is not None
                assert lval.is_new_def
            super().visit_assignment_stmt(stmt)

    vis = MyVisitor()
    tree.accept(vis)


def test_super_exprs() -> None:
    def test():
        class Base:
            def __init__(self, x: int) -> None:
                self.x = x
                self.var: int = 0

            def method(self) -> int:
                return self.x

        class Derived(Base):
            def __init__(self, x: int, y: int) -> None:
                super().__init__(x=x)
                super(Base, self).var = 123  # type: ignore[misc]
                self.y = y

            def method(self) -> int:
                return super().method() + self.y

    result = mypy_parse_and_type_check(test)
    tree = result.graph[TEST_MODULE].tree
    assert tree
    assert not result.errors


def test_special_decorators() -> None:
    def test() -> None:
        import abc
        import typing

        class Class(abc.ABC):
            @property
            def prop_get_set_del(self) -> int:
                return self._x

            @prop_get_set_del.setter
            def prop_get_set_del(self, value: int) -> None:
                self._x = value

            @prop_get_set_del.deleter
            def prop_get_set_del(self) -> None:
                del self._x

            @property
            def prop_get_set(self) -> str:
                return self._y

            @prop_get_set.setter
            def prop_get_set(self, value: str) -> None:
                self._y = value

            @property
            def prop_get(self) -> bytes:
                return b""

            @abc.abstractmethod
            def abstract_method(self, x: str) -> str: ...

            @staticmethod
            def static() -> int:
                return 42

            @classmethod
            def klass(cls) -> int:
                return cls().static()

            @typing.overload
            def overloaded(self, x: int) -> None: ...

            @typing.overload
            def overloaded(self, x: str) -> None: ...

            def overloaded(self, x: int | str) -> None:
                if isinstance(x, int):
                    self.prop_get_set_del = x
                else:
                    self.prop_get_set = x

    test()
    result = mypy_parse_and_type_check(test)
    assert not result.errors
    tree = result.graph[TEST_MODULE].tree
    assert tree
    class_def = tree.defs[-1]
    assert isinstance(class_def, mypy.nodes.ClassDef)


def test_variadic_tuple_type() -> None:
    def test():
        from collections.abc import Sequence

        def func(items: Sequence[int]) -> tuple[int, ...]:
            return tuple(items)

        def func2(items: Sequence[int]) -> tuple[int, int]:
            return items[0], len(items)

        x = func([1, 2, 3])
        y = func2([1, 2, 3])

    test()
    result = mypy_parse_and_type_check(test)
    assert not result.errors
    tree = result.graph[TEST_MODULE].tree
    assert tree
    func = tree.defs[1]
    assert isinstance(func, mypy.nodes.FuncDef)
    assert isinstance(func.type, mypy.types.CallableType)
    assert type(func.type.ret_type) == mypy.types.Instance
    func2 = tree.defs[2]
    assert isinstance(func2, mypy.nodes.FuncDef)
    assert isinstance(func2.type, mypy.types.CallableType)
    assert type(func2.type.ret_type) == mypy.types.TupleType


def test_tuple_covariance() -> None:
    def test():
        class Base:
            pass

        class Derived(Base):
            pass

        def func_out() -> tuple[Base, object]:
            return Derived(), 1

        def func_in(a: tuple[Base, object]) -> None:
            print(a)

        func_in((Derived(), 2))

    test()
    result = mypy_parse_and_type_check(test)
    assert not result.errors
    tree = result.graph[TEST_MODULE].tree
    assert tree


def test_if_else_expr_combined_type() -> None:
    def test():
        import typing

        def random() -> float:
            return 0.1

        class Base:
            pass

        class Derived(Base):
            pass

        typing.reveal_type(Base() if random() > 0.5 else Derived())

        typing.reveal_type("str" if random() < 0.5 else 1)
        okay: str | int = "str" if random() < 0.5 else 1
        typing.reveal_type(okay)
        bad: str = "str" if random() == 1 else 1

    result = mypy_parse_and_type_check(test)
    assert strip_error_prefixes(result) == [
        'note: Revealed type is "__test__.Base"',
        'note: Revealed type is "builtins.object"',
        'note: Revealed type is "Union[builtins.str, builtins.int]"',
        'error: Incompatible types in assignment (expression has type "object",'
        ' variable has type "str")  [assignment]',
    ]
    tree = result.graph[TEST_MODULE].tree
    assert tree
    assert get_revealed_types(result, tree) == [
        "__test__.Base",
        "builtins.object",
        "Union[builtins.str, builtins.int]",
    ]


def test_or_expr_combined_type() -> None:
    def test():
        import typing

        def random() -> float:
            return 0.1

        class Base:
            def __bool__(self) -> bool:
                return random() < 0.5

        class Derived(Base):
            pass

        typing.reveal_type(Base() or Derived())
        typing.reveal_type(Derived() or Base())
        true = True
        typing.reveal_type(true or Base())
        one = 1
        typing.reveal_type(Base() or one)
        bad: Derived = Base() or Derived()
        okay: Base = Base() or Derived()

    result = mypy_parse_and_type_check(test)
    assert strip_error_prefixes(result) == [
        'note: Revealed type is "__test__.Base"',
        'note: Revealed type is "__test__.Base"',
        'note: Revealed type is "Union[Literal[True], __test__.Base]"',
        'note: Revealed type is "Union[__test__.Base, builtins.int]"',
        'error: Incompatible types in assignment (expression has type "Base",'
        ' variable has type "Derived")  [assignment]',
    ]
    tree = result.graph[TEST_MODULE].tree
    assert tree
    assert get_revealed_types(result, tree) == [
        "__test__.Base",
        "__test__.Base",
        "Union[Literal[True], __test__.Base]",
        "Union[__test__.Base, builtins.int]",
    ]


def test_global_types() -> None:
    def test():
        import typing

        a = "a"
        b: typing.Final = "b"
        c = a + b
        d: typing.Final = a + b
        one = 1
        two: typing.Final = 2
        three = one + two
        four: typing.Final = three + one
        true = True
        false: typing.Final = False
        true_and_false = true and false
        true_or_false: typing.Final = true or false
        b_a = b"a"
        b_b: typing.Final = b"b"
        b_c = b_a + b_b
        b_d: typing.Final = 2 * b_b

        def silly_function() -> None:
            print(
                a,
                b,
                c,
                d,
                one,
                two,
                three,
                four,
                true,
                false,
                true_and_false,
                true_or_false,
                b_a,
                b_b,
                b_c,
                b_d,
            )

    result = mypy_parse_and_type_check(test)
    tree = result.graph[TEST_MODULE].tree
    assert tree
    silly_func_def = tree.defs[-1]
    assert isinstance(silly_func_def, mypy.nodes.FuncDef)
    assert len(silly_func_def.body.body) == 1
    print_stmt = silly_func_def.body.body[0]
    assert isinstance(print_stmt, mypy.nodes.ExpressionStmt)
    print_call = print_stmt.expr
    assert isinstance(print_call, mypy.nodes.CallExpr)
    for arg_name_expr in print_call.args:
        assert isinstance(arg_name_expr, mypy.nodes.NameExpr)
        assert arg_name_expr.kind == mypy.nodes.GDEF
        assert not (
            arg_name_expr.is_alias_rvalue
            or arg_name_expr.is_inferred_def
            or arg_name_expr.is_new_def
            or arg_name_expr.is_special_form
        )
        assert isinstance(arg_name_expr.node, mypy.nodes.Var)
        if isinstance(arg_name_expr.node.type, mypy.types.LiteralType):
            inst_type = arg_name_expr.node.type.fallback
        else:
            assert isinstance(arg_name_expr.node.type, mypy.types.Instance)
            inst_type = arg_name_expr.node.type
        assert inst_type.type.fullname in (
            "builtins.str",
            "builtins.int",
            "builtins.bool",
            "builtins.bytes",
        )


def test_annotated_metadata() -> None:
    """Negative test - this would be a good way to add key overrides to global state storage,
    but unfortunately MyPy strips it entirely from the AST, even the unanalyzed_type"""

    def test() -> None:
        import typing
        import dataclasses

        @dataclasses.dataclass
        class StateKey:
            key: bytes

        counter: typing.Annotated[int, StateKey(b"c")] = 1

    result = mypy_parse_and_type_check(test)
    tree = result.graph[TEST_MODULE].tree
    assert tree
    ass = tree.defs[-1]
    assert isinstance(ass, mypy.nodes.AssignmentStmt)
    assert isinstance(ass.unanalyzed_type, mypy.types.UnboundType)
    assert len(ass.unanalyzed_type.args) == 2
    _, ann_arg = ass.unanalyzed_type.args
    assert isinstance(ann_arg, mypy.types.RawExpressionType) and ann_arg.literal_value is None


def test_dataclass_transform_frozen() -> None:
    def test() -> None:
        import typing

        @typing.dataclass_transform(
            eq_default=False, order_default=False, kw_only_default=False, field_specifiers=()
        )
        class _StructMeta(type):
            def __new__(
                cls,
                name: str,
                bases: tuple[type, ...],
                namespace: dict[str, object],
                *,
                kw_only: bool = False,
            ) -> "_StructMeta":
                raise NotImplementedError

        class StructBase(metaclass=_StructMeta):
            pass

        class Struct(StructBase):
            field: int

        class FrozenStruct(StructBase, frozen=True):
            field: int

        class UnfrozenStruct(StructBase, frozen=False):
            field: int

        f1 = Struct(1)
        f2 = FrozenStruct(1)
        f3 = UnfrozenStruct(1)
        f1.field = 1
        f2.field = 2
        f3.field = 3

    result = mypy_parse_and_type_check(test)
    assert strip_error_prefixes(result) == [
        'error: Property "field" defined in "FrozenStruct" is read-only  [misc]',
    ]
    tree = result.graph[TEST_MODULE].tree
    assert isinstance(tree, mypy.nodes.MypyFile)
    struct_cls_def = get_class_by_name(tree, "Struct")
    assert struct_cls_def.info.metadata["dataclass"]["frozen"] is False
    frozen_struct_cls_def = get_class_by_name(tree, "FrozenStruct")
    assert frozen_struct_cls_def.info.metadata["dataclass"]["frozen"] is True
    unfrozen_struct_cls_def = get_class_by_name(tree, "UnfrozenStruct")
    assert unfrozen_struct_cls_def.info.metadata["dataclass"]["frozen"] is False
