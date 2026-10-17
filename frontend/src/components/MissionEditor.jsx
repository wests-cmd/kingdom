import React from 'react'
import useLiveData from '../hooks/useLiveData'
import {deviceLabel} from './common/presentation'
import {canChooseComputer,eligibleMissionComputers,setStepComputer} from './missionComputers'
export default function MissionEditor({value,onChange}){
 const computers=useLiveData('/nodes',5000)
 const choices=step=>eligibleMissionComputers(computers.data,step.kind)
 let plan
 try{plan=JSON.parse(value)}catch{return <p>Check the advanced plan format to restore the guided editor.</p>}
 const update=next=>onChange(JSON.stringify(next,null,2))
 const field=(name,text)=>update({...plan,[name]:text})
 const stepField=(index,name,text)=>update({...plan,steps:plan.steps.map((step,i)=>i===index?{...step,[name]:text}:step)})
 const computerField=(index,id)=>update({...plan,steps:plan.steps.map((step,i)=>i===index?setStepComputer(step,id):step)})
 const remove=index=>{const id=plan.steps[index].id;if(plan.steps.some(step=>step.depends_on.includes(id)||step.input_from===id)){window.alert('Remove or change the steps that depend on this one first.');return}update({...plan,steps:plan.steps.filter((_,i)=>i!==index)})}
 return <div className="page-stack"><label>Mission name<input value={plan.title} onChange={e=>field('title',e.target.value)}/></label><label>Your objective<textarea rows={4} value={plan.objective} onChange={e=>field('objective',e.target.value)}/></label>
 <label>What you will receive (one per line)<textarea rows={4} value={plan.deliverables.join('\n')} onChange={e=>field('deliverables',e.target.value.split('\n'))}/></label>
 <label>Needed before execution (one per line)<textarea rows={3} value={plan.missing_requirements.join('\n')} onChange={e=>field('missing_requirements',e.target.value.split('\n').filter(Boolean))}/></label>
 {plan.steps.map((step,index)=><fieldset key={step.id}><legend>Step {index+1}: {step.title}</legend><label>Title<input value={step.title} onChange={e=>stepField(index,'title',e.target.value)}/></label><label>Instructions<textarea rows={5} value={step.instructions} onChange={e=>stepField(index,'instructions',e.target.value)}/></label><label>How success is checked<textarea rows={2} value={step.acceptance} onChange={e=>stepField(index,'acceptance',e.target.value)}/></label>{step.path!==null&&step.path!==undefined&&<label>Workspace path<input value={step.path} onChange={e=>stepField(index,'path',e.target.value)}/></label>}<p className="muted">Operation: {step.kind.replaceAll('_',' ')}. Dependencies: {step.depends_on.join(', ')||'None'}.</p>{step.build&&<details><summary>Reviewed remote build command and artifacts</summary><pre>{JSON.stringify(step.build,null,2)}</pre><p>Requires a Linux worker and separate approval for this exact command. Artifact checks establish matching bytes; application tests are separate.</p></details>}{canChooseComputer(step)&&<div><label>Required computer<select value={step.computer_id||''} onChange={e=>computerField(index,e.target.value)}><option value="">Default placement (controller or approved automatic offload)</option>{step.computer_id&&!choices(step).some(node=>(node.id||node.node_id)===step.computer_id)&&<option value={step.computer_id}>Saved target unavailable: {step.computer_id}</option>}{choices(step).map(node=><option key={node.id||node.node_id} value={node.id||node.node_id}>{deviceLabel(node.public_identity?.display_name||node.hostname||node.id)} · {node.id||node.node_id}</option>)}</select></label><p className="muted">A required remote computer needs coordinated missions (level 5). If unavailable or busy, this step waits for that computer; it does not silently move to the controller.</p>{computers.error&&<p role="alert">Computer choices could not be refreshed. Saved targets are preserved.</p>}</div>}<button type="button" onClick={()=>remove(index)}>Remove step</button></fieldset>)}
 <button type="button" onClick={()=>{const id=`step_${Date.now()}`;update({...plan,steps:[...plan.steps,{id,title:'New step',kind:'model',instructions:'',path:null,argv:[],depends_on:plan.steps.length?[plan.steps.at(-1).id]:[],input_from:null,acceptance:'Describe the evidence needed to accept this step'}]})}}>Add step</button>
 </div>
}
