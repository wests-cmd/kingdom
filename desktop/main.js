/**
 * KINGDOM Native Desktop Application Entrypoint (Electron / App Shell)
 * Manages native window creation, guided first-run setup, local FastAPI backend process lifecycle, and IPC bridge.
 */

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
  if (!profile || typeof profile !== 'object') {
    return null;
  }

  if (typeof profile.gui !== 'boolean') {
    return null;
  }

  if (!Array.isArray(profile.knights)) {
    return null;
  }

  const knights = [...new Set(profile.knights.filter((name) => VALID_KNIGHTS.has(name)))];

  if (knights.length === 0) {
    return null;
  }

  return {
    name: typeof profile.name === 'string' ? profile.name : 'Custom',
    gui: profile.gui,
    knights
  };
}

function loadInstallCatalog() {
  try {
    if (!fs.existsSync(CATALOG_PATH)) {
      return null;
    }
    const raw = fs.readFileSync(CATALOG_PATH, 'utf8');
    return JSON.parse(raw);
  } catch (error) {
    console.error('[Kingdom Desktop] Failed to load install profile catalog:', error);
    return null;
  }
}

function loadSavedProfile() {
  try {
    if (!fs.existsSync(PROFILE_PATH)) {
      return null;
    }

    const raw = JSON.parse(fs.readFileSync(PROFILE_PATH, 'utf8'));
    return validateProfile(raw);
  } catch (error) {
    console.error('[Kingdom Desktop] Invalid or corrupt saved profile:', error);
    return null;
  }
}

function setupIpcHandlers() {
  ipcMain.handle('setup:getHardwareReport', async () => {
    const report = getHardwareReport();
    return {
      ...report,
      suggested_profile: suggestProfile(report)
    };
  });

  ipcMain.handle('setup:getInstallCatalog', async () => {
    return loadInstallCatalog();
  });

  ipcMain.handle('setup:saveProfile', async (_event, profile) => {
    const validated = validateProfile(profile);

    if (!validated) {
      throw new Error('Invalid Kingdom setup profile');
    }

    fs.mkdirSync(path.dirname(PROFILE_PATH), { recursive: true });

    fs.writeFileSync(PROFILE_PATH, JSON.stringify(validated, null, 2), {
      encoding: 'utf8',
      mode: 0o600
    });

    process.env.KINGDOM_LOCAL_PROFILE = PROFILE_PATH;

    if (setupWindow) {
      const currentSetupWin = setupWindow;
      setupWindow = null;
      startBackend(PROFILE_PATH);

      if (validated.gui) {
        await createWindow();
      }

      currentSetupWin.close();
    }

    return { saved: true };
  });
}

async function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    title: 'Kingdom — Distributed AI Runtime',
    backgroundColor: '#0d0d0d',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true
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

function createSetupWindow() {
  setupWindow = new BrowserWindow({
    width: 900,
    height: 680,
    resizable: false,
    title: 'Set Up Kingdom',
    backgroundColor: '#0d0d0d',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true
    }
  });

  setupWindow.loadFile(path.join(__dirname, 'setup-wizard.html'));

  setupWindow.on('closed', () => {
    setupWindow = null;
  });
}

if (app) {
  app.whenReady().then(() => {
    setupIpcHandlers();

    const savedProfile = loadSavedProfile();

    if (savedProfile) {
      process.env.KINGDOM_LOCAL_PROFILE = PROFILE_PATH;
      startBackend(PROFILE_PATH);

      if (savedProfile.gui) {
        createWindow();
      } else {
        console.log('[Kingdom Desktop] Running in headless mode (GUI disabled in profile).');
      }
    } else {
      console.log('[Kingdom Desktop] No valid saved profile found. Launching guided first-run setup wizard...');
      createSetupWindow();
    }

    app.on('activate', () => {
      if (BrowserWindow.getAllWindows().length === 0 && !setupWindow) {
        const activeProfile = loadSavedProfile();
        if (activeProfile && !activeProfile.gui) {
          return;
        }
        if (activeProfile) {
          createWindow();
        } else {
          createSetupWindow();
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
  createWindow,
  createSetupWindow,
  validateProfile,
  loadInstallCatalog,
  loadSavedProfile
};
