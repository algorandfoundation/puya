// @ts-check
import starlight from "@astrojs/starlight";
import { defineConfig } from "astro/config";
import remarkGithubAlerts from "remark-github-alerts";
import sidebar from "./sidebar.config.json";

// https://astro.build/config
export default defineConfig({
    site: "https://algorandfoundation.github.io",
    base: "/puya/",
    trailingSlash: "always",
    markdown: {
        remarkPlugins: [remarkGithubAlerts],
    },
    integrations: [
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