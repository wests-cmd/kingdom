import React, {useState} from 'react'
import api from '../api'
import useLiveData from '../hooks/useLiveData'

export default function SkillDocuments() {
 const saved = useLiveData('/skill-documents', 10000)
 const [content, setContent] = useState('')
 const [source, setSource] = useState('manual')
 const [harness, setHarness] = useState('generic')
 const [preview, setPreview] = useState(null)
 const [exported, setExported] = useState(null)
 const [busy, setBusy] = useState(false)
 const [error, setError] = useState('')
 const [notice, setNotice] = useState('')
 async function action(work) {
  setBusy(true); setError(''); setNotice('')
  try { await work() }
  catch (failure) { const detail = failure.response?.data?.detail; setError(typeof detail === 'string' ? detail : 'Could not complete this request. Check the document format and connection.') }
  finally { setBusy(false) }
 }
 function editContent(value) { setContent(value); setPreview(null) }
 async function readFile(event) {
  const file = event.target.files?.[0]; event.target.value = ''
  if (!file) return
  if (file.size > 262144) {setError('Choose a document up to 256 KB.'); return}
  await action(async () => {editContent(await file.text()); setNotice('Loaded locally. Select Review document to send it to Kingdom.')})
 }
 function download() {
  const url = URL.createObjectURL(new Blob([exported.content], {type:'text/markdown;charset=utf-8'}))
  const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'SKILL.md'
  document.body.appendChild(anchor); anchor.click(); anchor.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000)
 }
 return <section className="panel">
  <h2>Skills for your harness</h2>
  <p>Bring a SKILL.md from Hermes, Claude, or another harness. Kingdom saves its instructions and source so you can review and reuse them.</p>
  <p>Imported skills are untrusted context. Saving a document does not run it, install tools, or grant permissions. Referenced scripts and files are not included.</p>
  {(error || saved.error) && <p className="notice error" role="alert">{error || 'Could not load saved skill documents.'}</p>}
  {notice && <p className="notice" role="status">{notice}</p>}
  <fieldset disabled={busy} style={{border:0, padding:0, minWidth:0}}>
   <label>Choose SKILL.md <input type="file" accept=".md,text/markdown" onChange={readFile}/></label>
   <label style={{display:'block'}}>Or paste a skill document
    <textarea rows={9} value={content} onChange={event => editContent(event.target.value)} style={{width:'100%', boxSizing:'border-box'}} placeholder={'---\nname: repo-review\ndescription: Review a repository\n---\nDescribe the workflow here.'}/>
   </label>
   <label>Source label <input maxLength={500} value={source} onChange={event => {setSource(event.target.value); setPreview(null)}}/></label>
   <label>Original harness <input maxLength={64} value={harness} onChange={event => {setHarness(event.target.value); setPreview(null)}} placeholder="generic, hermes, claude…"/></label>
   <button disabled={!content.trim() || !source.trim() || !/^[a-z][a-z0-9_.-]{0,63}$/.test(harness)} onClick={() => action(async () => {
    if (new TextEncoder().encode(content).length > 262144) {setError('Keep the document within 256 KB.'); return}
    const response = await api.post('/skill-documents/preview', {content, source, harness}); setPreview(response.data)
   })}>Review document</button>
  </fieldset>
  {preview && <article className="record-detail">
   <h3>Review {preview.document.name}</h3><p>{preview.document.description}</p>
   <p>Source: {preview.document.provenance.source} · Harness: {preview.document.provenance.harness} · Untrusted</p>
   <p style={{overflowWrap:'anywhere'}}>Original file SHA-256: {preview.document.provenance.sha256}</p>
   <p style={{overflowWrap:'anywhere'}}>Confirmation checksum: {preview.checksum}</p>
   <pre style={{whiteSpace:'pre-wrap', overflowWrap:'anywhere', maxHeight:300, overflow:'auto'}}>{preview.document.instructions}</pre>
   <p>Review expires after five minutes. Saving replaces any document with the same name.</p>
   <button disabled={busy} onClick={() => action(async () => {
    await api.post('/skill-documents/confirm', {preview_id:preview.preview_id, checksum:preview.checksum})
    setPreview(null); setNotice('Saved as untrusted context. No execution permissions changed.'); saved.refresh()
   })}>Save reviewed document</button>
   <button disabled={busy} onClick={() => setPreview(null)}>Discard review</button>
  </article>}
  <h3>Saved skill documents</h3>
  {saved.data?.length === 0 && <p className="empty-state">No skill documents saved yet.</p>}
  {saved.data?.map(document => <article className="record-detail" key={document.skill_id}>
   <strong>{document.name}</strong><p>{document.description}</p>
   <button disabled={busy} onClick={() => action(async () => {const response = await api.get(`/skill-documents/${encodeURIComponent(document.skill_id)}/export`); setExported(response.data)})}>View and export</button>
  </article>)}
  {exported && <article className="record-detail"><h3>Export {exported.document.name}</h3>
   <p>Normalized Markdown includes name, description, and instructions. Harness-specific tool hints are omitted. Review for private information before sharing.</p>
   <pre style={{whiteSpace:'pre-wrap', overflowWrap:'anywhere', maxHeight:300, overflow:'auto'}}>{exported.content}</pre>
   <button disabled={busy} onClick={download}>Download SKILL.md</button>
   <button disabled={busy} onClick={() => action(async () => {await navigator.clipboard.writeText(exported.content); setNotice('Markdown copied.')})}>Copy Markdown</button>
   <button onClick={() => setExported(null)}>Close export</button>
  </article>}
 </section>
}
