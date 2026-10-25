import React, { useState, useEffect } from 'react'
import client, { api } from '../../api'
import {navigationForMode} from '../../interfaceMode'
export default function Sidebar({currentPage,setCurrentPage,interfaceMode='easy',collapsed=false,toggle}) {
 const groups=navigationForMode(interfaceMode)
 const [version,setVersion] = useState('Loading…')
 const [build,setBuild] = useState(null)
 useEffect(() => {api.getSystemVersion().then(data => setVersion(data.version ? `v${data.version}` : 'Unavailable')).catch(() => setVersion('Unavailable'))},[])
 useEffect(()=>{client.get('/hierarchy/releases').then(response=>{const local=response.data.knights?.find(row=>row.id==='local');setBuild(local?.installed?.revision||null)}).catch(()=>setBuild(null))},[])
 return <aside className={`sidebar ${collapsed?'is-collapsed':''}`}><button className="sidebar-toggle" aria-label={collapsed?'Expand sidebar':'Collapse sidebar'} aria-expanded={!collapsed} onClick={toggle}>{collapsed?'☰':'← Hide menu'}</button><div className="sidebar-logo"><img className="brand-mark" src="/branding/kingdom-icon.png" alt="Kingdom crowned K" />{!collapsed&&'KINGDOM'}</div><nav hidden={collapsed} aria-label="Main navigation">{groups.map(group => <div className="nav-group" key={group.name}><p className="nav-group-title">{group.name}</p><ul className="sidebar-nav">{group.items.map(([id,label]) => <li key={id}><button className={`sidebar-item ${currentPage === id ? 'active' : ''}`} aria-current={currentPage === id ? 'page' : undefined} onClick={() => setCurrentPage(id)}>{label}</button></li>)}</ul></div>)}</nav><div className="sidebar-footer" hidden={collapsed}><span>Local control</span><span>{version}</span><small title={build?`Backend source revision ${build}`:"Exact backend build unavailable"}>Build {build?build.slice(0,7):"unverified"}</small></div></aside>
}


