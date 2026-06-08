import { contextBridge, ipcRenderer } from 'electron'

// Expose safe APIs to renderer via contextBridge
contextBridge.exposeInMainWorld('jarvis', {
  // Get app version
  getVersion: () => ipcRenderer.invoke('jarvis:getVersion'),

  // Listen for interrupt shortcut from main process
  onInterrupt: (callback: () => void) => {
    ipcRenderer.on('jarvis:interrupt', () => callback())
    return () => {
      ipcRenderer.removeAllListeners('jarvis:interrupt')
    }
  },
})

// Type declaration for the exposed API
export interface JarvisAPI {
  getVersion: () => Promise<string>
  onInterrupt: (callback: () => void) => () => void
}

declare global {
  interface Window {
    jarvis?: JarvisAPI
  }
}
