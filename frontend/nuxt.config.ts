export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  modules: [
    '@unocss/nuxt',
    '@pinia/nuxt',
    '@vueuse/nuxt',
  ],
  css: ['~/assets/css/main.css'],
  devtools: { enabled: true },
  ssr: false,

  components: {
    dirs: [
      {
        path: '~/components',
        pathPrefix: false,
      },
    ],
  },

  vite: {
    server: {
      proxy: {
        '/api': {
          target: 'http://localhost:8000',
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ''),
        },
      },
    },
  },

  runtimeConfig: {
    public: {
      apiBaseUrl: process.env.NUXT_PUBLIC_API_BASE_URL || '/api',
    },
  },
});
