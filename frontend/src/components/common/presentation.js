export function deviceLabel(value,fallback='Registered device') {
 return typeof value === 'string' && /^[\p{L}\p{N}][\p{L}\p{N} ._'-]{0,79}$/u.test(value)
  && !/^(import|from|def|class|function|return|const|let|var)\s/i.test(value) ? value : fallback
}
export function capabilityLabel(value) {
 const known = ['compute','gpu','storage_read','storage_write','network','tool_execution','memory_access','ai_map_access',
  'filesystem.read','filesystem.write','filesystem.delete','process.execute','docker.execute','network.access','model.inference',
  'memory.read','memory.write','ai_map.read','ai_map.write','node.register','node.execute','system.admin','providers.test',
  'planner.execute','coder.execute','researcher.execute','memory.execute','security.execute']
 return known.includes(value) ? value.replaceAll('_',' ').replaceAll('.',' ') : 'Unsupported capability metadata'
}
export function fingerprintLabel(value) {
 return typeof value === 'string' && /^[a-f0-9]{64}$/i.test(value) ? value : 'No verified fingerprint recorded'
}
export function nodeStateLabel(value) {
 return ['CONNECTED','APPROVED','PENDING','PENDING_APPROVAL','DISCOVERED','DISCONNECTED','OFFLINE','STALE','REVOKED','REJECTED','QUARANTINED','healthy','idle','ready','working','running'].includes(value) ? value : 'Unknown'
}
export function workerLabel(value) {
 const labels = {planner:'Planning',coder:'Coding',researcher:'Research',memory:'Memory',security:'Security'}
 return labels[value] || 'Registered worker'
}
