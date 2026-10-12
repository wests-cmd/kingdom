/**
 * KINGDOM Desktop Secure Preload Bridge
 * Exposes safe desktop process management and guided setup IPC functions to the renderer without exposing Node.js primitives.
 */

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('kingdomDesktop', {
  updates: {
    status: () => ipcRenderer.invoke('updates:status'),
    check: () => ipcRenderer.invoke('updates:check'),
    download: () => ipcRenderer.invoke('updates:download'),
    install: () => ipcRenderer.invoke('updates:install')
  },
  getSessionToken: () => ipcRenderer.invoke('auth:getSessionToken'),
  restartRuntime: () => ipcRenderer.invoke('runtime:restart'),
  stopRuntime: () => ipcRenderer.invoke('runtime:stop'),
  getDoctorReport: () => ipcRenderer.invoke('doctor:getReport'),
  getHardwareReport: () => ipcRenderer.invoke('setup:getHardwareReport'),
  getInstallCatalog: () => ipcRenderer.invoke('setup:getInstallCatalog'),
  saveProfile: (profile) => ipcRenderer.invoke('setup:saveProfile', profile)
});
