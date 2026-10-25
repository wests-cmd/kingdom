export function computerName(username, computer, id) {
 const user = typeof username === 'string' ? username.trim() : ''
 const host = typeof computer === 'string' ? computer.trim() : ''
 if (user) return host && host !== user ? `${user} · ${host}` : user
 if (host && host !== 'kingdom-node') return host
 return `Computer ${String(id).slice(-8)}`
}
