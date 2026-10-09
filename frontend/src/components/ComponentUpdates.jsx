import React,{useState} from 'react'
import api from '../api'
import useLiveData from '../hooks/useLiveData'
export default function ComponentUpdates(){
 const {data,error,refresh}=useLiveData('/updates/ui',30000)
 const [candidate,setCandidate]=useState(null),[busy,setBusy]=useState(false),[message,setMessage]=useState('')
 const action=async name=>{setBusy(true);setMessage('');try{if(name==='check'){const response=await api.get('/updates/ui/check');setCandidate(response.data);setMessage(response.data.reason||'Published UI package found. Compatibility is checked before activation.')}else{await api.post(`/updates/ui/${name}`);await refresh();setMessage('Interface selection updated. Refresh this page when ready; the backend keeps running.')}}catch(e){setMessage(e.response?.data?.detail||'Update could not be verified.')}finally{setBusy(false)}}
 return <section className="panel"><h2>Updates</h2><p>Backend version: {data?.backend_version||'Loading…'}</p><p>{data?.notice}</p><p className="muted">Downloads only the published UI component for compatible interface changes. This is a component update, not a binary patch. Existing pages keep their current assets until refreshed.</p>{error&&<p role="alert">{error}</p>}<div className="action-row"><button disabled={busy} onClick={()=>action('check')}>Check published updates</button>{candidate?.available&&<button disabled={busy} onClick={()=>action('apply')}>Verify and apply UI update</button>}{data?.active&&<button disabled={busy} onClick={()=>action('rollback')}>Restore previous interface</button>}</div>{candidate?.release_url&&<a href={candidate.release_url} target="_blank" rel="noreferrer">Release details and native installers</a>}{message&&<p role="status">{message}</p>}</section>
}
