import { defineConfig } from 'vitepress'

export default defineConfig({
  title: 'LXC AutoScale',
  description: 'Automatic CPU and memory scaling for Proxmox LXC containers',
  base: '/proxmox-lxc-autoscale/',

  head: [
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
        text: 'v1.2.0',
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
      message: 'Released under the MIT License.',
      copyright: 'Copyright 2024-present Fabrizio Salmi',
    },

    search: {
      provider: 'local',
    },
  },
})
