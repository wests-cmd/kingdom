const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const fs = require('fs');
const { startBackend, stopBackend, waitForBackendReady } = require('./launcher');
const { getHardwareReport, suggestProfile } = require('./hardware');

let mainWindow = null;
let setupWindow = null;

const VALID_KNIGHTS = new Set(['planner', 'coder', 'researcher', 'memory', 'security']);
const CATALOG_PATH = path.join(__dirname, '..', 'configs', 'install_profiles.json');
const PROFILE_PATH = app ? path.join(app.getPath('userData'), 'local_profile.json') : path.join(__dirname, '..', 'configs', 'local_profile.json');

function validateProfile(profile) {
  if (!profile || typeof profile !== 'object' || typeof profile.gui !== 'boolean' || !Array.isArray(profile.knights)) {
    return null;
  }
  const knights = [...new Set(profile.knights.filter((name) => VALID_KNIGHTS.has(name)))];
  if (!knights.length) return null;
  return {
    name: typeof profile.name === 'string' && profile.name.trim() ? profile.name.trim() : 'Custom',
    gui: profile.gui,
    knights
  };
}

function loadInstallCatalog() {
  try {
    return fs.existsSync(CATALOG_PATH) ? JSON.parse(fs.readFileSync(CATALOG_PATH, 'utf8')) : null;
  } catch (error) {
    console.error('[Kingdom Desktop] Failed to load install profile catalog:', error);
    return null;
  }
}

function loadSavedProfile() {
  try {
    return fs.existsSync(PROFILE_PATH)
      ? validateProfile(JSON.parse(fs.readFileSync(PROFILE_PATH, 'utf8')))
      : null;
  } catch (error) {
    console.error('[Kingdom Desktop] Invalid or corrupt saved profile:', error);
    return null;
  }
}

function getGpuStatus() {
  try {
    return typeof app.getGPUFeatureStatus === 'function' ? app.getGPUFeatureStatus() : null;
  } catch (_) {
    return null;
  }
}

function setupIpcHandlers() {
  ipcMain.handle('setup:getHardwareReport', async () => {
    const report = getHardwareReport(getGpuStatus());
    return { ...report, suggested_profile: suggestProfile(report) };
  });

  ipcMain.handle('setup:getInstallCatalog', async () => loadInstallCatalog());

  ipcMain.handle('setup:saveProfile', async (_event, profile) => {
    const validated = validateProfile(profile);
    if (!validated) throw new Error('Invalid Kingdom setup profile');

    fs.mkdirSync(path.dirname(PROFILE_PATH), { recursive: true });
    fs.writeFileSync(PROFILE_PATH, JSON.stringify(validated, null, 2), { encoding: 'utf8', mode: 0o600 });
    process.env.KINGDOM_LOCAL_PROFILE = PROFILE_PATH;

    if (setupWindow) {
      const currentSetupWin = setupWindow;
      setupWindow = null;
      startBackend(PROFILE_PATH);
      if (validated.gui) {
        await createWindow();
      } else {
        app.quit();
      }
      currentSetupWin.close();
    }
    return { saved: true };
  });
}

async function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280, height: 800, title: 'Kingdom — Distributed AI Runtime',
    backgroundColor: '#0d0d0d',
    webPreferences: { preload: path.join(__dirname, 'preload.js'), nodeIntegration: false, contextIsolation: true }
  });

  const isReady = await waitForBackendReady();
  if (isReady) {
    const staticIndex = path.join(__dirname, '..', 'frontend', 'dist', 'index.html');
    if (fs.existsSync(staticIndex)) mainWindow.loadFile(staticIndex);
    else mainWindow.loadURL('http://localhost:8000');
  } else {
    mainWindow.loadFile(path.join(__dirname, 'error.html'));
  }
  mainWindow.on('closed', () => { mainWindow = null; });
}

function createSetupWindow() {
  setupWindow = new BrowserWindow({
    width: 900, height: 680, resizable: false, title: 'Set Up Kingdom',
    backgroundColor: '#0d0d0d',
    webPreferences: { preload: path.join(__dirname, 'preload.js'), nodeIntegration: false, contextIsolation: true }
  });
  setupWindow.loadFile(path.join(__dirname, 'setup-wizard.html'));
  setupWindow.on('closed', () => { setupWindow = null; });
}

if (app) {
  app.whenReady().then(() => {
    setupIpcHandlers();
    const savedProfile = loadSavedProfile();
    if (savedProfile) {
      process.env.KINGDOM_LOCAL_PROFILE = PROFILE_PATH;
      startBackend(PROFILE_PATH);
      if (savedProfile.gui) createWindow();
    } else {
      createSetupWindow();
    }

    app.on('activate', () => {
      if (BrowserWindow.getAllWindows().length === 0 && !setupWindow) {
        const activeProfile = loadSavedProfile();
        if (activeProfile?.gui) createWindow();
        else if (!activeProfile) createSetupWindow();
      }
    });
  });

  app.on('window-all-closed', () => {
    stopBackend();
    if (process.platform !== 'darwin') app.quit();
  });
}

module.exports = { createWindow, createSetupWindow, validateProfile, loadInstallCatalog, loadSavedProfile, getGpuStatus };