/**
 * KINGDOM Native Desktop Application Entrypoint (Electron / App Shell)
 * Manages native window creation, guided first-run setup, local FastAPI backend process lifecycle, and IPC bridge.
 */

const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const fs = require('fs');
const { startBackend, stopBackend, waitForBackendReady, getOwnerToken } = require('./launcher');
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
  ipcMain.handle('auth:getSessionToken', (event) => {
    const origin = new URL(event.senderFrame.url).origin;
    if (origin !== `http://127.0.0.1:${process.env.PORT || 8000}`) throw new Error('Untrusted session requester');
    return getOwnerToken();
  });
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
    backgroundColor: '#100e15',
    icon: path.join(app.isPackaged ? process.resourcesPath : __dirname, 'branding', 'kingdom-icon.png'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true
    }
  });

  mainWindow.webContents.setWindowOpenHandler(() => ({action: "deny"}));
  mainWindow.webContents.on("will-navigate", (event, url) => {
    if (new URL(url).origin !== `http://127.0.0.1:${process.env.PORT || 8000}`) event.preventDefault();
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
    backgroundColor: '#100e15',
    icon: path.join(app.isPackaged ? process.resourcesPath : __dirname, 'branding', 'kingdom-icon.png'),
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
      runReleaseSmoke(smokeReport).then(async () => {
        if (mainWindow) mainWindow.destroy();
        await stopBackend();
        app.exit(0);
      }).catch(async (error) => {
        console.error(error);
        if (mainWindow) mainWindow.destroy();
        if (setupWindow) setupWindow.destroy();
        await stopBackend();
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
    if (smokeReport) return;
    const activeProfile = loadSavedProfile();
    if (activeProfile && !activeProfile.gui) return;
    if (process.platform !== 'darwin') app.quit();
  });
  let quitting = false;
  app.on('before-quit', (event) => {
    if (quitting) return;
    event.preventDefault();
    quitting = true;
    stopBackend().then(() => app.quit());
  });
}

async function runReleaseSmoke(reportPath) {
  const deadline = Date.now() + 90000;
  async function until(check, description) {
    while (Date.now() < deadline) {
      const result = await check();
      if (result) return result;
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
  if (apiVersion.version !== require('./package.json').version) throw new Error('Packaged backend version mismatch');
  await until(() => mainWindow.webContents.executeJavaScript("Boolean(document.querySelector('.badge-online')) && document.body.textContent.includes('Last synchronized at')"), 'realtime connection and dashboard data');
  await mainWindow.webContents.executeJavaScript("fetch('/start', {method: 'POST', headers: {'X-Kingdom-Request': '1'}}).then(r => {if (!r.ok) throw new Error('Runtime start failed'); return r.json()})");
  await until(() => mainWindow.webContents.executeJavaScript("fetch('/status').then(r => r.json()).then(s => s.running && s.scheduler_running)"), 'running scheduler');
  await until(() => mainWindow.webContents.executeJavaScript("Array.from(document.querySelectorAll('.card-value')).some(e => e.textContent === 'ACTIVE')"), 'live runtime dashboard');
  await mainWindow.webContents.executeJavaScript("Array.from(document.querySelectorAll('.sidebar-item')).find(e => e.textContent === 'Tasks').click()");
  await until(() => mainWindow.webContents.executeJavaScript("Boolean(document.querySelector('textarea[aria-label=\"Task description\"]'))"), 'task submission form');
  await mainWindow.webContents.executeJavaScript(`(() => {
    const input = document.querySelector('textarea[aria-label="Task description"]');
    Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set.call(input, 'native release verification');
    input.dispatchEvent(new Event('input', {bubbles:true}));
  })()`);
  await mainWindow.webContents.executeJavaScript("document.querySelector('main.content form').requestSubmit()");
  const verifiedTask = await until(() => mainWindow.webContents.executeJavaScript("fetch('/tasks').then(r => r.json()).then(tasks => tasks.find(t => t.prompt === 'native release verification' && t.status === 'completed'))"), 'real verified native task');
  if (verifiedTask.result.results[0].outcome.output.words !== 3 || verifiedTask.result.results[0].verification.state !== 'VERIFIED') throw new Error('Native task outcome verification failed');
  report.taskExecuted = {taskId: verifiedTask.id, words: 3, verification: 'VERIFIED'};
  report.missionWorkspace = await mainWindow.webContents.executeJavaScript(`(async () => {
    async function request(url, method='GET', body=null) {
      const response=await fetch(url,{method,headers:{'X-Kingdom-Request':'1','Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{})});
      if(!response.ok)throw new Error('Mission workspace request failed: '+url);return response.json();
    }
    const input=document.querySelector('textarea[aria-label="Task description"]');
    if(input.maxLength!==500000||input.rows<12||!document.querySelector('input[type="file"][multiple]'))throw new Error('Large task editor missing');
    const policy=await request('/runtime/policy');
    if(![1,2,3,4,5].every(level=>policy.levels.some(item=>item.level===level)))throw new Error('Five autonomy levels missing');
    const upload=await fetch('/workspace/attachments?filename=native-test.txt',{method:'POST',headers:{'X-Kingdom-Request':'1','Content-Type':'application/octet-stream'},body:'native attachment round trip'});
    if(!upload.ok)throw new Error('Native attachment upload failed');const attachment=await upload.json();
    const retrieved=await fetch('/workspace/attachments/'+attachment.id+'/download').then(r=>r.text());
    if(retrieved!=='native attachment round trip')throw new Error('Native attachment retrieval differs');
    const mission=await request('/missions','POST',{plan:{title:'Native mission',objective:'Measure text with verified evidence',deliverables:['Verified text measurements'],steps:[{id:'measure',title:'Measure source',kind:'text_check',instructions:'native mission evidence',acceptance:'Three words measured with independent verification'}]}});
    await request('/runtime/policy','PUT',{level:4});
    await request('/missions/'+mission.id+'/approve','POST',{version:mission.version});
    return {fiveLevels:true,largeEditor:true,attachmentRoundtrip:true,missionId:mission.id};
  })()`);
  await until(() => mainWindow.webContents.executeJavaScript("fetch('/missions').then(r=>r.json()).then(items=>items.some(item=>item.plan.title==='Native mission'&&item.status==='completed'))"), 'verified native mission');
  report.missionWorkspace.missionVerified = true;
  fs.mkdirSync(path.dirname(reportPath), {recursive:true});
  fs.writeFileSync(path.join(path.dirname(reportPath),'mission-workspace.png'),(await mainWindow.webContents.capturePage()).toPNG());
  await mainWindow.webContents.executeJavaScript("Array.from(document.querySelectorAll('.sidebar-item')).find(e=>e.textContent==='Governance').click()");
  await until(() => mainWindow.webContents.executeJavaScript("document.querySelectorAll('input[name=autonomy]').length===6 && document.body.textContent.includes('Computer control')"), 'five levels and computer grants in native UI');
  fs.writeFileSync(path.join(path.dirname(reportPath),'governance.png'),(await mainWindow.webContents.capturePage()).toPNG());
  await mainWindow.webContents.executeJavaScript("fetch('/runtime/policy',{method:'PUT',headers:{'X-Kingdom-Request':'1','Content-Type':'application/json'},body:JSON.stringify({level:3})}).then(r=>{if(!r.ok)throw new Error('Policy restore failed')})");
  report.portableMaps = await mainWindow.webContents.executeJavaScript(`(async () => {
    async function request(url, body) {
      const response = await fetch(url, body ? {method:'POST', headers:{'X-Kingdom-Request':'1','Content-Type':'application/json'}, body:JSON.stringify(body)} : {});
      if (!response.ok) throw new Error('Packaged map workflow failed');
      return response.json();
    }
    const profiles = await request('/profiles/preferences');
    if (!profiles.available.some(profile => profile.profile_id === 'developer')) throw new Error('Frozen profile catalog missing');
    const content = JSON.stringify({schema_version:'1.0',map_id:'native-smoke',capabilities:['product_research'],providers:[{provider_id:'openfoodfacts',capabilities:['product_research']}]});
    const preview = await request('/skillmaps/preview',{filename:'native-smoke.json',content});
    await request('/skillmaps/confirm',{preview_id:preview.preview_id,checksum:preview.checksum});
    const exported = await request('/skillmaps/native-smoke/export');
    const reimport = await request('/skillmaps/preview',{filename:exported.filename,content:exported.payload});
    if (preview.checksum !== exported.checksum || reimport.checksum !== exported.checksum) throw new Error('Native map roundtrip differs');
    return {catalogLoaded:true,roundtripEquivalent:true,checksum:exported.checksum};
  })()`);
  await mainWindow.webContents.executeJavaScript("Array.from(document.querySelectorAll('.sidebar-item')).find(e => e.textContent === 'Settings').click()");
  await until(() => mainWindow.webContents.executeJavaScript("Boolean(document.querySelector('#appearance-mode')) && document.querySelector('.brand-mark')?.naturalWidth === 512"), 'packaged appearance settings and logo');
  await mainWindow.webContents.executeJavaScript("(() => {const select=document.querySelector('#appearance-mode'); select.value='light'; select.dispatchEvent(new Event('change',{bubbles:true}));})()");
  await until(() => mainWindow.webContents.executeJavaScript("document.documentElement.dataset.theme === 'light'"), 'applied light mode');
  mainWindow.webContents.reload();
  await until(() => !mainWindow.webContents.isLoading() && mainWindow.webContents.executeJavaScript("document.documentElement.dataset.theme === 'light' && document.querySelector('.brand-mark')?.naturalWidth === 512"), 'persisted native appearance');
  await mainWindow.webContents.executeJavaScript("Array.from(document.querySelectorAll('.sidebar-item')).find(e => e.textContent === 'Settings').click()");
  await until(() => mainWindow.webContents.executeJavaScript("Boolean(document.querySelector('#accessibility-scale'))"), 'native accessibility controls');
  for (const [id, value] of [['accessibility-contrast','high'],['accessibility-scale','200']]) {
    await mainWindow.webContents.executeJavaScript(`(() => {const select=document.getElementById(${JSON.stringify(id)}); select.value=${JSON.stringify(value)}; select.dispatchEvent(new Event('change',{bubbles:true}));})()`);
  }
  await until(() => mainWindow.webContents.executeJavaScript("document.documentElement.dataset.contrast === 'high' && document.documentElement.dataset.largeDisplay === 'true' && document.documentElement.scrollWidth <= document.documentElement.clientWidth"), 'native high contrast and 200 percent layout');
  await until(() => mainWindow.webContents.executeJavaScript("fetch('/preferences/accessibility').then(r => {if(!r.ok) throw new Error('Owner preference read failed');return r.json()}).then(p => p.preferences?.scale === 200 && p.preferences?.contrast === 'high')"), 'durable native accessibility preferences');
  mainWindow.webContents.reload();
  await until(() => !mainWindow.webContents.isLoading() && mainWindow.webContents.executeJavaScript("document.documentElement.dataset.contrast === 'high' && document.documentElement.dataset.largeDisplay === 'true' && Boolean(document.querySelector('.badge-online'))"), 'accessibility after native reload');
  report.accessibility = {highContrastApplied:true,scale200Applied:true,noHorizontalOverflow:true,ownerPreferencesSaved:true,persistedAfterReload:true};
  await mainWindow.webContents.executeJavaScript("Array.from(document.querySelectorAll('.sidebar-item')).find(e => e.textContent === 'Settings').click()");
  await until(() => mainWindow.webContents.executeJavaScript("Boolean(document.querySelector('.appearance-settings'))"), 'appearance reset page');
  await mainWindow.webContents.executeJavaScript("Array.from(document.querySelectorAll('button')).find(e => e.textContent === 'Reset appearance').click()");
  await until(() => mainWindow.webContents.executeJavaScript("document.documentElement.dataset.theme === 'dark'"), 'restored royal appearance');
  report.appearance = {logoLoaded:true,lightModeApplied:true,persistedAfterReload:true,resetVerified:true};
  await mainWindow.webContents.executeJavaScript("Array.from(document.querySelectorAll('.sidebar-item')).find(e => e.textContent === 'Dashboard').click()");
  await until(() => mainWindow.webContents.executeJavaScript("Boolean(document.querySelector('.card-value')) && document.body.textContent.includes('Last synchronized at')"), 'dashboard before evidence capture');
  report.dashboardLoaded = true;
  report.profilePersisted = Boolean(loadSavedProfile());
  report.version = apiVersion.version;
  report.realtimeConnected = true;
  report.runtimeStarted = true;
  report.platform = process.platform;
  report.arch = process.arch;
  fs.mkdirSync(path.dirname(reportPath), {recursive: true});
  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));
  fs.writeFileSync(reportPath.replace(/\.json$/, '.png'), (await mainWindow.webContents.capturePage()).toPNG());
  await mainWindow.webContents.executeJavaScript("fetch('/stop', {method: 'POST', headers: {'X-Kingdom-Request': '1'}}).then(r => {if (!r.ok) throw new Error('Runtime stop failed'); return r.json()})");
  await until(() => mainWindow.webContents.executeJavaScript("fetch('/status').then(r => r.json()).then(s => !s.running && !s.scheduler_running)"), 'stopped scheduler');
  report.runtimeStopped = true;
  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));
}

module.exports = {
  createWindow,
  createSetupWindow,
  validateProfile,
  loadInstallCatalog,
  loadSavedProfile
};
