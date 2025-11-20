/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_CHATKIT_CONFIG_URL?: string;
  readonly VITE_CHATKIT_AUTH_TOKEN?: string;
  readonly VITE_CHATKIT_USER_ID?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
