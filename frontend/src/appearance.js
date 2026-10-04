export const APPEARANCE_KEY = 'kingdom.appearance.v1'
export const PALETTES = Object.freeze([
  {id:'royal',name:'Royal purple',accent:'#b69aff',description:'Purple with black accents'},
  {id:'ocean',name:'Deep blue',accent:'#80bfff',description:'Cool blue and charcoal'},
  {id:'jade',name:'Jade',accent:'#7ed9b2',description:'Green and dark stone'},
  {id:'ember',name:'Copper',accent:'#efa784',description:'Warm copper and charcoal'},
  {id:'gold',name:'Antique gold',accent:'#dfc17d',description:'Gold and black'}
])
export const DEFAULT_APPEARANCE = Object.freeze({mode:'dark',palette:'royal',accent:'#b69aff',density:'comfortable',scale:100,motion:'system',atmosphere:10,contrast:'standard',targets:'standard',focus:'standard',pointer:'standard',reading:'standard',distraction:'standard'})
const member = (value,choices,fallback) => choices.includes(value) ? value : fallback
export function sanitizeAppearance(value) {
  const data = value && typeof value === 'object' && !Array.isArray(value) ? value : {}
  return {
    mode:member(data.mode,['dark','light','system'],'dark'),
    palette:member(data.palette,PALETTES.map(p=>p.id),'royal'),
    accent:typeof data.accent === 'string' && /^#[0-9a-f]{6}$/i.test(data.accent) ? data.accent.toLowerCase() : DEFAULT_APPEARANCE.accent,
    density:member(data.density,['comfortable','compact'],'comfortable'),
    scale:member(data.scale,[90,100,110,125,150,175,200],100),
    motion:member(data.motion,['system','reduced'],'system'),
    atmosphere:member(data.atmosphere,[0,5,10,15,20],10),
    contrast:member(data.contrast,['standard','high'],'standard'),
    targets:member(data.targets,['standard','large'],'standard'),
    focus:member(data.focus,['standard','strong'],'standard'),
    pointer:member(data.pointer,['standard','large'],'standard'),
    reading:member(data.reading,['standard','spacious'],'standard'),
    distraction:member(data.distraction,['standard','quiet'],'standard')
  }
}
export function loadAppearance(storage) {
  try {return sanitizeAppearance(JSON.parse(storage.getItem(APPEARANCE_KEY)))} catch {return {...DEFAULT_APPEARANCE}}
}
export function saveAppearance(storage,value) {
  try {storage.setItem(APPEARANCE_KEY,JSON.stringify(sanitizeAppearance(value)));return true} catch {return false}
}
function luminance(hex) {
  const channels = hex.slice(1).match(/../g).map(v=>parseInt(v,16)/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4)
  return channels[0]*.2126+channels[1]*.7152+channels[2]*.0722
}
export function contrastRatio(first,second) {
  const values=[luminance(first),luminance(second)].sort((a,b)=>b-a)
  return (values[0]+.05)/(values[1]+.05)
}
export function readableAccent(accent,background) {
  const target=luminance(background)>.5?0:255
  const values=accent.slice(1).match(/../g).map(v=>parseInt(v,16))
  for(let step=0;step<=20;step++) {
    const color='#'+values.map(v=>Math.round(v+(target-v)*step/20).toString(16).padStart(2,'0')).join('')
    if(contrastRatio(color,background)>=4.5)return color
  }
  return target?'#ffffff':'#000000'
}
export function appearanceVariables(value,systemDark=true) {
  const settings=sanitizeAppearance(value)
  const dark=settings.mode==='dark'||(settings.mode==='system'&&systemDark)
  const colors=dark?{
    '--bg-dark':'#100e15','--surface-dark':'#1b1822','--sidebar-bg':'#141119','--input-bg':'#141119',
    '--surface-border':'#39323f','--text-main':'#f4effa','--text-muted':'#b9b0c6','--button-bg':'#27222f',
    '--accent-red':'#ef9b9b','--accent-green':'#8ed6ac','--accent-orange':'#e7c083'
  }:{
    '--bg-dark':'#f5f2f8','--surface-dark':'#ffffff','--sidebar-bg':'#ece6f2','--input-bg':'#faf8fc',
    '--surface-border':'#d2c8dd','--text-main':'#241b31','--text-muted':'#62546f','--button-bg':'#ede7f4',
    '--accent-red':'#a52c3c','--accent-green':'#236b43','--accent-orange':'#835608'
  }
  const readable=readableAccent(settings.accent,dark?colors['--button-bg']:colors['--sidebar-bg'])
  if(settings.contrast==='high') {
    for(const key of ['--bg-dark','--surface-dark','--sidebar-bg','--input-bg','--button-bg'])colors[key]=dark?'#000000':'#ffffff'
    for(const key of ['--text-main','--text-muted','--surface-border'])colors[key]=dark?'#ffffff':'#000000'
    colors['--accent-green']=dark?'#8effb2':'#005523'
    colors['--accent-red']=dark?'#ffb3bd':'#990022'
    colors['--accent-orange']=dark?'#ffe080':'#634500'
  }
  return {dark,variables:{...colors,'--accent-primary':settings.accent,'--accent-readable':readable,
    '--accent-on-primary':contrastRatio(settings.accent,'#000000')>=contrastRatio(settings.accent,'#ffffff')?'#000000':'#ffffff',
    '--display-scale':String(settings.scale/100),'--atmosphere-opacity':String(settings.contrast==='high'||settings.distraction==='quiet'?0:settings.atmosphere/100)}}
}
