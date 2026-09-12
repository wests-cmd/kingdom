/**
 * KINGDOM Desktop Launcher Foundation
 * Manages local Kingdom backend startup, readiness polling, and desktop webview/window launch.
 */

const { spawn } = require('child_process');
const http = require('http');
const path = require('path');

let BACKEND_PORT = process.env.PORT || 8000;
let READINESS_URL = `http://localhost:${BACKEND_PORT}/health/ready`;
const MAX_POLL_ATTEMPTS = 30;
const POLL_INTERVAL_MS = 1000;

let backendProcess = null;

function setPort(port) {
  BACKEND_PORT = port;
  READINESS_URL = `http://localhost:${BACKEND_PORT}/health/ready`;
}

function checkReadiness(url = READINESS_URL) {
  return new Promise((resolve) => {
    http.get(url, (res) => {
      if (res.statusCode === 200) {
        resolve(true);
      } else {
        resolve(false);
      }
    }).on('error', () => {
      resolve(false);
    });
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

function startBackend() {
  console.log('[Kingdom Desktop Launcher] Starting local Kingdom FastAPI server...');
  const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';

  backendProcess = spawn(pythonCmd, ['-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', String(BACKEND_PORT)], {
    cwd: path.resolve(__dirname, '..'),
    env: { ...process.env, PYTHONUNBUFFERED: '1' },
    stdio: 'inherit'
  });

  backendProcess.on('exit', (code, signal) => {
    console.log(`[Kingdom Desktop Launcher] Backend process exited with code ${code}, signal ${signal}`);
  });
}

function stopBackend() {
  if (backendProcess) {
    console.log('[Kingdom Desktop Launcher] Stopping Kingdom backend process...');
    backendProcess.kill('SIGTERM');
    backendProcess = null;
  }
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
