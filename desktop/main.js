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

const smokeReport = process.env.GITHUB_ACTIONS === 'true' && process.env.KINGDOM_RELEASE_SMOKE_REPORT;
if (app && smokeReport) app.setPath('userData', path.join(path.dirname(smokeReport), 'user-data'));

const VALID_KNIGHTS = new Set(['planner', 'coder', 'researcher', 'memory', 'security']);

const CATALOG_PATH = app && app.isPackaged
  ? path.join(process.resourcesPath, 'configs', 'install_profiles.json')
  : path.join(__dirname, '..', 'configs', 'install_profiles.json');
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
  });

  const isReady = await waitForBackendReady();
  if (isReady) {
    await mainWindow.loadURL(`http://127.0.0.1:${process.env.PORT || 8000}`);
  } else {
    mainWindow.loadFile(path.join(__dirname, 'error.html'));
  }

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
  // A release runner uses a disposable profile and exercises the actual packaged app.
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

    if (smokeReport) {
      runReleaseSmoke(smokeReport).then(() => { stopBackend(); app.exit(0); }).catch((error) => {
        console.error(error);
        stopBackend();
        app.exit(1);
      });
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

async function runReleaseSmoke(reportPath) {
  const deadline = Date.now() + 90000;
  async function until(check, description) {
    while (Date.now() < deadline) {
      if (await check()) return;
      await new Promise((resolve) => setTimeout(resolve, 250));
    }
    throw new Error(`Release smoke timed out: ${description}`);
  }
  await until(() => setupWindow && !setupWindow.webContents.isLoading(), 'setup wizard');
  const report = await setupWindow.webContents.executeJavaScript(`(async () => {
    const hardware = await window.kingdomDesktop.getHardwareReport();
    const catalog = await window.kingdomDesktop.getInstallCatalog();
    if (!catalog || !catalog.profiles.developer) throw new Error('Missing bundled catalog');
    if (!hardware.cpu_cores) throw new Error('Hardware inspection failed');
    return {hardware, catalogLoaded: true, wizardLoaded: document.title};
  })()`);
  await setupWindow.webContents.executeJavaScript(`void window.kingdomDesktop.saveProfile({
    name: 'Developer', gui: true, knights: ['planner', 'coder', 'security']
  }).catch(console.error)`);
  await until(async () => mainWindow && !mainWindow.webContents.isLoading()
    && mainWindow.webContents.getURL().startsWith('http://127.0.0.1')
    && await mainWindow.webContents.executeJavaScript("Boolean(document.querySelector('#root')?.children.length)"), 'rendered dashboard');
  const apiVersion = await mainWindow.webContents.executeJavaScript("fetch('/api/system/version').then(r => r.json())");
  if (apiVersion.version !== '1.0.0') throw new Error('Packaged backend version mismatch');
  report.dashboardLoaded = true;
  report.profilePersisted = Boolean(loadSavedProfile());
  report.version = apiVersion.version;
  report.platform = process.platform;
  report.arch = process.arch;
  fs.mkdirSync(path.dirname(reportPath), {recursive: true});
  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));
  fs.writeFileSync(reportPath.replace(/\.json$/, '.png'), (await mainWindow.webContents.capturePage()).toPNG());
}

module.exports = {
  createWindow,
  createSetupWindow,
  validateProfile,
  loadInstallCatalog,
  loadSavedProfile
};
