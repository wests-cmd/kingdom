export const COORDINATION_PAGE_SIZE = 20

export function coordinationPage(nodes, page) {
 const pages = Math.max(1, Math.ceil(nodes.length / COORDINATION_PAGE_SIZE))
 const current = Math.min(Math.max(0, page), pages - 1)
 return {page:current, pages, nodes:nodes.slice(current * COORDINATION_PAGE_SIZE, (current + 1) * COORDINATION_PAGE_SIZE)}
}

export function coordinationDepths(nodes, parents) {
 const depths = new Map([['kingdom', 0]])
 for (const node of nodes) {
  let current = node.id, chain = [], seen = new Set()
  while (current && !depths.has(current) && !seen.has(current)) {
   seen.add(current); chain.push(current); current = parents[current]
  }
  let depth = depths.get(current) ?? 0
  for (const id of chain.reverse()) depths.set(id, ++depth)
 }
 return depths
}

export function coordinatorOptions(nodes, editing, query, selected, limit=50) {
 const text = query.trim().toLocaleLowerCase()
 const matches = nodes.filter(n => n.id !== editing && (!text || `${n.label} ${n.id}`.toLocaleLowerCase().includes(text)))
 const shown = matches.slice(0, limit)
 const current = nodes.find(n => n.id === selected && n.id !== editing)
 if (current && !shown.some(n => n.id === current.id)) shown.unshift(current)
 return {nodes:shown, total:matches.length}
}
