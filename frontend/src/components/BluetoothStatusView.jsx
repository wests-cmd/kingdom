import React from 'react'

export default function BluetoothStatusView({data, error, loading, busy, onRefresh}) {
  const available = !error && data
  const state = available ? data.adapter_state : 'unknown'
  const adapters = available && Array.isArray(data.adapters) ? data.adapters : []
  const links = available && Array.isArray(data.pan_links) ? data.pan_links : []
  const status = loading ? 'Checking Bluetooth…' : error ? 'Bluetooth status unavailable' :
    state === 'absent' ? 'No usable Bluetooth adapter reported' : state === 'off' ? 'Bluetooth is off' :
    state === 'on' ? links.length ? 'Bluetooth PAN link connected' : 'Bluetooth is on · No PAN connection' :
    'Bluetooth readiness is unknown'
  return <section className="panel" aria-label="Bluetooth on this Knight">
    <h3>Bluetooth on this Knight</h3>
    <p role={error ? 'alert' : 'status'}>{status}</p>
    {error ? <p>The current hardware report could not be read. No connection is assumed.</p> : available && <>
      <p>{data.reason}</p>
      {adapters.length > 0 && <ul aria-label="Reported Bluetooth adapters">{adapters.map(adapter =>
        <li key={adapter.path}>{adapter.address || 'Address not reported'} · {adapter.powered ? 'On' : 'Off'}</li>)}</ul>}
      {links.length > 0 && <ul aria-label="Connected paired PAN links">{links.map(link =>
        <li key={link.interface}>{link.interface} · Paired PAN · {link.device_address || 'Address not reported'}</li>)}</ul>}
      <p>Peer route: not checked by this hardware report. A signed control probe separately checks the route and the approved Knight.</p>
      <p className="muted">Observed {new Date(data.observed_at * 1000).toLocaleString()}. This is a dated observation, not a continuous connection check.</p>
    </>}
    <p className="muted">Only this Knight is reported here. Normal OS pairing and PAN setup are required. Control probes stay opt-in; no task routing or automatic pairing is enabled.</p>
    <button type="button" disabled={busy || loading} onClick={onRefresh}>{busy ? 'Refreshing…' : 'Refresh Bluetooth status'}</button>
    <p className="muted">Checked on opening and by the existing ten-minute interface refresh.</p>
  </section>
}
