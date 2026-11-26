// Presentation geometry only. No operation here mutates membership or authority.
export const CARD_W=218, CARD_H=104, GAP=20, PAGE_SIZE=40, LIMIT=100000
export const clamp=(n,min=0,max=LIMIT)=>Math.max(min,Math.min(max,Math.round(n)))
export const snap=n=>clamp(Math.round(n/16)*16)
export const knightKey=id=>'knight:'+id
export const agentKey=id=>'apprentice:'+id
export const frameKey=id=>'frame:'+id
export const metrics=value=>typeof value==='number'&&Number.isFinite(value)&&value>=0&&value<=100?Math.round(value):null
export function connectionState(c){
 if(c.id==='local')return 'local'
 if(['REVOKED','QUARANTINED','DISCONNECTED'].includes(c.state))return 'problem'
 if(c.state==='CONNECTED'&&c.current)return 'current'
 return 'unknown'
}
export function mapNodes(computers,groups,topology,view){
 const byId=new Map(computers.map(c=>[c.id,c]))
 const owner=new Map()
 for(const group of groups)for(const id of group.members)if(!owner.has(id))owner.set(id,group.id)
 const result=computers.map(c=>({key:knightKey(c.id),id:c.id,kind:'knight',label:c.name,group:owner.get(c.id)||'ungrouped',computer:c}))
 if(view==='teams')for(const n of topology?.nodes||[]){
  if(n.kind!=='apprentice'||!byId.has(n.host))continue
  const c=byId.get(n.host)
  if(c.id!=='local'&&!c.current)continue
  result.push({key:agentKey(n.id),id:n.id,kind:'apprentice',label:n.label,host:n.host,group:owner.get(n.host)||'ungrouped',computer:c})
 }
 return result.sort((a,b)=>a.group.localeCompare(b.group)||((a.kind==='knight'?0:1)-(b.kind==='knight'?0:1))||a.key.localeCompare(b.key))
}
export function pageNodes(nodes,query,page){
 const q=query.trim().toLowerCase(),matches=nodes.filter(n=>!q||(n.label+' '+n.id+' '+n.group).toLowerCase().includes(q))
 const pages=Math.max(1,Math.ceil(matches.length/PAGE_SIZE)),index=clamp(page,0,pages-1)
 return {nodes:matches.slice(index*PAGE_SIZE,(index+1)*PAGE_SIZE),page:index,pages,total:matches.length}
}
export function geometry(nodes,groups,positions){
 const boxes={},frames=[]
 let y=48
 const ordered=[...new Set(nodes.map(n=>n.group))]
 for(const group of ordered){
  const members=nodes.filter(n=>n.group===group),cols=Math.min(4,members.length)
  const start=y
  members.forEach((n,i)=>{const p=positions[n.key];boxes[n.key]={x:p?.x??(32+(i%cols)*(CARD_W+GAP)),y:p?.y??(start+44+Math.floor(i/cols)*(CARD_H+GAP)),w:CARD_W,h:CARD_H}})
  y+=Math.ceil(members.length/cols)*(CARD_H+GAP)+80
  const bounds=members.map(n=>boxes[n.key]),manual=positions[frameKey(group)]
  const x=Math.max(0,Math.min(...bounds.map(p=>p.x))-16),top=Math.max(0,Math.min(...bounds.map(p=>p.y))-36)
  const right=Math.max(...bounds.map(p=>p.x+p.w))+16,bottom=Math.max(...bounds.map(p=>p.y+p.h))+16
  frames.push({key:frameKey(group),id:group,label:groups.find(g=>g.id===group)?.name||'Unassigned',x,y:top,w:Math.max(right-x,manual?.w||0),h:Math.max(bottom-top,manual?.h||0),members:members.map(n=>n.key)})
 }
 return {boxes,frames,width:Math.max(1000,...frames.map(f=>f.x+f.w+24)),height:Math.max(500,...frames.map(f=>f.y+f.h+24))}
}
export function history(initial={}){return {doc:initial,past:[],future:[]}}
export function commit(s,doc){
 if(JSON.stringify(s.doc)===JSON.stringify(doc))return s
 return {doc,past:[...s.past,s.doc].slice(-40),future:[]}
}
export function undo(s){return s.past.length?{doc:s.past.at(-1),past:s.past.slice(0,-1),future:[s.doc,...s.future]}:s}
export function redo(s){return s.future.length?{doc:s.future[0],past:[...s.past,s.doc].slice(-40),future:s.future.slice(1)}:s}
export function moveCard(doc,key,point){return {...doc,[key]:{x:snap(point.x),y:snap(point.y)}}}
export function resizeFrame(doc,frame,w,h){return {...doc,[frame.key]:{x:0,y:0,w:clamp(w,32,20000),h:clamp(h,32,20000)}}}
export function moveFrame(doc,frame,boxes,dx,dy){
 const result={...doc},members=frame.members.map(key=>[key,boxes[key]]).filter(([,p])=>p)
 if(!members.length)return doc
 const minX=Math.min(...members.map(([,p])=>p.x)),minY=Math.min(...members.map(([,p])=>p.y))
 const maxX=Math.max(...members.map(([,p])=>p.x)),maxY=Math.max(...members.map(([,p])=>p.y))
 dx=clamp(dx,-minX,LIMIT-maxX);dy=clamp(dy,-minY,LIMIT-maxY)
 for(const [key,p] of members)result[key]={x:clamp(p.x+dx),y:clamp(p.y+dy)}
 return result
}
