import React, {useState, useEffect} from 'react'
import api from '../api'
import useLiveData from '../hooks/useLiveData'

export default function SkillMaps() {
 const maps = useLiveData('/skillmaps',5000)
 const providers = useLiveData('/providers/catalog',10000)
 const links = useLiveData('/discord/links',5000)
 const profiles = useLiveData('/profiles/preferences',5000)
 const workers = useLiveData('/knights',5000)
 const [preview,setPreview] = useState(null)
 const [notice,setNotice] = useState('')
 const [error,setError] = useState('')
 const [busy,setBusy] = useState(false)
 const [code,setCode] = useState('')
 const [grants,setGrants] = useState([])
 const [profile,setProfile] = useState('')
 useEffect(() => {
  if (!profile && profiles.data) setProfile(profiles.data.preferences?.profile_id || profiles.data.available[0]?.profile_id || '')
 }, [profiles.data, profile])
 const [results,setResults] = useState({})
 async function action(work) {
  setBusy(true);setError('');setNotice('')
  try {await work(); maps.refresh();providers.refresh();links.refresh();profiles.refresh()}
  catch (failure) {const detail=failure.response?.data?.detail;setError(typeof detail === 'string' ? detail : 'The request could not be completed. Check permissions, file format and the current worker or provider state.')}
  finally {setBusy(false)}
 }
 async function upload(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  if (file.size > 262144) {setError('Choose a skill map smaller than 256 KB.');return}
  await action(async () => {const response = await api.post('/skillmaps/preview',{filename:file.name,content:await file.text()});setPreview(response.data)})
 }
 async function exportMap(mapId) {
  await action(async () => {
   const response = await api.get(`/skillmaps/${encodeURIComponent(mapId)}/export`)
   const anchor = document.createElement('a')
   anchor.href=`/skillmaps/${encodeURIComponent(mapId)}/download`;anchor.download=response.data.filename
   document.body.appendChild(anchor);anchor.click();anchor.remove()
   setNotice(`Exported ${response.data.filename}. SHA-256: ${response.data.checksum}`)
  })
 }
 return <div className="page-stack">
  <div className="page-heading"><div><p className="eyebrow">Portable preferences</p><h1>Skill maps & Discord</h1><p>Bring a map, review what this Kingdom can support, then test reviewed providers through your workers.</p></div></div>
  {(error || maps.error || providers.error || links.error || profiles.error) && <p role="alert" className="notice error">{error || 'Could not load integration records. Check your connection.'}</p>}
  {notice && <p role="status" className="notice">{notice}</p>}
  <section className="panel"><h2>Import a skill map</h2><p>JSON or YAML, up to 256 KB. Importing saves preferences and provider requirements. It grants no permissions and installs no code.</p><label>Choose a skill map <input type="file" accept=".json,.yaml,.yml" disabled={busy} onChange={upload}/></label>
   {preview && <div className="record-detail"><h3>Review: {preview.map_id}</h3><p>{preview.skills} requested skills · {preview.unsupported_skills.length} unsupported · {preview.compatible_knights.length} compatible workers</p><p>Supported metadata checks: {preview.understood_capabilities.join(", ") || "None"}</p><p>Unsupported capabilities: {preview.unsupported_capabilities.join(", ") || "None"}</p><p>Unsupported skills: {preview.unsupported_skills.join(', ') || 'None'}</p>{preview.providers.map(provider => <p key={provider.provider_id}>{provider.provider_id}: {provider.reviewed ? 'Reviewed test adapter' : 'No reviewed test'}{provider.credential_required ? ' · credential reference required; testing unsupported' : ' · no credential reference supplied'}</p>)}<button disabled={busy} onClick={() => action(async () => {await api.post('/skillmaps/confirm',{preview_id:preview.preview_id,checksum:preview.checksum});setPreview(null);setNotice('Map saved as preferences.')})}>Confirm import</button><button onClick={() => setPreview(null)}>Discard preview</button></div>}
  </section>
  <section className="panel"><h2>Saved maps</h2>{maps.data?.length === 0 && <p className="empty-state">No maps saved yet.</p>}{maps.data?.map(map => <article className="record-detail" key={map.map_id}><h3>{map.map_id}</h3><div className="tab-row"><button disabled={busy} onClick={() => action(async () => {const response=await api.post(`/skillmaps/${map.map_id}/test`);setNotice(`Queued ${response.data.tasks.length} tasks. ${response.data.skipped.length} providers unsupported or disabled. Check Tasks for progress and approvals.`)})}>Test reviewed providers</button><button disabled={busy} onClick={() => action(async () => {const response=await api.post(`/skillmaps/${map.map_id}/results`);setResults(current => ({...current,[map.map_id]:response.data.results}));setNotice('Collected completed task evidence.')})}>Collect results</button><button disabled={busy} onClick={() => exportMap(map.map_id)}>Export JSON</button></div>{results[map.map_id]?.map(result => <p key={result.provider_id}>{result.provider_id}: {result.status}</p>)}<label>Preferred profile <select value={profile} onChange={event => setProfile(event.target.value)}>{profiles.data?.available.map(item => <option key={item.profile_id} value={item.profile_id}>{item.name}</option>)}</select></label><button disabled={busy} onClick={() => action(async () => {await api.post('/profiles/preferences',{profile_id:profile,map_id:map.map_id});setNotice('Preference saved. Installed workers and permissions were not changed.')})}>Use these preferences</button></article>)}</section>
  <section className="panel"><h2>Reviewed provider tests</h2><p>Enable only the services you want this Kingdom to contact. Tests read public metadata; they do not run uploaded endpoints.</p>{providers.data?.reviewed.map(provider => <div className="record-detail" key={provider.provider_id}><strong>{provider.provider_id}</strong><p>{provider.capabilities.join(', ')} · {provider.enabled ? 'Enabled' : 'Disabled'}</p><a href={provider.documentation} target="_blank" rel="noreferrer">Provider documentation</a><button disabled={busy} onClick={() => action(async () => {await api.post(`/providers/${provider.provider_id}/enable`,{enabled:!provider.enabled})})}>{provider.enabled ? 'Disable test' : 'Enable test'}</button></div>)}<h3>Worker permission</h3><p>Choose an installed worker to run reviewed provider tests. This adds only the provider-test permission.</p>{workers.data?.knights?.map(worker => <span key={worker.role}><button disabled={busy} onClick={() => action(async () => {await api.post(`/providers/workers/${worker.role}/permission`,{enabled:true});setNotice(`${worker.display_name} can run reviewed provider tests.`)})}>Allow {worker.display_name}</button><button disabled={busy} onClick={() => action(async () => {await api.post(`/providers/workers/${worker.role}/permission`,{enabled:false});setNotice('Worker test permission removed.')})}>Remove permission</button></span>)}<h3>Public API directory</h3><p>{providers.data?.discovered.length ?? 'Loading'} locally recorded discovery entries. Directory claims do not verify safety, authentication or availability.</p><button disabled={busy} onClick={() => action(async () => {const response=await api.post('/providers/catalog/refresh');setNotice(`Saved ${response.data.count} discovery entries from Public APIs.`)})}>Refresh directory</button></section>
  <section className="panel"><h2>Link a Discord identity</h2><p>{links.data?.configured ? 'Discord is configured. A live connection has not been certified by this app.' : 'Discord is disabled. Follow the repository’s Discord setup guide before generating a link code.'}</p><p>Provider testing needs test skillmaps, run task and providers test. Managing providers changes shared settings for this Kingdom.</p><p>Run /kingdom in Discord, then enter its five-minute code here. Choose each permission deliberately. Server membership grants nothing.</p><form onSubmit={event => {event.preventDefault();action(async () => {await api.post('/discord/links/confirm',{code,grants});setCode('');setGrants([]);setNotice('Discord identity linked with the selected permissions.')})}}><label>Link code <input type="password" autoComplete="off" value={code} onChange={event => setCode(event.target.value)} required/></label><div>{links.data?.available_permissions.map(grant => <label key={grant} style={{display:'block'}}><input type="checkbox" checked={grants.includes(grant)} onChange={event => setGrants(current => event.target.checked ? [...current,grant] : current.filter(item => item !== grant))}/>{grant.replaceAll('_',' ').replaceAll('.',' ')}</label>)}</div><button disabled={busy}>Confirm identity link</button></form>{links.data?.links.map(link => <div className="record-detail" key={link.user_id}><strong>Discord user {link.user_id}</strong><p>{link.revoked ? 'Revoked' : `${link.grants.length} permissions granted`}</p>{!link.revoked && <button disabled={busy} onClick={() => action(async () => {await api.post(`/discord/links/${link.user_id}/revoke`);setNotice('Discord access revoked.')})}>Revoke access</button>}</div>)}</section>
 </div>
}
