import { defineConfig, loadEnv, type Plugin } from 'vite';
import react from '@vitejs/plugin-react';

const POLYFILLS_ENTRY = '/src/polyfills.ts';

const loadPolyfillsFirst = (): Plugin => ({
  name: 'load-polyfills-first',
  transformIndexHtml() {
    return [
      {
        tag: 'script',
        attrs: {
          type: 'module',
          src: POLYFILLS_ENTRY,
        },
        injectTo: 'head-prepend',
      },
    ];
  },
});

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');

  return {
    plugins: [loadPolyfillsFirst(), react()],
    server: {
      port: 5173,
      open: true,
      host: env.VITE_DEV_HOST ?? 'localhost',
      allowedHosts: ['.localhost', 'fs-chat.kernhigh.org'],
    }
  };
});
