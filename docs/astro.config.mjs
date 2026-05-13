// @ts-check
import starlight from "@astrojs/starlight";
import { defineConfig } from "astro/config";
import remarkGithubAlerts from "remark-github-alerts";
import sidebar from "./sidebar.config.json";

// Swap fenced ```mermaid blocks for a <pre class="mermaid"> HTML node before
// ExpressiveCode (which runs as a rehype plugin) wraps them as code. The
// matching client-side mermaid.run() call is injected by mermaidClient below.
function remarkMermaid() {
    return (tree) => {
        const stack = [tree];
        while (stack.length) {
            const node = stack.pop();
            if (!node || !node.children) continue;
            for (let i = 0; i < node.children.length; i++) {
                const child = node.children[i];
                if (child.type === "code" && child.lang === "mermaid") {
                    node.children[i] = {
                        type: "html",
                        value: `<pre class="mermaid">${child.value
                            .replace(/&/g, "&amp;")
                            .replace(/</g, "&lt;")
                            .replace(/>/g, "&gt;")}</pre>`,
                    };
                } else {
                    stack.push(child);
                }
            }
        }
    };
}

// https://astro.build/config
export default defineConfig({
    site: "https://algorandfoundation.github.io",
    base: "/puya/",
    trailingSlash: "always",
    markdown: {
        remarkPlugins: [remarkGithubAlerts, remarkMermaid],
    },
    integrations: [
        {
            name: "mermaid-client",
            hooks: {
                "astro:config:setup": ({ injectScript }) => {
                    injectScript(
                        "page",
                        `
import mermaid from "mermaid";

const themeFor = () =>
    document.documentElement.dataset.theme === "dark" ? "dark" : "default";

const render = async () => {
    document.querySelectorAll("pre.mermaid:not([data-source])").forEach((el) => {
        el.dataset.source = el.textContent;
    });
    mermaid.initialize({ startOnLoad: false, theme: themeFor() });
    const nodes = document.querySelectorAll("pre.mermaid:not([data-processed])");
    if (nodes.length) await mermaid.run({ nodes });
};

render();

new MutationObserver(() => {
    document.querySelectorAll("pre.mermaid[data-source]").forEach((el) => {
        el.removeAttribute("data-processed");
        el.innerHTML = el.dataset.source;
    });
    render();
}).observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["data-theme"],
});
`,
                    );
                },
            },
        },
        starlight({
            title: "Algorand Python",
            tableOfContents: { minHeadingLevel: 2, maxHeadingLevel: 4 },
            customCss: [
                "./src/styles/api-reference.css",
                "remark-github-alerts/styles/github-colors-light.css",
                "remark-github-alerts/styles/github-colors-dark-media.css",
                "remark-github-alerts/styles/github-base.css",
            ],
            social: [
                {
                    icon: "github",
                    label: "GitHub",
                    href: "https://github.com/algorandfoundation/puya",
                },
                {
                    icon: "discord",
                    label: "Discord",
                    href: "https://discord.gg/algorand",
                },
            ],
            sidebar,
        }),
    ],
});