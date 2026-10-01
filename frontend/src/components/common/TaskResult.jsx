import React from 'react'

export function scrubText(value) {
 return String(value || '').replace(/(?:ghp_|github_pat_|sk-)[A-Za-z0-9_-]{10,}|bearer\s+\S+|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}/gi,'[redacted]')
  .replace(/((?:password|api[_ -]?key|secret|token)\s*[:=]\s*)[^\s,;]+/gi,'$1[redacted]')
}
function scrub(value,depth=0) {
 if(depth>10) return '[depth limit]'
 if(Array.isArray(value)) return value.slice(0,100).map(item=>scrub(item,depth+1))
 if(value && typeof value==='object') return Object.fromEntries(Object.entries(value).slice(0,100).map(([key,item])=>[key, /token|password|secret|credential|private.?key|api.?key|authorization/i.test(key) ? '[redacted]' : scrub(item,depth+1)]))
 return typeof value==='string' ? scrubText(value).slice(0,10000) : value
}
export function DebugDetails({value}) {
 return <details><summary>Developer diagnostics (credentials filtered)</summary><pre>{JSON.stringify(scrub(value),null,2)}</pre></details>
}
export default function TaskResult({result}) {
 const records = Array.isArray(result?.results) ? result.results : []
 if(!records.length) return <p className="muted">No supported result summary is available.</p>
 return <div>{records.map((record,index)=>{
  const outcome=record.outcome || {}
  const verified=record.verification?.state === 'VERIFIED'
  if(outcome.tool === 'provider.metadata@1.0.0') return <p key={index}>{verified ? 'Reviewed metadata response verified.' : 'Metadata response has not been verified.'} This confirms a read-only response, not a completed research or purchasing workflow.</p>
  if(outcome.tool === 'text.analyze@1.0.0') return <p key={index}>{verified ? 'Verified text analysis' : 'Unverified text analysis'}: {Number.isInteger(outcome.output?.words) ? outcome.output.words : 'Unavailable'} words; {Number.isInteger(outcome.output?.characters) ? outcome.output.characters : 'Unavailable'} characters.</p>
  if(outcome.tool === 'code.python.analyze@1.0.0') return <p key={index}>{verified && outcome.output?.valid_python ? 'Python syntax verified.' : 'Syntax has not been verified.'} Source code was analyzed without being executed.</p>
  if(outcome.kind === 'model_response') return <details key={index}><summary>View generated text</summary><p className="muted">Generated text does not verify external actions.</p><pre>{scrubText(outcome.output?.text).slice(0,10000)}</pre></details>
  return <p key={index}>Unsupported result format. Check authorized developer diagnostics.</p>
 })}</div>
}
