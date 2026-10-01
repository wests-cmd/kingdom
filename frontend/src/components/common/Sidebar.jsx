import React, { useState, useEffect } from 'react'
import { api } from '../../api'
const groups = [
 {name:'Operate',items:[['Dashboard','Dashboard'],['Tasks','Tasks'],['Swarm','Swarm'],['Runtime','Runtime']]},
 {name:'Knowledge',items:[['AIMap','Intelligence records'],['SkillMaps','Skill maps & Discord'],['Memory','Memory'],['Routing','Routing'],['Skills','Skills'],['Learning','Learning Center']]},
 {name:'Manage',items:[['Governance','Governance'],['Nodes','Nodes & Cluster'],['Mobile','Devices & Knowledge'],['Security','Security'],['Logs','Logs & Activity']]}
]
export default function Sidebar({currentPage,setCurrentPage}) {
 const [version,setVersion] = useState('Loading…')
 useEffect(() => {api.getSystemVersion().then(data => setVersion(data.version ? `v${data.version}` : 'Unavailable')).catch(() => setVersion('Unavailable'))},[])
 return <aside className="sidebar"><div className="sidebar-logo"><svg className="brand-mark" viewBox="0 0 28 32" aria-hidden="true"><path d="M3 3h22v17L14 29 3 20Z" fill="none" stroke="currentColor" strokeWidth="1.5"/><path d="M9 9v12m1-6 9-6m-9 6 9 6" fill="none" stroke="currentColor" strokeWidth="1.5"/></svg>KINGDOM</div><nav aria-label="Main navigation">{groups.map(group => <div className="nav-group" key={group.name}><p className="nav-group-title">{group.name}</p><ul className="sidebar-nav">{group.items.map(([id,label]) => <li key={id}><button className={`sidebar-item ${currentPage === id ? 'active' : ''}`} aria-current={currentPage === id ? 'page' : undefined} onClick={() => setCurrentPage(id)}>{label}</button></li>)}</ul></div>)}</nav><div className="sidebar-footer"><span>Local control</span><span>{version}</span></div></aside>
}
