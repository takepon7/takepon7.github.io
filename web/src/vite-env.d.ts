/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_GITAI_API_BASE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

interface Window {
  GITAI_API_BASE?: string;
}
