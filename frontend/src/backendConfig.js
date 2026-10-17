import { resolveBackendOrigin } from './backendLocation'

export const backendOrigin = resolveBackendOrigin(import.meta.env.VITE_API_URL, {
  development: import.meta.env.DEV,
  origin: window.location.origin
})
export const backendURL = path => new URL(path, `${backendOrigin}/`).href
