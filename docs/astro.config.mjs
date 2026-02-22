// @ts-check
import starlight from '@astrojs/starlight'
import { defineConfig } from 'astro/config'
import remarkGithubAlerts from 'remark-github-alerts'

// https://astro.build/config
export default defineConfig({
  site: 'https://algorandfoundation.github.io',
  base: '/puya/',
  markdown: {
    remarkPlugins: [remarkGithubAlerts],
  },
  integrations: [
    starlight({
      title: 'Algorand Python',
      social: [
        { icon: 'github', label: 'GitHub', href: 'https://github.com/algorandfoundation/puya' },
        { icon: 'discord', label: 'Discord', href: 'https://discord.gg/algorand' },
      ],
      sidebar: [
        {
          label: 'Language Guide',
          items: [
            { slug: 'language-guide' },
            { slug: 'language-guide/structure' },
            { slug: 'language-guide/types' },
            { slug: 'language-guide/control' },
            { slug: 'language-guide/modules' },
            { slug: 'language-guide/builtins' },
            { slug: 'language-guide/errors' },
            { slug: 'language-guide/data-structures' },
            { slug: 'language-guide/storage' },
            { slug: 'language-guide/logs' },
            { slug: 'language-guide/transactions' },
            { slug: 'language-guide/ops' },
            { slug: 'language-guide/opcode-budget' },
            { slug: 'language-guide/arc4' },
            { slug: 'language-guide/arc28' },
            { slug: 'language-guide/calling-apps' },
            { slug: 'language-guide/compile' },
            { slug: 'language-guide/unsupported-python-features' },
            { slug: 'language-guide/migration-4-5' },
          ],
        },
        { label: 'Compiler', slug: 'compiler' },
        {
          label: 'Reference',
          items: [
            { slug: 'reference/principles' },
            { slug: 'reference/algopy-testing' },
            { slug: 'reference/avm-debugger' },
            { slug: 'reference/language-servers' },
            {
              label: 'Architecture Decisions',
              collapsed: true,
              autogenerate: { directory: 'reference/architecture-decisions' },
            },
          ],
        },
        {
          label: 'Front-End Guide',
          collapsed: true,
          autogenerate: { directory: 'front-end-guide' },
        },
        {
          label: 'API Reference',
          collapsed: true,
          autogenerate: { directory: 'api' },
        },
      ],
    }),
  ],
})