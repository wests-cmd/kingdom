import { useState, useEffect, useCallback } from 'react'
import api from '../api'
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
  load(); const timer = setInterval(load, interval); return () => {active = false;clearInterval(timer)}
 }, [path, interval])
 return {data, error, updated, refresh}
}
