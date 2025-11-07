# Language Servers

Algorand Python can be integrated with IDE’s that support the Language Server Protocol (LSP).

## VSCode

Use the official [Algorand Python](https://marketplace.visualstudio.com/items?itemName=AlgorandFoundation.algorand-python-vscode) extension and AlgoKit Python template to get started

## PyCharm and JetBrains IDE’s

Ensure the active interpreter for your project has PuyaPy 5.4.0 or later available

To configure the Algorand Python language server

1. Download and extract this [template](./lsp4ij-template.zip)
2. Install the [LSP4IJ](https://plugins.jetbrains.com/plugin/23257-lsp4ij) plugin
3. Navigate to `Settings | Languages & Frameworks | Language Servers`
4. Click the + Add Language Server button
5. Click Import Template…
6. Select the folder containing the template
7. Click OK

You may also need to start the language server, do this by navigating to the Language Server tab
in the tool sidebar, right click the PuyaPy entry and click restart

## Other

The language server can be integrated with other IDE’s that support LSP by starting
the language server via `puyapy-ls` or `python -m puyapy.lsp` and will communicate
over stdio by default.
