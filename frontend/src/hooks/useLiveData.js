import { useState, useEffect, useCallback } from 'react'
import api from '../api'
import { startPolling } from '../common/polling'
import { REFRESH_EVENT } from '../common/periodicRefresh'
export default function useLiveData(path, interval = 5000) {
 const [data, setData] = useState(null)
 const [error, setError] = useState('')
 const [updated, setUpdated] = useState(null)
 const refresh = useCallback(async () => {
  try { const response = await api.get(path); setData(response.data); setError(''); setUpdated(new Date()) }
  catch { setError('Could not refresh this information. Check the Kingdom connection.') }
 }, [path])
 useEffect(() => { let active = true; setData(null); setError(''); setUpdated(null)
  const load = async () => { try { const response = await api.get(path); if (active) {setData(response.data);setError('');setUpdated(new Date())} } catch {if (active) setError('Could not load this information. Check the Kingdom connection.')} }
  let pending = false
  const singleLoad = async () => { if (pending) return; pending = true; try {await load()} finally {pending = false} }
  const stop = startPolling(singleLoad, interval)
  window.addEventListener(REFRESH_EVENT, singleLoad)
  return () => {active = false;stop();window.removeEventListener(REFRESH_EVENT, singleLoad)}
 }, [path, interval])
 return {data, error, updated, refresh}
}
