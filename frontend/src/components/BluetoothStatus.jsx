import React, {useState} from 'react'
import useLiveData from '../hooks/useLiveData'
import BluetoothStatusView from './BluetoothStatusView'

export default function BluetoothStatus() {
  const {data, error, refresh} = useLiveData('/peer-paths/bluetooth/status', null)
  const [busy, setBusy] = useState(false)
  const onRefresh = async () => {
    if (busy) return
    setBusy(true)
    try { await refresh() } finally { setBusy(false) }
  }
  return <BluetoothStatusView data={data} error={error} loading={!data && !error} busy={busy} onRefresh={onRefresh}/>
}
