import React,{useEffect,useMemo,useState} from 'react'
import useLiveData from '../hooks/useLiveData'
import {notificationItems} from './common/taskVisibility'

export default function NotificationCenter({onNavigate}) {
 const feed=useLiveData('/events?limit=100',10000)
 const items=useMemo(()=>notificationItems(feed.data),[feed.data])
 const [seen,setSeen]=useState(null)
 const [open,setOpen]=useState(false)
 // Initial history is not a burst of new alerts on launch.
 useEffect(()=>{
  if(items!==null && seen===null)setSeen(new Set(items.map(item=>item.id)))
 },[items,seen])
 const unreviewed=items&&seen ? items.filter(item=>!seen.has(item.id)) : []
 const important=unreviewed.filter(item=>item.important).length
 const label=important>0?`${important} new important notice${important===1?'':'s'}`:
  unreviewed.length>0?`${unreviewed.length} new notice${unreviewed.length===1?'':'s'}`:'No new notices'
 return <section className="panel notification-center" aria-label="Kingdom notifications">
  <div className="section-heading"><div><h2>Notifications</h2>
    <p className="muted">In-app activity alerts from Kingdom events. Approval requests still require review in Governance.</p></div>
    <div className="action-row">
      <span className="status-chip" role="status">{items===null?'Activity unavailable':feed.error?'Activity update failed':label}</span>
      <button type="button" aria-expanded={open} onClick={()=>setOpen(v=>!v)}>{open?'Hide notices':'View notices'}</button>
    </div>
  </div>
  {feed.error && <p role="alert">Activity could not refresh. Notifications may be stale or missing. Review actual tasks and approvals.</p>}
  {open && <>
    <p className="muted">Notices are marked viewed only while this Home page is open. This is not a mobile push or system notification service.</p>
    <div className="action-row">
      <button type="button" onClick={feed.refresh}>Refresh activity</button>
      <button type="button" disabled={!items?.length} onClick={()=>setSeen(new Set(items.map(item=>item.id)))}>
        Mark notices viewed here
      </button>
    </div>
    {items===null?<p role="status">Loading activity…</p>:items.length===0?
      <p>No matching recent events were recorded.</p>:
      <ol className="notification-list">{items.map(item=>
       <li key={item.id} className={seen?.has(item.id)?'':'notice-new'}>
         <div className="home-task-title"><strong>{item.title}</strong>
           <small>{item.when}</small></div>
         <p>{item.explanation}</p>
         <button type="button" onClick={()=>onNavigate?.(item.kind==='governance.approval_required'?'Governance':'Tasks')}>
           {item.kind==='governance.approval_required'?'Review approvals':'Review tasks'}
         </button>
       </li>)}</ol>}
  </>}
 </section>
}
