import test from 'node:test'
import assert from 'node:assert/strict'
import { hasDrafts, trackDrafts, refreshUIComponent, startPeriodicRefresh } from '../src/common/periodicRefresh.js'

const settle = async () => { for (let i = 0; i < 12; i++) await Promise.resolve() }
function fixture(overrides = {}) {
  let callback, delay, refreshes = 0, checks = 0, reloads = 0
  const notices = [], page = { hidden: false }, host = { navigator: { onLine: true } }
  const controller = startPeriodicRefresh({ page, host, interval: 100,
    clock: { setTimeout(fn, ms) { callback = fn; delay = ms; return 1 }, clearTimeout() { callback = null } },
    refresh: async () => { refreshes++ }, checkUpdate: async () => { checks++; return true },
    drafts: () => false, reload: () => reloads++, notify: (...args) => notices.push(args), ...overrides })
  return { controller, page, host, notices, count: () => ({ refreshes, checks, reloads }),
    delay: () => delay, async next() { const fn = callback; callback = null; await fn(); await settle() } }
}

test('open refresh, ten-minute data cycles and every second cycle update; cleanup', async () => {
  const f = fixture(); await settle()
  assert.deepEqual(f.count(), { refreshes: 1, checks: 0, reloads: 0 })
  await f.next(); assert.equal(f.count().checks, 0)
  await f.next(); assert.deepEqual(f.count(), { refreshes: 3, checks: 1, reloads: 1 })
  f.controller.stop()
})
test('drafts defer reload and safe action rechecks without discarding', async () => {
  let dirty = true
  const f = fixture({ drafts: () => dirty }); await settle(); await f.next(); await f.next()
  assert.equal(f.count().reloads, 0); assert.equal(f.notices.at(-1)[1], true)
  f.controller.reloadWhenSafe(); assert.equal(f.count().reloads, 0)
  dirty = false; f.controller.reloadWhenSafe(); assert.equal(f.count().reloads, 1)
  f.controller.stop()
})
test('hidden and offline suspend work without advancing update cycle', async () => {
  const f = fixture(); await settle(); f.page.hidden = true; await f.next()
  f.page.hidden = false; f.host.navigator.onLine = false; await f.next()
  assert.equal(f.count().refreshes, 1)
  f.host.navigator.onLine = true; await f.next(); assert.equal(f.count().checks, 0)
  await f.next(); assert.equal(f.count().checks, 1); f.controller.stop()
})
test('failure has bounded backoff and stopping pending call suppresses reload', async () => {
  const failed = fixture({ refresh: async () => { throw Error('offline') } }); await settle()
  assert.equal(failed.delay(), 200); await failed.next(); assert.equal(failed.delay(), 400)
  await failed.next(); assert.equal(failed.delay(), 400); failed.controller.stop()
  let finish
  const f = fixture({ checkUpdate: () => new Promise(resolve => { finish = resolve }) })
  await settle(); await f.next()
  const pending = f.next(); await settle(); f.controller.stop(); finish(true); await pending
  assert.equal(f.count().reloads, 0)
})
test('draft detector protects populated text, checkbox changes and files', () => {
  for (const field of [{ value: 'unfinished' }, { disabled: true, value: 'submitting draft' }, { type: 'checkbox', checked: true, defaultChecked: false },
    { type: 'file', files: [1] }, { isContentEditable: true, textContent: 'writing' }]) {
    assert.equal(hasDrafts({ querySelectorAll: () => [field] }), true)
  }
  assert.equal(hasDrafts({ querySelectorAll: () => [{ value: '' }, { type: 'hidden', value: 'internal' }] }), false)
})
test('cleared and whitespace edits remain dirty through timer update and cleanup removes listeners', async () => {
  for (const value of ['', '   ']) {
    const handlers = new Map(), field = { value }
    const page = { querySelectorAll: () => [field], addEventListener: (type, fn) => handlers.set(type, fn),
      removeEventListener: type => handlers.delete(type) }
    const tracker = trackDrafts(page)
    handlers.get('input')({ target: { closest: () => field } })
    assert.equal(tracker.hasDrafts(), true)
    const f = fixture({ drafts: tracker.hasDrafts }); await settle(); await f.next(); await f.next()
    assert.equal(f.count().reloads, 0)
    f.controller.reloadWhenSafe(); assert.equal(f.count().reloads, 0)
    f.controller.stop(); tracker.stop(); assert.equal(handlers.size, 0)
  }
})
test('slow cycles schedule no overlapping work and cleanup aborts outstanding request', async () => {
  let release, signal, calls = 0, scheduled = 0, cleared = 0
  const c = startPeriodicRefresh({ page: { hidden: false }, host: { navigator: { onLine: true } },
    refresh: value => { calls++; signal = value; return new Promise(resolve => { release = resolve }) },
    checkUpdate: async () => { throw Error('must not run') }, drafts: () => false,
    reload: () => { throw Error('must not reload') }, notify: () => {},
    clock: { setTimeout() { scheduled++; return 1 }, clearTimeout() { cleared++ } } })
  await settle(); assert.equal(calls, 1); assert.equal(scheduled, 0)
  c.stop(); assert.equal(signal.aborted, true); release(); await settle()
  assert.equal(scheduled, 0); assert.equal(cleared, 1)
})
test('same active component and unknown native builds never auto apply', async () => {
  for (const status of [{ active: 'a'.repeat(64), backend_build: 'b'.repeat(40) }, { active: null, backend_build: null }]) {
    let posts = 0
    const api = { get: async path => ({ data: path.endsWith('/check') ? { available: true, sha256: 'a'.repeat(64) } : status }),
      post: async () => { posts++; return {} } }
    await refreshUIComponent(api); assert.equal(posts, 0)
  }
})
test('verified server apply response enables reload, failures propagate', async () => {
  const calls = []
  const api = { get: async path => ({ data: path.endsWith('/check') ? { available: true, sha256: 'a'.repeat(64) } : { active: null, backend_build: 'b'.repeat(40) } }),
    post: async path => { calls.push(path); return { data: { active: 'a'.repeat(64) } } } }
  assert.equal(await refreshUIComponent(api), true); assert.deepEqual(calls, ['/updates/ui/apply'])
  api.post = async () => { throw Error('incompatible build') }
  await assert.rejects(refreshUIComponent(api), /incompatible/)
})
