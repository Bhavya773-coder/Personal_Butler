import { app, BrowserWindow, globalShortcut, ipcMain } from 'electron'
import path from 'path'

let mainWindow: BrowserWindow | null = null

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    title: 'JARVIS Core',
    backgroundColor: '#0a0a0f',
    // icon: path.join(__dirname, '../public/icon.png'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
    autoHideMenuBar: true,
    frame: true,
    show: false,
  })

  // Load Vite dev server or production build
  if (process.env.VITE_DEV_SERVER_URL) {
    mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL)
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'))
  }

  // Show window when ready to avoid white flash
  mainWindow.once('ready-to-show', () => {
    mainWindow?.show()
  })

  // Register global shortcut: Ctrl+Space for interrupt
  globalShortcut.register('Control+Space', () => {
    mainWindow?.webContents.send('jarvis:interrupt')
  })

  mainWindow.on('closed', () => {
    mainWindow = null
  })
}

app.whenReady().then(createWindow)

app.on('window-all-closed', () => {
  globalShortcut.unregisterAll()
  app.quit()
})

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow()
  }
})

// IPC Handlers
ipcMain.handle('jarvis:getVersion', () => {
  return app.getVersion()
})
