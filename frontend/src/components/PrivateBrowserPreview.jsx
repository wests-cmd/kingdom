import React, {useState} from 'react'
import api from '../api'
import useLiveData from '../hooks/useLiveData'
import {privateBrowserPreviewTask} from '../privateBrowserPreview'

/** Read-only experimental preview, not an OS-level private desktop. */
export default function PrivateBrowserPreview({onQueued}) {
  const {data, error} = useLiveData('/agent-sessions/browser-readiness', 12000)
  const [url, setUrl] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [problem, setProblem] = useState('')
  const submit = async event => {
    event.preventDefault()
    setBusy(true)
    setMessage('')
    setProblem('')
    try {
      const request = privateBrowserPreviewTask(url)
      const {data: task} = await api.post('/tasks', request)
      setMessage('Task ' + task.id + ' queued for Kingdom authorization and review. Browser observation is not proof that the website objective succeeded.')
      onQueued?.()
    } catch (error) {
      setProblem(error.response?.data?.detail || error.message || 'Browser task could not be queued.')
    } finally { setBusy(false) }
  }
  const ready = Boolean(data?.ready_for_disposable_testing)
  return <details className="panel">
    <summary>Private browser preview (experimental)</summary>
    <p>Preview an owner-approved HTTPS website in a disposable headless browser. This does not move your mouse or type in your desktop applications. A powered-off host cannot execute this task.</p>
    <p role="note"><strong>Not production-certified.</strong> Browser routing is not an OS network sandbox. The feature stays disabled until an operator configures it and grants permission. Do not use sensitive accounts or payments.</p>
    {error && <p role="alert">Browser readiness could not be checked: {String(error.message || error)}</p>}
    {data && <div role="status"><strong>{ready ? 'Disposable testing available' : 'Private browser unavailable'}</strong>
      {data.public_release_certified === false && <p>Public unattended certification: not verified.</p>}
      {(data.blockers || []).length > 0 && <ul>{data.blockers.map((reason, i) => <li key={i}>{reason}</li>)}</ul>}
    </div>}
    <form onSubmit={submit}>
      <label>Approved HTTPS website<input type="url" inputMode="url" placeholder="https://example.org/" maxLength={2048}
        autoComplete="off" value={url} onChange={event => setUrl(event.target.value)} required /></label>
      <button type="submit" disabled={busy || !ready || !url.trim()}>
        {busy ? 'Queuing preview…' : 'Queue read-only preview'}
      </button>
    </form>
    {problem && <p role="alert">{String(problem)}</p>}
    {message && <p role="status">{message}</p>}
  </details>
}
