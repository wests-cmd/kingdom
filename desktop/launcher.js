/**
 * KINGDOM Desktop Launcher Foundation
 * Manages local Kingdom backend startup, readiness polling, and desktop webview/window launch.
 */

const { spawn, spawnSync } = require('child_process');
const http = require('http');
const path = require('path');
const fs = require('fs');

let BACKEND_PORT = process.env.PORT || 8000;
let READINESS_URL = `http://127.0.0.1:${BACKEND_PORT}/health/ready`;
const MAX_POLL_ATTEMPTS = 30;
const POLL_INTERVAL_MS = 1000;

let backendProcess = null;

function setPort(port) {
  BACKEND_PORT = port;
  READINESS_URL = `http://127.0.0.1:${BACKEND_PORT}/health/ready`;
}

function checkReadiness(url = READINESS_URL) {
  return new Promise((resolve) => {
    const request = http.get(url, (res) => {
      res.resume();
      if (res.statusCode === 200) {
        resolve(true);
      } else {
        resolve(false);
      }
    }).on('error', () => {
      resolve(false);
    });
    request.setTimeout(2000, () => { request.destroy(); resolve(false); });
  });
}

async function waitForBackendReady() {
  console.log(`[Kingdom Desktop Launcher] Waiting for backend readiness at ${READINESS_URL}...`);
  for (let attempt = 1; attempt <= MAX_POLL_ATTEMPTS; attempt++) {
    const ready = await checkReadiness();
    if (ready) {
      console.log(`[Kingdom Desktop Launcher] Kingdom Backend is READY!`);
      return true;
    }
    await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
  }
  console.error(`[Kingdom Desktop Launcher] Timed out waiting for Kingdom backend to become ready.`);
  return false;
}

function getBackendBinaryPath() {
  const binaryName = process.platform === 'win32' ? 'kingdom-backend.exe' : 'kingdom-backend';

  if (process.env.KINGDOM_BACKEND_BIN && fs.existsSync(process.env.KINGDOM_BACKEND_BIN)) {
    return process.env.KINGDOM_BACKEND_BIN;
  }

  if (process.resourcesPath) {
    const packagedBin = path.join(process.resourcesPath, 'bin', binaryName);
    if (fs.existsSync(packagedBin)) {
      return packagedBin;
    }
  }

  const localBin = path.join(__dirname, 'bin', binaryName);
  if (fs.existsSync(localBin)) {
    return localBin;
  }

  return null;
}

function startBackend(profilePath) {
  console.log('[Kingdom Desktop Launcher] Starting local Kingdom FastAPI server...');
  const bundledBin = getBackendBinaryPath();
  const isPackaged = Boolean(process.resourcesPath && !process.env.KINGDOM_DEV_MODE);

  const env = {
    ...process.env,
    PYTHONUNBUFFERED: '1'
  };

  const activeProfile = profilePath || process.env.KINGDOM_LOCAL_PROFILE;
  if (activeProfile) {
    env.KINGDOM_LOCAL_PROFILE = activeProfile;
  }

  if (bundledBin) {
    const runtimeDir = env.KINGDOM_DATA_DIR || (activeProfile
      ? path.join(path.dirname(activeProfile), 'runtime')
      : path.join(require('os').homedir(), '.kingdom'));
    fs.mkdirSync(runtimeDir, { recursive: true });
    env.KINGDOM_DATA_DIR = runtimeDir;
    console.log(`[Kingdom Desktop Launcher] Found standalone bundled backend binary: ${bundledBin}`);
    backendProcess = spawn(bundledBin, ['--host', '127.0.0.1', '--port', String(BACKEND_PORT)], {
      cwd: runtimeDir,
      env,
      windowsHide: true,
      stdio: 'inherit'
    });
  } else if (isPackaged) {
    console.error('[Kingdom Desktop Launcher] FATAL: Kingdom installation is incomplete. Bundled backend runtime binary was not found.');
    return;
  } else {
    console.log('[Kingdom Desktop Launcher] Standalone binary not found in development mode. Falling back to Python runtime mode...');
    const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';

    backendProcess = spawn(pythonCmd, ['-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', String(BACKEND_PORT)], {
      cwd: path.resolve(__dirname, '..'),
      env,
      stdio: 'inherit'
    });
  }

  if (backendProcess) {
    backendProcess.on('error', (error) => {
      console.error('[Kingdom Desktop Launcher] Failed to start backend:', error.message);
    });
    backendProcess.on('exit', (code, signal) => {
      console.log(`[Kingdom Desktop Launcher] Backend process exited with code ${code}, signal ${signal}`);
    });
  }
}

function stopBackend() {
  if (backendProcess) {
    const child = backendProcess;
    backendProcess = null;
    console.log('[Kingdom Desktop Launcher] Stopping Kingdom backend process...');
    if (process.platform === 'win32' && child.pid) {
      spawnSync('taskkill', ['/PID', String(child.pid), '/T', '/F'], {windowsHide: true});
    } else {
      child.kill('SIGTERM');
    }
    return new Promise((resolve) => {
      if (child.exitCode !== null) return resolve();
      const timer = setTimeout(() => { child.kill('SIGKILL'); resolve(); }, 5000);
      child.once('exit', () => { clearTimeout(timer); resolve(); });
    });
  }
  return Promise.resolve();
}

async function launchDesktop() {
  console.log('====================================================');
  console.log('       KINGDOM DESKTOP APPLICATION LAUNCHER         ');
  console.log('====================================================');

  const alreadyRunning = await checkReadiness();
  if (!alreadyRunning) {
    startBackend();
  } else {
    console.log('[Kingdom Desktop Launcher] Kingdom backend is already running locally.');
  }

  const isReady = await waitForBackendReady();

  if (isReady) {
    console.log('[Kingdom Desktop Launcher] Launching Command Center UI...');
  } else {
    console.error('[Kingdom Desktop Launcher] Failed to start Kingdom backend.');
    stopBackend();
    process.exit(1);
  }
}

if (require.main === module) {
  launchDesktop();

  process.on('SIGINT', () => {
    stopBackend();
    process.exit(0);
  });
  process.on('SIGTERM', () => {
    stopBackend();
    process.exit(0);
  });
}

module.exports = {
  startBackend,
  stopBackend,
  waitForBackendReady,
  checkReadiness
};
