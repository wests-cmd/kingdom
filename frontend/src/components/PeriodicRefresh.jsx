import React, { useEffect, useRef, useState } from 'react'
import api from '../api'
import { REFRESH_EVENT, trackDrafts, refreshUIComponent, startPeriodicRefresh } from '../common/periodicRefresh'

export default function PeriodicRefresh() {
  const controller = useRef(null)
  const [notice, setNotice] = useState(null)
  useEffect(() => {
    const drafts = trackDrafts()
    controller.current = startPeriodicRefresh({
      refresh: async signal => {
        await api.get('/health/live', { signal, timeout: 15000 })
        window.dispatchEvent(new Event(REFRESH_EVENT))
      },
      checkUpdate: signal => refreshUIComponent(api, signal),
      drafts: drafts.hasDrafts, reload: () => window.location.reload(),
      notify: (message, ready) => setNotice({ message, ready })
    })
    return () => { drafts.stop(); controller.current.stop(); controller.current = null }
  }, [])
  return notice && <div role="status" className="panel">{notice.message}{notice.ready && <button onClick={() => { if (window.confirm('Reload the updated interface now? Any unsaved edits will be lost. Save your work first.')) window.location.reload() }}>Reload interface…</button>}</div>
}
