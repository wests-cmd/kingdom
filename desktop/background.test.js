const {test} = require('node:test');
const assert = require('node:assert/strict');
const {EventEmitter} = require('node:events');
const {BackgroundLifecycle} = require('./background');

function harness(overrides = {}) {
  const calls = {quit: 0, stop: 0, show: 0, errors: 0};
  class Tray extends EventEmitter {
    setToolTip(value) { this.tooltip = value; }
    setContextMenu(value) { this.menu = value; }
    destroy() { this.destroyed = true; }
  }
  const lifecycle = new BackgroundLifecycle({
    app: {quit() { calls.quit++; }}, Tray, Menu: {buildFromTemplate: items => items},
    icon: 'icon.png', showWindow() { calls.show++; },
    async stopBackend() { calls.stop++; }, reportError() { calls.errors++; }, ...overrides
  });
  return {lifecycle, calls};
}
const closeEvent = () => ({prevented: false, preventDefault() { this.prevented = true; }});

test('closing the window keeps its backend running and tray can restore it', async () => {
  const {lifecycle, calls} = harness();
  assert.equal(lifecycle.start(), true);
  const window = new EventEmitter();
  let hidden = 0;
  window.hide = () => hidden++;
  lifecycle.attach(window);
  const event = closeEvent(); window.emit('close', event);
  assert.equal(event.prevented, true);
  assert.equal(hidden, 1);
  assert.equal(calls.stop, 0);
  assert.equal(calls.quit, 0);
  lifecycle.tray.menu[0].click();
  lifecycle.tray.emit('double-click');
  await Promise.resolve();
  assert.equal(calls.show, 2);
});

test('explicit Quit stops the owned server once before closing, allowing repeated quit events', async () => {
  let release;
  const {lifecycle, calls} = harness({stopBackend: () => { calls.stop++; return new Promise(resolve => { release = resolve; }); }});
  lifecycle.start();
  lifecycle.tray.menu.at(-1).click();
  assert.equal(calls.quit, 1);
  const first = closeEvent(), second = closeEvent();
  const stopping = lifecycle.beforeQuit(first);
  await lifecycle.beforeQuit(second);
  assert.equal(first.prevented, true);
  assert.equal(second.prevented, true);
  assert.equal(calls.stop, 1);
  const window = new EventEmitter(); window.hide = () => assert.fail('must close when quitting');
  lifecycle.attach(window);
  const closing = closeEvent(); window.emit('close', closing);
  assert.equal(closing.prevented, false);
  const tray = lifecycle.tray;
  release(); await stopping;
  assert.equal(tray.destroyed, true);
  assert.equal(lifecycle.tray, null);
  assert.equal(calls.quit, 2);
  const final = closeEvent(); await lifecycle.beforeQuit(final);
  assert.equal(final.prevented, false);
});

test('an unavailable tray does not leave an unreachable hidden window', () => {
  const {lifecycle, calls} = harness({Tray: class { constructor() { throw new Error('No tray'); } }});
  assert.equal(lifecycle.start(), false);
  const window = new EventEmitter(); window.hide = () => assert.fail('unreachable window');
  lifecycle.attach(window);
  const event = closeEvent(); window.emit('close', event);
  assert.equal(event.prevented, false);
  assert.equal(calls.errors, 1);
});

test('shutdown errors are reported and cannot trap the app in a quit loop', async () => {
  const {lifecycle, calls} = harness({stopBackend: async () => { throw new Error('shutdown failed'); }});
  lifecycle.start();
  await lifecycle.beforeQuit(closeEvent());
  assert.equal(calls.errors, 1);
  assert.equal(calls.quit, 1);
  assert.equal(lifecycle.stopped, true);
});
