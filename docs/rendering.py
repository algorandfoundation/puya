"""Renderer for MyST, customised to handle re-exporting."""

# ruff: noqa: INP001
from __future__ import annotations

import typing

from autodoc2.render.myst_ import MystRenderer as BaseMystRenderer

if typing.TYPE_CHECKING:
    from autodoc2.utils import ItemData


class MystRenderer(BaseMystRenderer):
    @typing.override
    def render_package(self, item: ItemData) -> typing.Iterable[str]:
        """Create the content for a package."""
        if self.standalone and self.is_hidden(item):
            yield from ["---", "orphan: true", "---", ""]

        full_name = item["full_name"]

        yield f"# {{py:mod}}`{full_name}`"
        yield ""

        yield f"```{{py:module}} {full_name}"
        if self.no_index(item):
            yield ":noindex:"
        if self.is_module_deprecated(item):
            yield ":deprecated:"
        yield from ["```", ""]

        if self.show_docstring(item):
            yield f"```{{autodoc2-docstring}} {item['full_name']}"
            if parser_name := self.get_doc_parser(item["full_name"]):
                yield f":parser: {parser_name}"
            yield ":allowtitles:"
            yield "```"
            yield ""

        visible_subpackages = [i["full_name"] for i in self.get_children(item, {"package"})]
        if visible_subpackages:
            yield from [
                "## Subpackages",
                "",
                "```{toctree}",
                ":titlesonly:",
                ":maxdepth: 3",
                "",
            ]
            for name in visible_subpackages:
                yield name
            yield "```"
            yield ""

        visible_submodules = [i["full_name"] for i in self.get_children(item, {"module"})]
        if visible_submodules:
            yield from [
                "## Submodules",
                "",
                "```{toctree}",
                ":titlesonly:",
                ":maxdepth: 1",
                "",
            ]
            for name in visible_submodules:
                yield name
            yield "```"
            yield ""

        visible_children = [
            i["full_name"]
            for i in self.get_children(item)
            if i["type"] not in ("package", "module")
        ]
        if not visible_children:
            return

        yield f"## {item['type'].capitalize()} Contents"
        yield ""

        if self.show_module_summary(item):
            imports = dict(item.get("imports", []))
            for heading, types in [
                ("Classes", {"class"}),
                ("Functions", {"function"}),
                ("Data", {"data"}),
                ("External", {"external"}),
            ]:
                visible_items = list(self.get_children(item, types))

                if visible_items:
                    yield from [f"### {heading}", ""]
                    yield from self.generate_summary(
                        visible_items,
                        alias={
                            # use the alias defined in the import if available
                            i["full_name"]: (
                                imports.get(i["full_name"]) or i["full_name"].split(".")[-1]
                            )
                            for i in visible_items
                        },
                    )
                    yield ""

            yield from ["### API", ""]
            for name in visible_children:
                if name not in imports:  # exclude imported symbols
                    yield from self.render_item(name)
