# Building a front end for Puya

**Previous**: [Introduction](./00-introduction.md)


## Calling puya

Before getting into building out the front end, let's look at how we will be calling into the back end which informs us of the artifacts we will need to produce. 

### Installing puya

The Puya compiler is currently published to the Python Package Index under the name `puyapy`. This package includes the `puyapy` front end cli for compiling Algorand Python projects, and a `puya` executable for invoking just the back end. To install it you will require a working python 3.12 environment then the package can be installed with:

```shell
pipx install puyapy
```

Or to install a specific version

```shell
pipx install puyapy==4.4.2 --force
```

Once installed, you should verify that puya is available on your PATH.

```shell
> puya
usage: puya [-h] [--version]
            [--log-level {notset,debug,info,warning,error,critical}]
            [--log-format {default,json}] --options OPTIONS --awst AWST
            [--source-annotations SOURCE_ANNOTATIONS]
puya: error: the following arguments are required: --options, --awst
```

You should see an error message saying two required arguments are not present. 

### Puya Options

The first artifact required by the Puya compiler is a file containing the options to be used when producing compilation output. You can find the JSON schema for this file [here](./puya-options.json). The only required property is `compilationSet` which is what Puya uses to determine compilation targets. Whilst not strictly speaking required, if none of the `output*` properties are set to `true`, there will be no compilation output.  

> Puya will 'build' all contracts and logic signatures passed in the accompanying AWST file, but it will only generate output for items named in the `compilationSet`.

A minimal options file might look like this: 

```json
{
  "output_teal": true,
  "compilation_set": {
    "HelloWorldContract": "out"
  }
}
```

Puya will look for a contract with `"id": "HelloWorldContract"` and produce `*.teal` files in the `out` directory (relative to the current working directory). 

### AWST json

The second artifact required by the compiler is the AWST nodes themselves, serialized to JSON. This file will be deserialized by Python's cattrs library using a `_type` property to disambiguate nodes. As such, each node should be serialized with an additional `_type` property set to the node's name. eg.

```json
{
    "_type": "BoolConstant",
    "source_location": { },
    "wtype": { },
    "value": true
}
```

The root of this json file should be an array of `RootNode`. RootNode being the base type for all nodes which are allowed to appear without additional context, currently `Contract`, `LogicSignature`, and `Subroutine`. Since subroutines don't have compilation output on their own, the file should contain at least one contract or logic signature. 

A minimal awst file might look like this:

```json
[
  {
    "_type": "Contract",
    "source_location": { "file": "d:/example/hello-contract.ext", "line": 3, "end_line": 3, "column": 0, "end_column": 62 },
    "id": "HelloWorldContract",
    "name": "HelloWorldContract",
    "description": null,
    "method_resolution_order": [],
    "approval_program": {
      "_type": "ContractMethod",
      "source_location": { "file": "d:/example/hello-contract.ext", "line": 4, "end_line": 4, "column": 2, "end_column": 35 },
      "args": [],
      "return_type": { "_type": "WType", "name": "bool", "immutable": true, "ephemeral": false, "scalar_type": 2 },
      "body": {
        "_type": "Block",
        "source_location": { "file": "d:/example/hello-contract.ext", "line": 4, "end_line": 8, "column": 36, "end_column": 3 },
        "body": [
          {
            "_type": "ReturnStatement",
            "source_location": { "file": "d:/example/hello-contract.ext", "line": 7, "end_line": 7, "column": 4, "end_column": 15 },
            "value": {
              "_type": "BoolConstant",
              "source_location": { "file": "d:/example/hello-contract.ext", "line": 7, "end_line": 7, "column": 11, "end_column": 15 },
              "wtype": { "_type": "WType", "name": "bool", "immutable": true, "ephemeral": false, "scalar_type": 2 },
              "value": true
            }
          }
        ],
        "label": null,
        "comment": null
      },
      "documentation": { "_type": "MethodDocumentation", "description": null, "args": {}, "returns": null },
      "inline": null,
      "cref": "HelloWorldContract",
      "member_name": "approvalProgram",
      "arc4_method_config": null
    },
    "clear_program": {
      "_type": "ContractMethod",
      "source_location": { "file": "d:/example/hello-contract.ext", "line": 9, "end_line": 9, "column": 2, "end_column": 37 },
      "args": [],
      "return_type": { "_type": "WType", "name": "bool", "immutable": true, "ephemeral": false, "scalar_type": 2 },
      "body": {
        "_type": "Block",
        "source_location": { "file": "d:/example/hello-contract.ext", "line": 9, "end_line": 11, "column": 38, "end_column": 3 },
        "body": [
          {
            "_type": "ReturnStatement",
            "source_location": { "file": "d:/example/hello-contract.ext", "line": 10, "end_line": 10, "column": 4, "end_column": 15 },
            "value": {
              "_type": "BoolConstant",
              "source_location": { "file": "d:/example/hello-contract.ext", "line": 10, "end_line": 10, "column": 11, "end_column": 15 },
              "wtype": { "_type": "WType", "name": "bool", "immutable": true, "ephemeral": false, "scalar_type": 2 },
              "value": true
            }
          }
        ],
        "label": null,
        "comment": null
      },
      "documentation": { "_type": "MethodDocumentation", "description": null, "args": {}, "returns": null },
      "inline": null,
      "cref": "HelloWorldContract",
      "member_name": "clearStateProgram",
      "arc4_method_config": null
    },
    "methods": [],
    "app_state": [],
    "state_totals": null,
    "reserved_scratch_space": [],
    "avm_version": null
  }
]
```

Note that the cattrs deserializer expects `null` values to be provided for optional properties rather than just omitting them.

### Source annotations

This artifact is optional. If provided, source annotations should be a json file representing a dictionary of source file paths to the source file lines. The key should be the absolute path to the source file and should match exactly the string used in `source_location.file`. The value should be an array of source file lines. Each line should be the full text of the original source code including leading and trailing white space but excluding new line characters (CRLF/LF). The source annotations, if provided, will be used to annotate teal output in debug modes.

### Other options

`--version` can be used in isolation to have puya return its version information

`--log-level` determines the minimum log level which will be output. The default is `info`. Set this to `debug` to include additional debug information if you run into issues. Possible values are `debug`, `info`, `warning`, `error`, `critical`. 

`--log-format` determines how the logs are written to STDIO. The `default` option is to output logs in a human-readable format. Set this to `json` if you wish to digest Puya's log output in a machine-readable form.  

### Putting it all together

Assuming you have the above options and awst json files available as `options.json` and `awst.json` in the CWD, you can invoke puya with the command:

```shell
puya --options options.json --awst awst.json --log-level=info
```

> Puya currently requires out directories to be created by the front end, so the above command will fail if you don't have an `out` dir in your CWD.

This command should result in the console output 

```
> puya --options options.json --awst awst.json --log-level=info
info: Writing out/HelloWorldContract.approval.teal
info: Writing out/HelloWorldContract.clear.teal
```

The `out` directory will contain a `*.teal` file for both the approval and clear state programs.

Producing the above artifacts and invoking Puya is the end game of building a new front end. 

**Next up**: [Designing a langauge](./02-designing-a-language.md)
