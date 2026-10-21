import React, { useState, useEffect } from 'react'
import { api } from '../../api'
import {navigationForMode} from '../../interfaceMode'
export default function Sidebar({currentPage,setCurrentPage,interfaceMode='easy',collapsed=false,toggle}) {
 const groups=navigationForMode(interfaceMode)
 const [version,setVersion] = useState('Loading…')
 useEffect(() => {api.getSystemVersion().then(data => setVersion(data.version ? `v${data.version}` : 'Unavailable')).catch(() => setVersion('Unavailable'))},[])
 return <aside className={`sidebar ${collapsed?'is-collapsed':''}`}><button className="sidebar-toggle" aria-label={collapsed?'Expand sidebar':'Collapse sidebar'} aria-expanded={!collapsed} onClick={toggle}>{collapsed?'☰':'← Hide menu'}</button><div className="sidebar-logo"><img className="brand-mark" src="/branding/kingdom-icon.png" alt="Kingdom crowned K" />{!collapsed&&'KINGDOM'}</div><nav hidden={collapsed} aria-label="Main navigation">{groups.map(group => <div className="nav-group" key={group.name}><p className="nav-group-title">{group.name}</p><ul className="sidebar-nav">{group.items.map(([id,label]) => <li key={id}><button className={`sidebar-item ${currentPage === id ? 'active' : ''}`} aria-current={currentPage === id ? 'page' : undefined} onClick={() => setCurrentPage(id)}>{label}</button></li>)}</ul></div>)}</nav><div className="sidebar-footer" hidden={collapsed}><span>Local control</span><span>{version}</span></div></aside>
}


