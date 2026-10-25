// UI refreshes are observations, not peer leases or execution heartbeats.
export function startPolling(load, interval, page = document, clock = globalThis) {
  let stopped = false, pending = false, timer
  const delay = () => page.hidden ? Math.max(interval, 60000) : interval
  const schedule = () => { if (!stopped) timer = clock.setTimeout(tick, delay()) }
  const tick = async () => {
    if (stopped || pending) return
    pending = true
    try { await load() } catch { /* caller owns its visible error state */ }
    finally { pending = false; schedule() }
  }
  const visibility = () => {
    clock.clearTimeout(timer)
    if (pending) return
    if (page.hidden) schedule()
    else void tick()
  }
  page.addEventListener('visibilitychange', visibility)
  void tick()
  return () => { stopped = true; clock.clearTimeout(timer); page.removeEventListener('visibilitychange', visibility) }
}
