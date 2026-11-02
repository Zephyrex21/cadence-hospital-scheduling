/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Public URL of the API host, used to wake it directly (empty string disables). */
  readonly VITE_BACKEND_URL?: string
}
