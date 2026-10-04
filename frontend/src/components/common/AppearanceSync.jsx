import React,{useEffect,useRef,useState} from 'react'
import api from '../../api'
import {DEFAULT_APPEARANCE,sanitizeAppearance} from '../../appearance'
import {useAppearance} from './AppearanceProvider'

export default function AppearanceSync(){
 const {settings,update}=useAppearance()
 const current=useRef(settings),initial=useRef(JSON.stringify(settings)),lastSaved=useRef(null)
 const writing=useRef(false),pending=useRef(null),mounted=useRef(true)
 const [ready,setReady]=useState(false),[status,setStatus]=useState('Loading saved accessibility preferences…')
 current.current=settings
 useEffect(()=>{
  let active=true
  api.get('/preferences/accessibility').then(({data})=>{
   if(!active)return
   if(data.preferences&&initial.current===JSON.stringify(DEFAULT_APPEARANCE)&&JSON.stringify(current.current)===initial.current){
    const saved=sanitizeAppearance(data.preferences)
    lastSaved.current=JSON.stringify(saved);update(saved)
   }
   setReady(true)
  }).catch(()=>{if(active)setStatus('Preferences remain on this device. Kingdom preference sync is unavailable.')})
  mounted.current=true
  return()=>{active=false;mounted.current=false;pending.current=null}
 },[])
 useEffect(()=>{
  if(!ready)return
  const serialized=JSON.stringify(settings)
  if(serialized===lastSaved.current){setStatus('Preferences saved for this Kingdom owner.');return}
  async function flush(){
   if(writing.current)return
   writing.current=true
   try{
    while(pending.current&&mounted.current){
     const next=pending.current;pending.current=null
     try{
      await api.put('/preferences/accessibility',next)
      lastSaved.current=JSON.stringify(next)
      if(mounted.current)setStatus('Preferences saved for this Kingdom owner.')
     }catch{
      if(mounted.current)setStatus('Preferences remain on this device. Kingdom could not save this change.')
     }
    }
   }finally{writing.current=false}
  }
  const timer=setTimeout(()=>{
   pending.current=settings;flush()
  },500)
  return()=>clearTimeout(timer)
 },[settings,ready])
 return <p className="preference-sync-status muted" role="status">{status}</p>
}
