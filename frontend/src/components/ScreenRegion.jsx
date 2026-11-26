import React,{useEffect,useRef,useState} from 'react'

export default function ScreenRegion({onRegion,disabled=false}){
 const canvas=useRef(null),source=useRef(null),stream=useRef(null),generation=useRef(0)
 const [size,setSize]=useState(null),[box,setBox]=useState({x:0,y:0,w:1,h:1}),[anchor,setAnchor]=useState(null),[notice,setNotice]=useState(''),[crop,setCrop]=useState('')
 useEffect(()=>()=>{generation.current++;stream.current?.getTracks().forEach(t=>t.stop())},[])
 function show(image,w,h){
   const ratio=Math.min(1,1600/Math.max(w,h))
   const snapshot=document.createElement('canvas');snapshot.width=Math.max(1,Math.round(w*ratio));snapshot.height=Math.max(1,Math.round(h*ratio))
   snapshot.getContext('2d').drawImage(image,0,0,snapshot.width,snapshot.height)
   source.current=snapshot;setSize({w:snapshot.width,h:snapshot.height});setBox({x:0,y:0,w:snapshot.width,h:snapshot.height});setAnchor(null);setCrop('');onRegion(null);setNotice('Choose two corners or enter the exact rectangle. Review the crop before attaching.')
 }
 useEffect(()=>{if(!size||!canvas.current||!source.current)return
   const ctx=canvas.current.getContext('2d');ctx.drawImage(source.current,0,0)
   ctx.strokeStyle='#ff5252';ctx.lineWidth=3;ctx.strokeRect(box.x,box.y,box.w,box.h)
 },[size,box])
 async function file(e){
   const picked=e.target.files?.[0];e.target.value='';if(!picked)return
   if(picked.size>10000000||!['image/png','image/jpeg','image/webp'].includes(picked.type)){setNotice('Choose a PNG, JPEG or WebP up to 10 MB.');return}
   const serial=++generation.current
   try{const img=await createImageBitmap(picked);if(serial===generation.current){if(img.width*img.height>40000000)throw Error('Image too large');show(img,img.width,img.height)}img.close()}catch{setNotice('Could not open the selected image.')}
 }
 async function capture(){
   if(!navigator.mediaDevices?.getDisplayMedia){setNotice('Screen capture is unavailable here. Choose a screenshot file instead.');return}
   const serial=++generation.current;let media
   try{
     media=await navigator.mediaDevices.getDisplayMedia({video:true,audio:false});stream.current=media
     if(serial!==generation.current)return
     const video=document.createElement('video');video.srcObject=media;video.muted=true;await video.play()
     if(serial===generation.current&&video.videoWidth&&video.videoHeight)show(video,video.videoWidth,video.videoHeight)
     video.pause();video.srcObject=null
   }catch{if(serial===generation.current)setNotice('Capture unavailable or declined. Nothing was sent.')}
   finally{media?.getTracks().forEach(t=>t.stop());if(stream.current===media)stream.current=null}
 }
 function point(e){
   if(disabled||!size)return
   const rect=e.currentTarget.getBoundingClientRect(),x=Math.min(size.w-1,Math.max(0,Math.round((e.clientX-rect.left)*size.w/rect.width))),y=Math.min(size.h-1,Math.max(0,Math.round((e.clientY-rect.top)*size.h/rect.height)))
   if(!anchor){setAnchor({x,y});setNotice('Choose the opposite corner.');return}
   setBox({x:Math.min(x,anchor.x),y:Math.min(y,anchor.y),w:Math.max(1,Math.abs(x-anchor.x)),h:Math.max(1,Math.abs(y-anchor.y))});setAnchor(null);setCrop('');onRegion(null)
 }
 function preview(){
   if(!source.current||!size||!Object.values(box).every(Number.isInteger)||box.x<0||box.y<0||box.w<1||box.h<1||box.x+box.w>size.w||box.y+box.h>size.h){setNotice('Rectangle must fit inside the image.');return}
   const output=document.createElement('canvas')
   for(const max of [640,480,320,240,160]){
     const scale=Math.min(1,max/Math.max(box.w,box.h));output.width=Math.max(1,Math.round(box.w*scale));output.height=Math.max(1,Math.round(box.h*scale))
     output.getContext('2d').drawImage(source.current,box.x,box.y,box.w,box.h,0,0,output.width,output.height)
     const url=output.toDataURL('image/jpeg',0.72)
     if(url.length<=18000){setCrop(url);setNotice('Review this compressed crop. Only the crop will be sent to your selected model after Send.');return}
   }
   setNotice('Crop is too detailed for this budget; choose a smaller region.')
 }
 return <details><summary>Point at a screen region</summary>
 <p>Capture only on request, or choose an existing screenshot. Red outline marks your selected region; it is not an automatic click instruction. Select a vision model before sending.</p>
 <input type="file" accept="image/png,image/jpeg,image/webp" disabled={disabled} onChange={file}/>
 <button type="button" disabled={disabled} onClick={capture}>Choose screen or window</button>
 {size&&<><canvas ref={canvas} width={size.w} height={size.h} onClick={point} aria-label="Select two corners on the screenshot" style={{width:'100%',height:'auto',cursor:'crosshair'}}/>
 <div style={{display:'flex',flexWrap:'wrap',gap:6}}>{Object.keys(box).map(k=><label key={k}>{k}<input type="number" min={k==='w'||k==='h'?1:0} value={box[k]} disabled={disabled} onChange={e=>{setBox({...box,[k]:Number(e.target.value)});setCrop('');onRegion(null)}} style={{width:85}}/></label>)}</div>
 <button type="button" disabled={disabled} onClick={preview}>Preview marked region</button></>}
 {crop&&<><img src={crop} alt="Reviewed region crop" style={{maxWidth:'100%'}}/><button type="button" disabled={disabled} onClick={()=>{onRegion(crop);setNotice('Crop attached. Review your question and click Send.')}}>Attach reviewed crop</button></>}
 <button type="button" disabled={disabled} onClick={()=>{generation.current++;stream.current?.getTracks().forEach(t=>t.stop());source.current=null;setSize(null);setCrop('');onRegion(null);setNotice('Region discarded.')}}>Discard region</button>
 {notice&&<p role="status">{notice}</p>}</details>
}
