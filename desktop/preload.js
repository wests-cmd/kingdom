/**
 * KINGDOM Desktop Secure Preload Bridge
 * Exposes safe desktop process management IPC functions to the renderer without exposing Node.js primitives.
 */

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('kingdomDesktop', {
  restartRuntime: () => ipcRenderer.invoke('runtime:restart'),
  stopRuntime: () => ipcRenderer.invoke('runtime:stop'),
  getDoctorReport: () => ipcRenderer.invoke('doctor:getReport')
});
