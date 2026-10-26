import React,{useEffect,useMemo,useRef,useState} from 'react'
import {graphLayout,releaseIntent,W,H} from './common/proximityGraph'

export default function KnightNetworkGraph({computers,groups,busy,readOnly,onIntent,onMenu}) {
 const svg=useRef(null),drag=useRef(null)
 const [positions,setPositions]=useState({}),[moving,setMoving]=useState(null),[zoom,setZoom]=useState(1)
 const layout=useMemo(()=>graphLayout(computers,groups),[computers.map(c=>c.id).join('|'),JSON.stringify(groups)])
 useEffect(()=>{setPositions({})},[layout])
 const points=Object.fromEntries(Object.entries(layout.points).map(([id,p])=>[id,{...p,...positions[id]}]))
 const point=e=>{const p=svg.current.createSVGPoint();p.x=e.clientX;p.y=e.clientY;return p.matrixTransform(svg.current.getScreenCTM().inverse())}
 const menu=(e,target)=>onMenu(e,target)
 const start=(e,c)=>{if(e.button!==0||busy)return;e.preventDefault();const p=point(e);drag.current={id:c.id,start:p,offset:{x:points[c.id].x-p.x,y:points[c.id].y-p.y},moved:false};svg.current.setPointerCapture(e.pointerId);setMoving(c.id)}
 const move=e=>{const d=drag.current;if(!d)return;const p=point(e);d.moved ||= Math.hypot(p.x-d.start.x,p.y-d.start.y)>5;const next={x:Math.max(35,Math.min(W-35,p.x+d.offset.x)),y:Math.max(55,Math.min(H-35,p.y+d.offset.y))};d.last=next;setPositions(old=>({...old,[d.id]:next}))}
 const end=e=>{const d=drag.current;if(!d)return;drag.current=null;setMoving(null);if(svg.current.hasPointerCapture(e.pointerId))svg.current.releasePointerCapture(e.pointerId)
  if(!d.moved){menu(e,computers.find(c=>c.id===d.id));return}
  if(!readOnly){const intent=releaseIntent(d.id,d.last,points,groups);if(intent)onIntent(intent)}
 }
 const keyboard=(e,target)=>{if(e.key==='Enter'||e.key===' '||e.key==='ContextMenu'||(e.shiftKey&&e.key==='F10')){e.preventDefault();const r=e.currentTarget.getBoundingClientRect();menu({preventDefault(){},stopPropagation(){},clientX:r.left,clientY:r.bottom},target)}}
 const local=computers.find(c=>c.id==='local')
 return <section className="knight-network" aria-label="Live Knight network graph">
  <header><div><h3>Knight network</h3><p>Drag Knights together to propose a group. Pull one away to remove it. Right-click a Knight or group for actions.</p></div><div className="action-row"><button onClick={()=>setZoom(z=>Math.max(.6,z-.2))} aria-label="Zoom out">−</button><button onClick={()=>{setZoom(1);setPositions({})}}>Fit / reset</button><button onClick={()=>setZoom(z=>Math.min(2,z+.2))} aria-label="Zoom in">+</button></div></header>
  <svg ref={svg} viewBox={`${W*(1-1/zoom)/2} ${H*(1-1/zoom)/2} ${W/zoom} ${H/zoom}`} role="group" aria-label="Interactive network of actual Kingdom Knights" onPointerMove={move} onPointerUp={end} onPointerCancel={()=>{drag.current=null;setMoving(null)}} onContextMenu={e=>menu(e,null)}>
   {layout.regions.map(g=><g key={g.id} role="button" tabIndex={0} aria-label={`${g.name} group actions`} onKeyDown={e=>keyboard(e,g.id==='ungrouped'?null:groups.find(t=>t.id===g.id))} onContextMenu={e=>menu(e,g.id==='ungrouped'?null:groups.find(t=>t.id===g.id))}>
    <ellipse cx={g.cx} cy={g.cy} rx={g.rx} ry={g.ry} fill={g.color} fillOpacity=".045" stroke={g.color} strokeOpacity=".5" strokeDasharray={g.id==='ungrouped'?'5 5':undefined}/>
    <text x={g.cx} y={g.cy-g.ry+23} textAnchor="middle" fill={g.color} className="network-team-label">{g.name}</text>
   </g>)}
   {local&&computers.filter(c=>c.id!==local.id).map(c=><line key={c.id} x1={points.local?.x} y1={points.local?.y} x2={points[c.id]?.x} y2={points[c.id]?.y} stroke={c.state==='CONNECTED'?'#4ade80':'#94a3b8'} strokeOpacity=".5" strokeWidth="2" strokeDasharray={c.state==='CONNECTED'?undefined:'6 6'}/>)}
   {computers.map(c=>{const p=points[c.id];if(!p)return null;const online=c.id==='local'||c.state==='CONNECTED';const team=groups.find(g=>g.members.includes(c.id));return <g key={c.id} transform={`translate(${p.x},${p.y})`} className={`network-node ${moving===c.id?'dragging':''}`} role="button" tabIndex={0} aria-label={`${c.name}, ${c.state}${team?`, group ${team.name}`:''}. Open Knight actions`} onPointerDown={e=>start(e,c)} onKeyDown={e=>keyboard(e,c)} onContextMenu={e=>menu(e,c)}>
    <title>{c.name} · {c.state}{team?` · ${team.name}`:''}</title><circle r="23" fill="#0f172a" stroke={p.color} strokeWidth="3" strokeDasharray={online?undefined:'4 4'}/><circle r="7" fill={online?'#4ade80':'#94a3b8'}/>
    <text y="42" textAnchor="middle" className="network-name">{c.name.length>32?c.name.slice(0,29)+'…':c.name}</text><text y="59" textAnchor="middle" className="network-state">{c.state}{team?.captain===c.id?' · Team leader':''}</text>
   </g>})}
  </svg>
  <p className="network-legend">● Connected　◌ Disconnected / unknown · Lines show this Knight’s approved peer relationships, not physical wiring or proof of work. Colors show saved groups. Layout changes do not grant permissions.</p>
 </section>
}
