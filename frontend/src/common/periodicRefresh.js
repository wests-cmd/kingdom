export const REFRESH_EVENT = 'kingdom:refresh-data'
export const TEN_MINUTES = 600000

// Conservative: even an untouched populated editor can contain an owner draft.
export function hasDrafts(page = document) {
  return [...page.querySelectorAll('input,textarea,[contenteditable="true"],select')].some(field => {
    if (['button', 'submit', 'hidden'].includes(field.type)) return false
    if (field.type === 'checkbox' || field.type === 'radio') return field.checked !== field.defaultChecked
    if (field.type === 'file') return field.files?.length > 0
    return String(field.isContentEditable ? field.textContent : field.value || '').trim().length > 0
  })
}

// Sticky for this app session: clearing an editor can itself be an unsaved edit.
// Only an explicit owner reload discards this protection; polling never resets it.
export function trackDrafts(page = document) {
  let dirty = false
  const changed = event => {
    const field = event.target?.closest?.('input,textarea,select,[contenteditable="true"]')
    if (field && !['button', 'submit', 'hidden'].includes(field.type)) dirty = true
  }
  page.addEventListener('input', changed, true)
  page.addEventListener('change', changed, true)
  return { hasDrafts: () => dirty || hasDrafts(page), stop() {
    page.removeEventListener('input', changed, true)
    page.removeEventListener('change', changed, true)
  } }
}

export async function refreshUIComponent(api, signal) {
  const options = { signal, timeout: 45000 }
  const { data: status } = await api.get('/updates/ui', options)
  const { data: candidate } = await api.get('/updates/ui/check', options)
  if (candidate?.available !== true || !/^[a-f0-9]{64}$/.test(candidate.sha256 || '') || candidate.sha256 === status?.active) return false
  if (!/^[a-f0-9]{40}$/.test(status?.backend_build || '')) {
    return 'A published interface is available. Automatic activation requires a verified native build; review Updates.'
  }
  // The server re-fetches and verifies checksum, manifest and exact native build.
  const { data: applied } = await api.post('/updates/ui/apply', {}, options)
  if (!/^[a-f0-9]{64}$/.test(applied?.active || '') || applied.active === status.active) return false
  return true
}

export function startPeriodicRefresh({ refresh, checkUpdate, drafts, reload, notify,
  page = document, host = window, clock = globalThis, interval = TEN_MINUTES }) {
  let stopped = false, pending = false, timer, cycles = 0, failures = 0, waiting = false
  const abort = new AbortController()
  const usable = () => !page.hidden && host.navigator.onLine !== false
  const schedule = () => { if (!stopped) timer = clock.setTimeout(tick, Math.min(interval * 2 ** failures, interval * 4)) }
  const tryReload = () => {
    if (stopped || !waiting) return
    if (!usable() || drafts()) notify('Interface update ready. Save your work, then explicitly reload when ready; unsaved edits are protected.', true)
    else { waiting = false; reload() }
  }
  const tick = async () => {
    if (stopped || pending) return
    if (!usable()) { schedule(); return }
    pending = true
    try {
      await refresh(abort.signal)
      if (stopped) return
      cycles++
      // Opening is refresh cycle zero, then UI checks on cycles two, four…
      if (cycles > 1 && (cycles - 1) % 2 === 0) {
        const update = await checkUpdate(abort.signal)
        if (stopped) return
        if (update === true) { waiting = true; tryReload() }
        else if (typeof update === 'string') notify(update, false)
      }
      failures = 0
    } catch {
      if (!stopped) { failures = Math.min(failures + 1, 2); notify('Periodic refresh failed. Your drafts are preserved; retrying automatically.', waiting) }
    } finally { pending = false; schedule() }
  }
  // Visibility/online events never trigger requests; the bounded timer catches up.
  void tick()
  return { reloadWhenSafe: tryReload, stop() { stopped = true; abort.abort(); clock.clearTimeout(timer) } }
}
