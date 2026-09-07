/**
 * KINGDOM Native Desktop Application Entrypoint (Electron / App Shell)
 * Manages native window creation, local FastAPI backend process lifecycle, and IPC bridge.
 */

const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const { startBackend, stopBackend, waitForBackendReady } = require('./launcher');

let mainWindow = null;

async function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    title: "Kingdom v40.2.0 — Distributed AI Runtime",
    backgroundColor: "#0d0d0d",
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true
    }
  });

  const isReady = await waitForBackendReady();
  if (isReady) {
    mainWindow.loadURL('http://localhost:8000');
  } else {
    mainWindow.loadFile(path.join(__dirname, 'error.html'));
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

if (app) {
  app.whenReady().then(() => {
    startBackend();
    createWindow();

    app.on('activate', () => {
      if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
  });

  app.on('window-all-closed', () => {
    stopBackend();
    if (process.platform !== 'darwin') app.quit();
  });
}

module.exports = { createWindow };
