// This value is public build configuration, never a credential.
export function resolveBackendOrigin(configured, { development = false, origin } = {}) {
  const value = configured?.trim() || (development ? 'http://localhost:8000' : origin)
  const url = new URL(value)
  if (url.username || url.password || url.search || url.hash || url.pathname !== '/') {
    throw new Error('Kingdom API URL must be an origin without credentials, path, query or fragment.')
  }
  const local = ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname)
  if (url.protocol !== 'https:' && !(url.protocol === 'http:' && (local || !configured?.trim()))) {
    throw new Error('Kingdom API URL requires HTTPS outside localhost.')
  }
  return url.origin
}
