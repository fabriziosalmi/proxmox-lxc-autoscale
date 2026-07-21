import { defineConfig } from 'vitepress'

export default defineConfig({
  title: 'LXC AutoScale',
  description: 'Automatic CPU and memory scaling for Proxmox LXC containers',
  base: '/proxmox-lxc-autoscale/',

  head: [
    // Everything this site loads is first-party. 'unsafe-inline' is required
    // because VitePress emits an inline appearance script and inline styles.
    // Applied to the built site only: `vitepress dev` serves HMR over a
    // websocket, which a strict connect-src would block as soon as the dev
    // server is not same-origin (--host, or a custom server.hmr.port).
    ...(process.env.NODE_ENV === 'production'
      ? [
          [
            'meta',
            {
              'http-equiv': 'Content-Security-Policy',
              content:
                "default-src 'self'; script-src 'self' 'unsafe-inline'; " +
                "style-src 'self' 'unsafe-inline'; img-src 'self' data:; " +
                "font-src 'self'; connect-src 'self'; base-uri 'self'; form-action 'self'",
            },
          ] as [string, Record<string, string>],
        ]
      : []),
    ['meta', { name: 'theme-color', content: '#e6832a' }],
    ['meta', { name: 'og:type', content: 'website' }],
    ['meta', { name: 'og:title', content: 'LXC AutoScale' }],
    ['meta', { name: 'og:description', content: 'Automatic CPU and memory scaling for Proxmox LXC containers' }],
  ],

  themeConfig: {
    logo: undefined,
    siteTitle: 'LXC AutoScale',

    nav: [
      { text: 'Guide', link: '/guide/getting-started' },
      { text: 'Configuration', link: '/guide/configuration' },
      { text: 'Reference', link: '/reference/tier-snippets' },
      {
        text: 'v2.0.0',
        items: [
          { text: 'Changelog', link: 'https://github.com/fabriziosalmi/proxmox-lxc-autoscale/releases' },
          { text: 'PyPI', link: 'https://github.com/fabriziosalmi/proxmox-lxc-autoscale' },
        ],
      },
    ],

    sidebar: [
      {
        text: 'Introduction',
        items: [
          { text: 'What is LXC AutoScale?', link: '/' },
          { text: 'Getting Started', link: '/guide/getting-started' },
        ],
      },
      {
        text: 'Guide',
        items: [
          { text: 'Configuration', link: '/guide/configuration' },
          { text: 'Tiers', link: '/guide/tiers' },
          { text: 'CPU Core Pinning', link: '/guide/cpu-pinning' },
          { text: 'Horizontal Scaling', link: '/guide/horizontal-scaling' },
          { text: 'Docker', link: '/guide/docker' },
          { text: 'Security', link: '/guide/security' },
          { text: 'Notifications', link: '/guide/notifications' },
        ],
      },
      {
        text: 'Operations',
        items: [
          { text: 'Service Management', link: '/guide/service-management' },
          { text: 'Logging & Monitoring', link: '/guide/logging' },
          { text: 'Troubleshooting', link: '/guide/troubleshooting' },
          { text: 'Uninstallation', link: '/guide/uninstallation' },
        ],
      },
      {
        text: 'Reference',
        items: [
          { text: 'Tier Snippets (40 apps)', link: '/reference/tier-snippets' },
          { text: 'FAQ', link: '/reference/faq' },
          { text: 'Default Settings', link: '/reference/defaults' },
        ],
      },
    ],

    socialLinks: [
      { icon: 'github', link: 'https://github.com/fabriziosalmi/proxmox-lxc-autoscale' },
    ],

    editLink: {
      pattern: 'https://github.com/fabriziosalmi/proxmox-lxc-autoscale/edit/main/docs/:path',
      text: 'Edit this page on GitHub',
    },

    footer: {
      message: 
        'Released under the MIT License. · <a href="https://fabriziosalmi.github.io/privacy">Privacy &amp; legal</a>',
      copyright: 'Copyright 2024-present Fabrizio Salmi',
    },

    search: {
      provider: 'local',
    },
  },
})
