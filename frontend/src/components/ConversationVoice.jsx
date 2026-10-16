import React,{useEffect,useRef,useState} from 'react'

export default function ConversationVoice({onTranscript,answer,disabled=false}) {
 const Recognition=typeof window!=='undefined'&&(window.SpeechRecognition||window.webkitSpeechRecognition)
 const canRead=typeof window!=='undefined'&&Boolean(window.speechSynthesis&&window.SpeechSynthesisUtterance)
 const recognition=useRef(null),generation=useRef(0)
 const [listening,setListening]=useState(false),[draft,setDraft]=useState(''),[notice,setNotice]=useState(''),[reading,setReading]=useState(false)
 useEffect(()=>()=>{generation.current+=1;recognition.current?.abort();if(canRead)window.speechSynthesis.cancel()},[])
 const begin=()=>{
  if(!Recognition||disabled||listening)return
  const serial=++generation.current
  const instance=new Recognition()
  recognition.current=instance
  instance.continuous=false
  instance.interimResults=false
  instance.maxAlternatives=1
  instance.lang=navigator.language||'en-US'
  setDraft('');setNotice('Listening. Stop when finished; review the transcript before using it.')
  instance.onresult=event=>{
   if(serial!==generation.current)return
   const text=Array.from(event.results).filter(result=>result.isFinal).map(result=>result[0]?.transcript||'').join(' ').slice(0,24000)
   setDraft(text);setNotice('Review and edit the transcript. It has not been sent.')
  }
  instance.onerror=event=>{if(serial===generation.current){setListening(false);setNotice(`Voice input unavailable (${event.error||'browser error'}). You can type your message.`)}}
  instance.onend=()=>{if(serial===generation.current)setListening(false)}
  try{instance.start();setListening(true)}catch{setListening(false);setNotice('The browser could not start voice input. Type your message instead.')}
 }
 const discard=()=>{generation.current+=1;recognition.current?.abort();recognition.current=null;setListening(false);setDraft('');setNotice('Voice input discarded. Nothing was sent.')}
 const read=()=>{
  if(!canRead||!answer)return
  window.speechSynthesis.cancel()
  const utterance=new window.SpeechSynthesisUtterance(answer)
  utterance.onend=()=>setReading(false)
  utterance.onerror=()=>{setReading(false);setNotice('Reading stopped or is unavailable. The answer remains available as text.')}
  setReading(true);window.speechSynthesis.speak(utterance)
 }
 return <details style={{minWidth:0,overflowWrap:'anywhere'}}><summary>Optional voice input and read aloud</summary>
 <p className="muted">Voice input starts only when you click Start microphone. Your browser may send audio or answer text to its speech provider; offline operation is not guaranteed. Typing and reading text remain available.</p>
 {!Recognition?<p>Speech recognition is unavailable in this browser. Use the message box.</p>:<div style={{display:'flex',flexWrap:'wrap',gap:8}}>
  <button type="button" disabled={disabled||listening} onClick={begin}>Start microphone</button>
  <button type="button" disabled={!listening} onClick={()=>recognition.current?.stop()}>Stop and review</button>
  <button type="button" disabled={!listening&&!draft} onClick={discard}>Discard recording</button>
 </div>}
 {draft&&<div><label>Review transcript<textarea rows={3} maxLength={24000} value={draft} onChange={event=>setDraft(event.target.value)}/></label><button type="button" disabled={disabled||listening||!draft.trim()} onClick={()=>{onTranscript(draft.trim());setDraft('');setNotice('Reviewed transcript copied to your message. Review the message and click Send when ready.')}}>Use reviewed transcript in message</button></div>}
 <div style={{display:'flex',flexWrap:'wrap',gap:8,marginTop:8}}><button type="button" disabled={!canRead||!answer||reading} onClick={read}>Read saved answer aloud</button><button type="button" disabled={!canRead||!reading} onClick={()=>{window.speechSynthesis.cancel();setReading(false)}}>Stop reading</button></div>
 {!canRead&&<p>Read aloud is unavailable in this browser.</p>}
 {notice&&<p role="status">{notice}</p>}
 </details>
}
