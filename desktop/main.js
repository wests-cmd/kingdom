/**
 * KINGDOM Native Desktop Application Entrypoint (Electron / App Shell)
 * Manages native window creation, local FastAPI backend process lifecycle, and IPC bridge.
 */

const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const fs = require('fs');
const http = require('http');
const { startBackend, stopBackend, waitForBackendReady } = require('./launcher');
const { getHardwareReport, suggestProfile } = require('./hardware');

let mainWindow = null;

const CATALOG_PATH = path.resolve(__dirname, '..', 'configs', 'install_profiles.json');

function getProfilePath() {
  if (app && app.isPackaged) {
    return path.join(app.getPath('userData'), 'local_profile.json');
  }
  return path.resolve(__dirname, '..', 'configs', 'local_profile.json');
}

const PROFILE_PATH = getProfilePath();

const VALID_KNIGHT_ROLES = ['planner', 'coder', 'researcher', 'memory', 'security'];

function validateProfile(profile) {
  if (!profile || typeof profile !== 'object') {
    return null;
  }

  const gui = profile.gui !== false; // default true
  let knights = Array.isArray(profile.knights) ? profile.knights : [];

  const seen = new Set();
  const validKnights = [];
  for (const k of knights) {
    if (typeof k === 'string' && VALID_KNIGHT_ROLES.includes(k) && !seen.has(k)) {
      seen.add(k);
      validKnights.push(k);
    }
  }

  return {
    name: typeof profile.name === 'string' ? profile.name : 'Custom Profile',
    gui: gui,
    knights: validKnights.length > 0 ? validKnights : VALID_KNIGHT_ROLES.slice()
  };
}

function loadCatalog() {
  try {
    if (fs.existsSync(CATALOG_PATH)) {
      return JSON.parse(fs.readFileSync(CATALOG_PATH, 'utf-8'));
    }
  } catch (error) {
    console.error('[Kingdom Desktop] Failed to load install catalog:', error);
  }
  return null;
}

function loadSavedProfile() {
  if (!fs.existsSync(PROFILE_PATH)) {
    return null;
  }

  try {
    const profile = JSON.parse(fs.readFileSync(PROFILE_PATH, 'utf-8'));
    return validateProfile(profile);
  } catch (error) {
    console.error('[Kingdom Desktop] Invalid local profile; using first-run setup:', error);
    return null;
  }
}

async function launchBackendAndUI(profile) {
  process.env.KINGDOM_LOCAL_PROFILE = PROFILE_PATH;

  startBackend();

  if (profile && profile.gui === false) {
    console.log('[Kingdom Desktop] Headless profile active. Backend running without GUI window.');
    return;
  }

  if (!mainWindow) {
    mainWindow = new BrowserWindow({
      width: 1280,
      height: 800,
      title: "Kingdom v1.0.0 — Distributed AI Runtime",
      backgroundColor: "#0d0d0d",
      webPreferences: {
        preload: path.join(__dirname, 'preload.js'),
        nodeIntegration: false,
        contextIsolation: true
      }
    });

    mainWindow.on('closed', () => {
      mainWindow = null;
    });
  }

  const isReady = await waitForBackendReady();
  if (isReady) {
    const staticIndex = path.join(__dirname, '..', 'frontend', 'dist', 'index.html');
    if (fs.existsSync(staticIndex)) {
      mainWindow.loadFile(staticIndex);
    } else {
      mainWindow.loadURL('http://localhost:8000');
    }
  } else {
    mainWindow.loadFile(path.join(__dirname, 'error.html'));
  }
}

function openSetupWizard() {
  mainWindow = new BrowserWindow({
    width: 900,
    height: 700,
    title: "Kingdom v1.0.0 — First-Run Guided Setup",
    backgroundColor: "#0d0d0d",
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true
    }
  });

  mainWindow.loadFile(path.join(__dirname, 'setup-wizard.html'));

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

function registerIpcHandlers() {
  ipcMain.handle('setup:getHardwareReport', () => {
    const report = getHardwareReport();
    return {
      ...report,
      suggested_profile: suggestProfile(report)
    };
  });

  ipcMain.handle('setup:getInstallCatalog', () => {
    return loadCatalog();
  });

  ipcMain.handle('setup:saveProfile', async (_event, profile) => {
    const validated = validateProfile(profile);
    if (!validated) {
      throw new Error('Invalid Kingdom setup profile');
    }

    fs.mkdirSync(path.dirname(PROFILE_PATH), { recursive: true });
    fs.writeFileSync(PROFILE_PATH, JSON.stringify(validated, null, 2), { encoding: 'utf-8', mode: 0o600 });

    if (mainWindow) {
      mainWindow.close();
      mainWindow = null;
    }

    await launchBackendAndUI(validated);

    return { saved: true, profile: validated };
  });

  ipcMain.handle('updater:check', async () => {
    return new Promise((resolve) => {
      http.get(`http://localhost:${process.env.PORT || 8000}/api/system/version`, (res) => {
        let data = '';
        res.on('data', chunk => data += chunk);
        res.on('end', () => {
          try {
            const versionInfo = JSON.parse(data);
            resolve({
              current_version: versionInfo.version || '1.0.0',
              update_available: false,
              status: 'up_to_date'
            });
          } catch (e) {
            resolve({ current_version: '1.0.0', update_available: false, status: 'check_failed' });
          }
        });
      }).on('error', () => {
        resolve({ current_version: '1.0.0', update_available: false, status: 'offline' });
      });
    });
  });

  ipcMain.handle('runtime:restart', async () => {
    stopBackend();
    const saved = loadSavedProfile();
    await launchBackendAndUI(saved);
    return { status: 'restarted' };
  });

  ipcMain.handle('runtime:stop', () => {
    stopBackend();
    return { status: 'stopped' };
  });
}

if (app) {
  app.whenReady().then(() => {
    registerIpcHandlers();

    const savedProfile = loadSavedProfile();
    if (savedProfile) {
      launchBackendAndUI(savedProfile);
    } else {
      openSetupWizard();
    }

    app.on('activate', () => {
      if (BrowserWindow.getAllWindows().length === 0) {
        const profile = loadSavedProfile();
        if (profile) {
          launchBackendAndUI(profile);
        } else {
          openSetupWizard();
        }
      }
    });
  });

  app.on('window-all-closed', () => {
    stopBackend();
    if (process.platform !== 'darwin') app.quit();
  });
}

module.exports = {
  createWindow: () => launchBackendAndUI(loadSavedProfile()),
  validateProfile,
  loadSavedProfile,
  getProfilePath
};
