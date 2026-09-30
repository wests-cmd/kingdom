let accessCode = ""
export function setAccessCode(value) { accessCode = value }
export function getAccessCode() { return accessCode }
export async function initializeSession() {
  if (window.kingdomDesktop?.getSessionToken) accessCode = await window.kingdomDesktop.getSessionToken()
}
