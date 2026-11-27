import { backendURL } from './backendConfig'
import { RealtimeClient } from './common/realtimeClient.js'

export const realtime = new RealtimeClient(() => {
  const url = new URL(backendURL('/ws'))
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  return new WebSocket(url)
})
