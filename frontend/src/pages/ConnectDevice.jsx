import React, { useState } from 'react'

const hex = bytes => Array.from(new Uint8Array(bytes), byte => byte.toString(16).padStart(2, '0')).join('')

export default function ConnectDevice() {
  const params = new URLSearchParams(window.location.hash.split('?')[1] || '')
  const [code, setCode] = useState(params.get('code') || '')
  const [name, setName] = useState('My device')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [session, setSession] = useState(null)
  const request = async (path, body, token) => {
    const response = await fetch(path, { method: 'POST', credentials: 'omit',
      headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: JSON.stringify(body) })
    const result = await response.json()
    if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'Connection failed.')
    return result
  }
  const pair = async event => {
    event.preventDefault(); setBusy(true); setMessage('Connecting…')
    try {
      if (!window.isSecureContext || !crypto.subtle) throw new Error('Open Kingdom using HTTPS to connect this device.')
      const identityResponse = await fetch('/nodes/identity', { credentials: 'omit' })
      if (!identityResponse.ok) throw new Error('Kingdom identity could not be verified.')
      const identity = await identityResponse.json()
      if (params.get('fingerprint') && params.get('fingerprint') !== identity.fingerprint) throw new Error('Kingdom identity does not match this invitation.')
      const keys = await crypto.subtle.generateKey({ name: 'Ed25519' }, false, ['sign', 'verify'])
      const deviceId = `device-${crypto.randomUUID()}`
      const normalizedCode = code.trim().toUpperCase()
      const signature = await crypto.subtle.sign('Ed25519', keys.privateKey,
        new TextEncoder().encode(`${normalizedCode}:${deviceId}:${identity.node_id}`))
      const result = await request('/mobile/pair', { code: normalizedCode, device_id: deviceId,
        device_name: name.trim(), device_public_key_hex: hex(await crypto.subtle.exportKey('raw', keys.publicKey)), signature: hex(signature) })
      setSession(result.session_token)
      setMessage('Connection request sent. Approve this device in Kingdom → Nodes & Cluster → Pending Approvals. Keep this page open.')
      history.replaceState(null, '', '/#/connect')
      setCode('')
    } catch (error) { setMessage(error.name === 'NotSupportedError' ? 'This browser does not support secure device pairing. Update it and try again.' : error.message) }
    finally { setBusy(false) }
  }
  const checkStatus = async () => {
    setBusy(true)
    try { const result = await request('/mobile/session/status', {}, session)
      setMessage(`${result.device_name}: ${result.device_state}. This companion connection does not grant owner access or run tasks.`)
    } catch (error) { setMessage(error.message) }
    finally { setBusy(false) }
  }
  return <main style={{ maxWidth: 520, margin: '32px auto', padding: 24, color: '#eee' }}>
    <h1>Connect this device to Kingdom</h1>
    <p>Scan the QR code from Kingdom or enter its single-use connection code here. Your owner access code is never needed on this page.</p>
    {!session && <form onSubmit={pair} style={{ display: 'grid', gap: 16 }}>
      <label>Connection code <input aria-label="Connection code" value={code} onChange={e => setCode(e.target.value)} required maxLength={64} autoComplete="off" style={{ width: '100%', padding: 12 }} /></label>
      <label>Device name <input aria-label="Device name" value={name} onChange={e => setName(e.target.value)} required maxLength={100} style={{ width: '100%', padding: 12 }} /></label>
      <button disabled={busy}>{busy ? 'Connecting…' : 'Request connection'}</button>
    </form>}
    {session && <button onClick={checkStatus} disabled={busy}>Check approval status</button>}
    {message && <p role="status">{message}</p>}
    <p>Connections expire after 24 hours or when Kingdom restarts. Native Android/iOS apps are not included; this is a browser companion.</p>
  </main>
}
