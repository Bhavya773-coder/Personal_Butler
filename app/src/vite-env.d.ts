/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

// Electron preload API exposed via contextBridge
interface JarvisAPI {
  getVersion: () => Promise<string>
  onInterrupt: (callback: () => void) => () => void
}

declare global {
  interface Window {
    jarvis?: JarvisAPI
  }
}

export {}

