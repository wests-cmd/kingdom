import React, { useEffect, useState } from 'react'
import { QRCodeSVG } from 'qrcode.react'
import api from '../api'

export default function DevicePairing() {
  const [challenge, setChallenge] = useState(null)
  const [address, setAddress] = useState(window.location.protocol === 'https:' ? window.location.origin : '')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [now, setNow] = useState(Date.now())
  useEffect(() => { const timer = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(timer) }, [])
  const create = async () => {
    setBusy(true); setError('')
    try { setChallenge((await api.post('/mobile/challenge?ttl_seconds=300')).data) }
    catch (e) { setError(e.response?.data?.detail || 'Could not create a connection code. Check your Kingdom connection.') }
    finally { setBusy(false) }
  }
  let base = ''
  try { const url = new URL(address); if (url.protocol === 'https:' && !url.username && !url.password && !url.search && !url.hash && url.pathname === '/' && !['localhost', '127.0.0.1', '[::1]'].includes(url.hostname)) base = url.origin } catch { /* Display setup guidance rather than a broken QR. */ }
  const remaining = challenge ? Math.max(0, Math.ceil(challenge.expires_at - now / 1000)) : 0
  const link = base && challenge && remaining ? `${base}/#/connect?${new URLSearchParams({ code: challenge.code, fingerprint: challenge.kingdom_fingerprint })}` : ''
  return <section className="card" style={{ padding: 20 }}>
    <h2>Add a phone or other device</h2>
    <p>1. Create a connection code. 2. Scan the QR or open the connection page and enter the code. 3. Approve the request under Nodes & Cluster → Pending Approvals.</p>
    <label>Kingdom HTTPS address reachable from your device <input aria-label="Kingdom HTTPS address" type="url" placeholder="https://your-kingdom.example" value={address} onChange={e => setAddress(e.target.value)} style={{ width: '100%', padding: 10 }} /></label>
    {!base && <p>The desktop listens only on this computer. For a phone, first provide a reachable HTTPS Kingdom server address. A localhost QR would not connect your phone.</p>}
    <button onClick={create} disabled={busy}>{busy ? 'Creating…' : 'Create connection code'}</button>
    {error && <p role="alert">{error}</p>}
    {challenge && <div style={{ display: 'flex', flexWrap: 'wrap', gap: 24, marginTop: 16 }}>
      <div><p>Single-use connection code</p><strong style={{ fontSize: 24, overflowWrap: 'anywhere' }}>{remaining ? challenge.code : 'Code expired'}</strong><p>Expires in {remaining} seconds. Create a new code if needed.</p>
        {base && <p>Manual entry page: <a href={`${base}/#/connect`} target="_blank" rel="noreferrer">{base}/#/connect</a></p>}
      </div>
      {link && <div><QRCodeSVG value={link} size={220} marginSize={4} level="M" title="Scan to connect to Kingdom" /><p>Scan with your phone camera. No QR service receives your code.</p></div>}
    </div>}
    <p>This creates a limited browser companion request, not owner access or a compute worker. For a compute worker, use a Knight invitation and the Knight daemon.</p>
  </section>
}
