LOAD_OP_CODES = frozenset(
    [
        "addr",
        "arg",
        *(f"arg_{i}" for i in range(4)),
        "byte",
        *(f"bytec_{i}" for i in range(4)),  # valid as long as we don't push through a bytecblock
        "gaid",
        "gload",
        # global OpcodeBudget could be affected by shuffling,
        # but we don't guarantee ordering of stack manipulations
        "global",
        "gtxn",
        "gtxna",
        "int",
        *(f"intc_{i}" for i in range(4)),  # valid as long as we don't push through an intcblock
        "load",  # valid as long as we don't push through a store/stores
        "method",
        "pushbytes",
        "pushint",
        "txn",
        "txna",
        # below are valid as long as we don't push through an itxn_submit
        "gitxn",
        "gitxna",
        "itxn",
        "itxna",
    ]
)
LOAD_OP_CODES_INCL_OFFSET = frozenset(
    [
        *LOAD_OP_CODES,
        "dig",
        "frame_dig",
    ]
)
STORE_OPS_INCL_OFFSET = frozenset(
    [
        "app_global_del",
        # "bury", TODO: this one is very hard, and doesn't show up in any of our examples
        # "assert", TODO: enable this but only for O2 or higher
        "frame_bury",
        "itxn_field",
        "pop",
        "store",
    ]
)

COMMUTATIVE_OPS = frozenset(
    [
        "+",
        "*",
        "&",
        "&&",
        "|",
        "||",
        "^",
        "==",
        "!=",
        "b*",
        "b+",
        "b&",
        "b|",
        "b^",
        "b==",
        "b!=",
        "addw",
        "mulw",
    ]
)

ORDERING_OPS = frozenset(["<", "<=", ">", ">=", "b<", "b<=", "b>", "b>="])
