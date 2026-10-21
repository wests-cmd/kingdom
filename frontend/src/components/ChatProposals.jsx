import React, {useEffect, useState} from 'react'
import api from '../api'

export default function ChatProposals() {
  const [profiles, setProfiles] = useState([])
  const [form, setForm] = useState({project_scope:'projects/default', objective:'', acceptance:'', exported_context:'', local_profile:''})
  const [proposal, setProposal] = useState(null)
  const [reply, setReply] = useState('')
  const [review, setReview] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => {
    api.get('/workspace/model-profiles').then(r => setProfiles((r.data.profiles || []).filter(p => {
      try {return p.provider === 'ollama' && ['localhost','127.0.0.1','[::1]'].includes(new URL(p.endpoint).hostname)} catch {return false}
    }))).catch(() => setError('Could not load local model connections.'))
    const saved = localStorage.getItem('kingdom.chat-proposal-id')
    if (saved) api.get(`/chat-proposals/${encodeURIComponent(saved)}`).then(r => setProposal(r.data)).catch(() => setError('The last proposal could not be restored from this Kingdom.'))
  }, [])
  useEffect(() => {if (proposal) localStorage.setItem('kingdom.chat-proposal-id', proposal.id)},[proposal])
  const act = async fn => {setBusy(true); setError(''); try {await fn()} catch(e) {setError(e.response?.data?.detail || 'The operation did not finish. Your saved proposal remains available.')} finally {setBusy(false)}}
  const field = key => ({value:form[key], style:{width:'100%',boxSizing:'border-box',minWidth:0}, onChange:e => setForm({...form,[key]:e.target.value})})
  const create = e => {e.preventDefault(); act(async () => {setProposal((await api.post('/chat-proposals',form)).data); setReview(null); setReply('')})}
  const submit = () => act(async () => {
    await api.post(`/chat-proposals/${proposal.id}/reply`,{text:reply})
    const next = (await api.post(`/chat-proposals/${proposal.id}/review`)).data
    setProposal(next)
    await api.post(`/requests/${next.request_id}/background`,{})
    setReview((await api.get(`/requests/${next.request_id}`)).data)
  })
  return <section className="panel" style={{minWidth:0}}>
    <h2>ChatGPT and other chat helpers</h2>
    <p>Ask a chat for code, then have Kingdom review it with your local model. This assisted connection uses copy and paste. It does not use a Codex worker or automatically operate your chat account.</p>
    <form onSubmit={create} style={{display:'grid',gap:12,minWidth:0}}>
      <label>Project workspace<input required maxLength={160} {...field('project_scope')} /></label>
      <label>What should change?<textarea required maxLength={3000} {...field('objective')} /></label>
      <label>How will we check it?<textarea required maxLength={3000} {...field('acceptance')} /></label>
      <details><summary>Choose context to share</summary><p>Only text you put here goes into the prompt. Leave out passwords, tokens and private vault notes.</p><textarea aria-label="Context to share with chat" maxLength={10000} {...field('exported_context')} /></details>
      <label>Local reviewer<select required {...field('local_profile')}><option value="">Choose a local model connection</option>{profiles.map(p => <option key={p.id} value={p.id}>{p.id} · {p.model}</option>)}</select></label>
      <button disabled={busy || !profiles.length}>1. Prepare a chat prompt</button>
      {!profiles.length && <p>First add a local Ollama model in the model connection settings. Cloud connections are not used as the reviewer.</p>}
    </form>
    {proposal && <div className="page-stack" style={{minWidth:0,marginTop:16}}>
      <p>Saved proposal: {proposal.id} · {proposal.status.replaceAll('_',' ')}</p>
      <label>Copy this prompt into your chat<textarea readOnly aria-label="Prepared chat prompt" value={proposal.prompt} rows={7} style={{width:'100%',boxSizing:'border-box'}} /></label>
      <a href="https://chatgpt.com/" target="_blank" rel="noopener noreferrer">Open ChatGPT Chat</a>
      {!proposal.proposal_sha256 && <><label>2. Paste the chat’s answer<textarea aria-label="Chat proposal reply" maxLength={12000} value={reply} onChange={e => setReply(e.target.value)} rows={7} style={{width:'100%',boxSizing:'border-box'}} /></label><button disabled={busy || !reply.trim()} onClick={submit}>Save and review locally</button></>}
      {proposal.request_id && <button disabled={busy} onClick={() => act(async () => setReview((await api.get(`/requests/${proposal.request_id}`)).data))}>Refresh local review</button>}
      {review && <div><h3>Local assessment · {review.status.replaceAll('_',' ')}</h3><pre style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{review.answer || review.error || 'Work is saved. Refresh to check its progress.'}</pre></div>}
      <p>A model’s assessment can be wrong. Code stays a proposal until a governed coding task applies it and independent tests pass. No project files are changed by this review.</p>
      <button disabled={busy} onClick={() => {localStorage.removeItem('kingdom.chat-proposal-id');setProposal(null);setReview(null);setReply('')}}>Prepare another proposal</button>
    </div>}
    {error && <p role="alert">{error}</p>}
  </section>
}
