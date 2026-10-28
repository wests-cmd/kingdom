export const palette=['#38bdf8','#4ade80','#fbbf24','#c084fc','#2dd4bf','#fb7185']
export const W=1000,H=540
export function graphLayout(computers,groups) {
 const visible=new Set(computers.map(c=>c.id))
 const teams=groups.map(g=>({...g,members:g.members.filter(id=>visible.has(id))})).filter(g=>g.members.length)
 const grouped=new Set(teams.flatMap(g=>g.members))
 const buckets=[...teams,{id:'ungrouped',name:'Ungrouped',members:computers.filter(c=>!grouped.has(c.id)).map(c=>c.id)}].filter(g=>g.members.length)
 const points={},regions=[]
 const cols=Math.ceil(Math.sqrt(buckets.length||1)),rows=Math.ceil(buckets.length/cols)||1
 buckets.forEach((g,i)=>{
  const width=W/cols,height=(H-40)/rows,cx=width*(i%cols+.5),cy=40+height*(Math.floor(i/cols)+.5)
  const radius=Math.min(width*.32,height*.3,130),color=g.id==='ungrouped'?'#94a3b8':palette[groups.findIndex(t=>t.id===g.id)%palette.length]
  regions.push({...g,cx,cy,rx:width*.46,ry:height*.44,color})
  g.members.forEach((id,j)=>{const angle=2*Math.PI*j/g.members.length-Math.PI/2;points[id]={x:cx+(g.members.length>1?radius*Math.cos(angle):0),y:cy+(g.members.length>1?radius*Math.sin(angle):0),group:g.id,color}})
 })
 return {points,regions}
}
// Only the node intentionally released by the user can propose a membership
// change. Layout motion must never merge arbitrary neighboring groups.
export function releaseIntent(id,point,points,groups,startPoint=points[id]) {
 const origin=groups.find(g=>g.members.includes(id))
 const nearest=Object.entries(points).filter(([other])=>other!==id).map(([other,p])=>({id:other,d:Math.hypot(point.x-p.x,point.y-p.y)})).sort((a,b)=>a.d-b.d)[0]
 if(nearest?.d<76){
  const target=groups.find(g=>g.members.includes(nearest.id))
  if(origin&&target?.id===origin.id)return null
  if(origin&&target)return {kind:'combine',groups:[origin.id,target.id]}
  return target?{kind:'add',group:target.id,members:[id]}:origin?{kind:'add',group:origin.id,members:[nearest.id]}:{kind:'create',members:[id,nearest.id]}
 }
 const others=origin?.members.filter(other=>other!==id&&points[other]).map(other=>points[other])||[]
 if(others.length){const x=others.reduce((sum,p)=>sum+p.x,0)/others.length,y=others.reduce((sum,p)=>sum+p.y,0)/others.length
  const initialDistance=startPoint?Math.hypot(startPoint.x-x,startPoint.y-y):0
  if(Math.hypot(point.x-x,point.y-y)>Math.max(220,initialDistance+100))return {kind:'remove',members:[id]}
 }
 return null
}
