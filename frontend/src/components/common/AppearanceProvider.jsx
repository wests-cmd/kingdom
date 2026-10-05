import React,{createContext,useContext,useEffect,useState} from 'react'
import {APPEARANCE_KEY,DEFAULT_APPEARANCE,appearanceVariables,loadAppearance,sanitizeAppearance,saveAppearance} from '../../appearance'

const AppearanceContext=createContext(null)
function storedAppearance() {try{return loadAppearance(window.localStorage)}catch{return {...DEFAULT_APPEARANCE}}}
export function applyAppearance(settings) {
  const {dark,variables}=appearanceVariables(settings,window.matchMedia('(prefers-color-scheme: dark)').matches)
  const root=document.documentElement
  for(const [key,value] of Object.entries(variables))root.style.setProperty(key,value)
  root.dataset.theme=dark?'dark':'light'
  root.dataset.density=settings.density
  root.dataset.motion=settings.motion
  for(const key of ['contrast','targets','focus','pointer','reading','distraction'])root.dataset[key]=settings[key]
  root.dataset.largeDisplay=settings.scale>125?'true':'false'
  root.style.colorScheme=dark?'dark':'light'
}
export function initializeAppearance() {applyAppearance(storedAppearance())}
export function AppearanceProvider({children}) {
  const [settings,setSettings]=useState(storedAppearance)
  const [saved,setSaved]=useState(true)
  useEffect(()=>{
    applyAppearance(settings)
    const media=window.matchMedia('(prefers-color-scheme: dark)')
    const change=()=>applyAppearance(settings)
    media.addEventListener('change',change)
    return()=>media.removeEventListener('change',change)
  },[settings])
  useEffect(()=>{
    const change=event=>{if(event.key===APPEARANCE_KEY)setSettings(storedAppearance())}
    window.addEventListener('storage',change)
    return()=>window.removeEventListener('storage',change)
  },[])
  const update=changes=>{
    const value=sanitizeAppearance({...settings,...changes})
    setSettings(value)
    try{setSaved(saveAppearance(window.localStorage,value))}catch{setSaved(false)}
  }
  return <AppearanceContext.Provider value={{settings,update,saved,reset:()=>update(DEFAULT_APPEARANCE)}}>{children}</AppearanceContext.Provider>
}
export function useAppearance(){return useContext(AppearanceContext)}
