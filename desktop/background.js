/** Window visibility is independent of the owned backend's lifetime. */
class BackgroundLifecycle {
  constructor({app, Tray, Menu, icon, showWindow, stopBackend, reportError = console.error}) {
    Object.assign(this, {app, Tray, Menu, icon, showWindow, stopBackend, reportError});
    this.tray = null;
    this.quitting = false;
    this.stopped = false;
  }

  start() {
    try {
      this.tray = new this.Tray(this.icon);
      this.tray.setToolTip('Kingdom — running in the background');
      this.tray.setContextMenu(this.Menu.buildFromTemplate([
        {label: 'Open Kingdom', click: () => this.open()},
        {label: 'Kingdom keeps working when its window is closed', enabled: false},
        {type: 'separator'},
        {label: 'Quit Kingdom and stop this computer’s server', click: () => this.app.quit()}
      ]));
      this.tray.on('double-click', () => this.open());
      return true;
    } catch (error) {
      if (this.tray) this.tray.destroy();
      this.tray = null;
      this.reportError('[Kingdom Desktop] Background icon unavailable; window close will quit.', error);
      return false;
    }
  }

  open() {
    Promise.resolve().then(() => this.showWindow()).catch(error =>
      this.reportError('[Kingdom Desktop] Could not reopen the window.', error));
  }

  attach(window) {
    window.on('close', event => {
      if (this.quitting || !this.tray) return;
      event.preventDefault();
      window.hide();
    });
  }

  async beforeQuit(event) {
    if (this.stopped) return;
    event.preventDefault();
    if (this.quitting) return;
    this.quitting = true;
    try {
      await this.stopBackend();
    } catch (error) {
      this.reportError('[Kingdom Desktop] Server shutdown failed.', error);
    } finally {
      this.stopped = true;
      if (this.tray) this.tray.destroy();
      this.tray = null;
      this.app.quit();
    }
  }
}

module.exports = {BackgroundLifecycle};
