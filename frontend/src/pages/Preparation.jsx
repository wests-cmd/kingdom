import React, {useState} from 'react'
import ToolWorkshop from '../components/ToolWorkshop'
import ModelLab from '../components/ModelLab'

export default function Preparation(){
 const [mode,setMode]=useState('tools')
 return <div><h1>Preparation</h1><p>Add tested tools and prepare model candidates while keeping clear records of what actually ran. Existing execution permissions and owner command approvals apply.</p>
  <div role="group" aria-label="Preparation area"><button aria-pressed={mode==='tools'} onClick={()=>setMode('tools')}>Build a tool</button><button aria-pressed={mode==='models'} onClick={()=>setMode('models')}>Prepare a model</button></div>
  {mode==='tools'?<ToolWorkshop/>:<ModelLab/>}
 </div>
}
