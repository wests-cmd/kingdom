/** Compact native window; no microphone or privileged IPC is enabled by opening it. */
const ACCELERATOR = 'CommandOrControl+Shift+Space';

class QuickAssistant {
  constructor({BrowserWindow, globalShortcut, allowed, ready, origin, reportError = console.error}) {
    Object.assign(this, {BrowserWindow, globalShortcut, allowed, ready, origin, reportError});
    this.window = null;
    this.opening = false;
    this.registered = false;
    this.stopped = false;
  }

  register() {
    if (this.stopped || !this.allowed()) return false;
    if (this.registered) return true;
    try {
      this.registered = this.globalShortcut.register(ACCELERATOR, () => {
        void this.open().catch(error => this.reportError('Quick Kingdom unavailable', error));
      }) === true;
    } catch (error) {
      this.reportError('Quick Kingdom shortcut unavailable', error);
    }
    return this.registered;
  }

  async open() {
    if (this.stopped || !this.allowed() || this.opening) return false;
    if (this.window && !this.window.isDestroyed()) {
      if (this.window.isMinimized()) this.window.restore();
      this.window.show();
      this.window.focus();
      return true;
    }
    this.opening = true;
    let window;
    try {
      if (!await this.ready() || this.stopped || !this.allowed()) return false;
      const url = this.origin() + '/#/quick';
      window = new this.BrowserWindow({
        width: 520, height: 620, minWidth: 360, minHeight: 400,
        title: 'Quick Kingdom', show: false, alwaysOnTop: true,
        autoHideMenuBar: true, backgroundColor: '#100e15',
        webPreferences: {sandbox: true, nodeIntegration: false, contextIsolation: true}
      });
      this.window = window;
      window.webContents.setWindowOpenHandler(() => ({action: 'deny'}));
      window.webContents.on('will-navigate', (event, target) => {
        if (target !== url) event.preventDefault();
      });
      window.webContents.on('will-redirect', (event, target) => {
        if (target !== url) event.preventDefault();
      });
      window.on('closed', () => { if (this.window === window) this.window = null; });
      await window.loadURL(url);
      if (this.stopped || window.isDestroyed() || !this.allowed()) {
        if (!window.isDestroyed()) window.destroy();
        return false;
      }
      window.show();
      window.focus();
      return true;
    } catch (error) {
      if (window && !window.isDestroyed()) window.destroy();
      throw error;
    } finally {
      this.opening = false;
    }
  }

  stop() {
    this.stopped = true;
    if (this.registered) this.globalShortcut.unregister(ACCELERATOR);
    this.registered = false;
    if (this.window && !this.window.isDestroyed()) this.window.destroy();
  }
}

module.exports = {QuickAssistant, ACCELERATOR};
