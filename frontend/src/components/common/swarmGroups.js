export function memberChoices(computers, groups, targetId, selected=[]) {
 const owners=new Map(groups.flatMap(g=>g.members.map(id=>[id,g])))
 return computers.map(c=>({...c,other:owners.get(c.id)?.id!==targetId?owners.get(c.id):null,checked:selected.includes(c.id)}))
  .sort((a,b)=>Number(!!a.other)-Number(!!b.other)||a.name.localeCompare(b.name))
}
export function splitSizes(size, count) {
 if(!Number.isInteger(size)||!Number.isInteger(count)||count<2||count>size) return []
 return Array.from({length:count},(_,i)=>Math.floor(size/count)+(i<size%count?1:0))
}
export function swarmCount(computers) {
 return `One Kingdom · ${computers.length} ${computers.length===1?'Knight':'Knights'}`
}
