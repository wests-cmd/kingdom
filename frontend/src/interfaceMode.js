export const INTERFACE_MODE_KEY = 'kingdom.interface-mode'
export const EASY_PAGES = ['Dashboard','Workbench','Tasks','Swarm','Memory','Nodes','Governance','Security','Recovery','Settings']
export const ADVANCED_NAVIGATION = [
 {name:'Operate',items:[['Dashboard','Dashboard'],['Workbench','Agent workbench'],['Preparation','Tools & model lab'],['Tasks','Tasks'],['Automations','Automations'],['Swarm','Swarm'],['Runtime','Runtime']]},
 {name:'Knowledge',items:[['AIMap','Intelligence records'],['SkillMaps','Skill maps & Discord'],['Memory','Memory'],['Routing','Routing'],['Skills','Skills'],['Learning','Learning Center']]},
 {name:'Manage',items:[['Governance','Governance'],['Nodes','Nodes & Cluster'],['Mobile','Devices & Knowledge'],['Security','Security'],['Recovery','Recovery'],['Logs','Logs & Activity'],['Settings','Settings']]}
]
export function navigationForMode(mode) {
 if(mode === 'advanced') return ADVANCED_NAVIGATION
 return [{name:'Your workspace',items:[['Dashboard','Home'],['Workbench','Talk & work'],['Tasks','Tasks'],['Swarm','Swarm'],['Memory','Vault & memory'],['Nodes','Computers'],['Governance','Approvals & permissions'],['Security','Security'],['Recovery','Recovery'],['Settings','Settings']]}]
}
export function loadInterfaceMode(storage) {
 try {return storage.getItem(INTERFACE_MODE_KEY) === 'advanced' ? 'advanced' : 'easy'} catch {return 'easy'}
}
export function saveInterfaceMode(storage,mode) {
 try {storage.setItem(INTERFACE_MODE_KEY,mode === 'advanced' ? 'advanced' : 'easy');return true} catch {return false}
}
export function pageForMode(page,mode) {return mode === 'advanced' || EASY_PAGES.includes(page) ? page : 'Dashboard'}
