import React, {useState} from 'react'
import api from '../api'
import useLiveData from '../hooks/useLiveData'

export default function KnowledgeSources() {
 const [scope, setScope] = useState('project')
 const [draftScope, setDraftScope] = useState('project')
 const [profile, setProfile] = useState('')
 const [source, setSource] = useState('notes.md')
 const [text, setText] = useState('')
 const [query, setQuery] = useState('')
 const [hits, setHits] = useState(null)
 const [busy, setBusy] = useState(false)
 const [error, setError] = useState('')
 const [notice, setNotice] = useState('')
 const [discordExport,setDiscordExport]=useState(''),[channels,setChannels]=useState(''),[discordPreview,setDiscordPreview]=useState(null)
 const [deleting, setDeleting] = useState(null)
 const profiles = useLiveData('/workspace/model-profiles', 15000)
 const documents = useLiveData(`/knowledge/${encodeURIComponent(scope)}/documents`, 10000)
 const configured = Array.isArray(profiles.data) ? profiles.data : (profiles.data?.profiles || [])
 async function action(work) {
  setBusy(true); setError(''); setNotice('')
  try {await work()}
  catch (failure) {const detail = failure.response?.data?.detail; setError(typeof detail === 'string' ? detail : 'The knowledge request failed. Check the embedding model, input size and connection.')}
  finally {setBusy(false)}
 }
 async function readFile(event) {
  const file = event.target.files?.[0]; event.target.value = ''
  if (!file) return
  if (file.size > 262144) {setError('Choose a UTF-8 text file up to 256 KB.'); return}
  await action(async () => {setText(await file.text()); setSource(file.name); setNotice('Loaded locally. Select Embed and save to send this text to your embedding provider.')})
 }
 return <section className="panel">
  <h2>Knowledge sources</h2>
  <p>Save source text as vectors, then retrieve relevant passages with citations. This adds context to your model; it does not train its weights. Sources remain untrusted.</p>
  {(error || documents.error) && <p role="alert" className="notice error">{error || 'Could not load this knowledge scope.'}</p>}
  {notice && <p role="status" className="notice">{notice}</p>}
  <form onSubmit={event => {event.preventDefault(); if (/^[a-z][a-z0-9_.-]{0,63}$/.test(draftScope)) {setScope(draftScope); setHits(null); setDeleting(null)} else setError('Use a lowercase scope name, such as project or shared.')}}>
   <label>Knowledge scope <input disabled={busy} maxLength={64} value={draftScope} onChange={event => setDraftScope(event.target.value)}/></label>
   <button disabled={busy}>Open scope</button>
  </form>
  <p>Current scope: <strong>{scope}</strong>. Sources and searches stay within this scope.</p>
  <details><summary>Import an explicit Discord message export</summary><p>Only the channel IDs you list are accepted. This does not fetch ordinary chat, verify the publisher or grant tool permissions.</p>
   <label>Allowed channel IDs, separated by commas<input value={channels} onChange={event=>{setChannels(event.target.value);setDiscordPreview(null)}}/></label>
   <label>Export JSON<textarea rows={6} maxLength={262144} value={discordExport} onChange={event=>{setDiscordExport(event.target.value);setDiscordPreview(null)}}/></label>
   <button disabled={busy||!profile||!discordExport||!channels} onClick={()=>action(async()=>{const {data}=await api.post(`/knowledge/${encodeURIComponent(scope)}/discord/preview`,{profile,allowed_channel_ids:channels.split(',').map(v=>v.trim()).filter(Boolean),export_json:discordExport});setDiscordPreview(data)})}>Preview export</button>
   {discordPreview&&<div><p>{discordPreview.notice}</p>{discordPreview.documents.map(doc=><article key={doc.source}><strong>{doc.source}</strong><pre style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{doc.text}</pre></article>)}<button disabled={busy} onClick={()=>action(async()=>{const {data}=await api.post(`/knowledge/${encodeURIComponent(scope)}/discord/import`,{profile,allowed_channel_ids:channels.split(',').map(v=>v.trim()).filter(Boolean),export_json:discordExport,checksum:discordPreview.checksum},{timeout:620000});setNotice(`Imported ${data.documents.length} sources into ${data.scope}.`);setDiscordPreview(null);documents.refresh()})}>Confirm and embed these sources</button></div>}
  </details>
  <fieldset disabled={busy} style={{border:0, padding:0, minWidth:0}}>
   <label>Embedding model profile <input value={profile} maxLength={64} list="embedding-profile-options" onChange={event => {setProfile(event.target.value); setHits(null)}} placeholder="Select your embedding profile"/></label>
   <datalist id="embedding-profile-options">{configured.map(item => <option key={item.id} value={item.id}>{item.model}</option>)}</datalist>
   <p>Use an installed embedding model, such as all-minilm. A chat-only model may reject embedding requests. Configure its connection under Model profiles.</p>
   <label>Choose text file <input type="file" accept=".txt,.md,.csv,.json,.log,text/plain,text/markdown" onChange={readFile}/></label>
   <label style={{display:'block'}}>Source label <input maxLength={500} value={source} onChange={event => setSource(event.target.value)}/></label>
   <label style={{display:'block'}}>Source text
    <textarea rows={7} value={text} onChange={event => setText(event.target.value)} style={{width:'100%', boxSizing:'border-box'}}/>
   </label>
   <p>Up to 256 KB. File contents go only to the configured embedding provider when you save. Links in the text are not fetched.</p>
   <button disabled={!profile || !text.trim() || !source.trim()} onClick={() => action(async () => {
    if (new TextEncoder().encode(text).length > 262144) {setError('Keep the source within 256 KB.'); return}
    const response = await api.post(`/knowledge/${encodeURIComponent(scope)}/documents`, {profile, source, text}, {timeout:600000})
    setNotice(`Saved ${response.data.chunks} chunks with ${response.data.dimension}-dimensional embeddings.`); setText(''); setHits(null); documents.refresh()
   })}>Embed and save</button>
   <form onSubmit={event => {event.preventDefault(); action(async () => {const response = await api.post(`/knowledge/${encodeURIComponent(scope)}/search`, {profile, query, limit:5}, {timeout:600000}); setHits(response.data)})}}>
    <label>Find relevant passages <input value={query} maxLength={8000} onChange={event => setQuery(event.target.value)}/></label>
    <button disabled={!profile || !query.trim()}>Search vectors</button>
   </form>
  </fieldset>
  {hits && <div><h3>Retrieved passages</h3>{hits.length === 0 && <p>No matching documents for this scope and embedding profile. Save sources first; changed embedding models need re-ingestion.</p>}{hits.map(hit => <article className="record-detail" key={hit.citation}>
   <strong>{hit.source}</strong><p>Cosine similarity: {Number(hit.score).toFixed(3)} · Chunk {hit.chunk}</p>
   <p style={{overflowWrap:'anywhere'}}><code>{hit.citation}</code></p><p style={{whiteSpace:'pre-wrap', overflowWrap:'anywhere'}}>{hit.text}</p>
  </article>)}</div>}
  <h3>Sources in {scope}</h3>
  {documents.data?.length === 0 && <p className="empty-state">No sources saved in this scope.</p>}
  {documents.data?.map(item => <article className="record-detail" key={item.id}>
   <strong>{item.source}</strong><p>Profile: {item.profile} · Dimensions: {item.dimension}</p>
   <p style={{overflowWrap:'anywhere'}}>SHA-256: {item.sha256}</p>
   {deleting === item.id ? <div><p>Delete this source and all its stored vectors?</p><button disabled={busy} onClick={() => action(async () => {await api.delete(`/knowledge/${encodeURIComponent(scope)}/documents/${encodeURIComponent(item.id)}`); setDeleting(null); setHits(null); documents.refresh(); setNotice('Source and vectors deleted.')})}>Delete source and vectors</button><button disabled={busy} onClick={() => setDeleting(null)}>Keep source</button></div> : <button disabled={busy} onClick={() => setDeleting(item.id)}>Remove source…</button>}
  </article>)}
 </section>
}
