import React, {useEffect, useState} from 'react'

export default function DesktopUpdates() {
 const bridge=window.kingdomDesktop?.updates
 const [status,setStatus]=useState(null),[update,setUpdate]=useState(null),[busy,setBusy]=useState(false),[message,setMessage]=useState('')
 useEffect(()=>{if(bridge)bridge.status().then(setStatus).catch(()=>setMessage('Could not read desktop update status.'))},[])
 if(!bridge)return null
 const action=async name=>{
  setBusy(true);setMessage('')
  try{
   const result=await bridge[name]()
   if(name==='check'){setUpdate(result);setMessage(result.reason||(result.available?`Version ${result.latest} is ready to download.`:'Your desktop is up to date.'))}
   if(name==='download'){setStatus(result);setMessage('Download verified. Keep working, or update and restart when ready.')}
   if(name==='install')setMessage(result.cancelled?'Update postponed. Your download is ready.':'Restarting to finish the update…')
  }catch(error){setMessage(error.message||'Update failed. Your current installation and data are retained.')}
  finally{setBusy(false)}
 }
 return <section className="panel"><h2>Desktop updates</h2><p>Installed version: {status?.current||'Loading…'}</p><p>Update Kingdom here without uninstalling it. Profiles, tasks, settings and model connections stay in their existing data folder. Full desktop updates require a restart; compatible interface updates below keep the backend running.</p>{status?.previous&&!status.previous.success&&<p role="alert">{status.previous.message}</p>}<div className="action-row"><button disabled={busy||!status} onClick={()=>action('check')}>Check desktop updates</button>{update?.available&&!status?.ready&&<button disabled={busy} onClick={()=>action('download')}>{busy?'Downloading…':'Download verified update'}</button>}{status?.ready&&<button disabled={busy} onClick={()=>action('install')}>Update and restart</button>}</div>{busy&&<p role="status">Working on the update. You can keep this window open.</p>}{message&&<p role="status">{message}</p>}</section>
}
