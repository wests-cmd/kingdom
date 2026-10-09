import React from 'react'
export default function MissionEditor({value,onChange}){
 let plan
 try{plan=JSON.parse(value)}catch{return <p>Check the advanced plan format to restore the guided editor.</p>}
 const update=next=>onChange(JSON.stringify(next,null,2))
 const field=(name,text)=>update({...plan,[name]:text})
 const stepField=(index,name,text)=>update({...plan,steps:plan.steps.map((step,i)=>i===index?{...step,[name]:text}:step)})
 const remove=index=>{const id=plan.steps[index].id;if(plan.steps.some(step=>step.depends_on.includes(id)||step.input_from===id)){window.alert('Remove or change the steps that depend on this one first.');return}update({...plan,steps:plan.steps.filter((_,i)=>i!==index)})}
 return <div className="page-stack"><label>Mission name<input value={plan.title} onChange={e=>field('title',e.target.value)}/></label><label>Your objective<textarea rows={4} value={plan.objective} onChange={e=>field('objective',e.target.value)}/></label>
 <label>What you will receive (one per line)<textarea rows={4} value={plan.deliverables.join('\n')} onChange={e=>field('deliverables',e.target.value.split('\n'))}/></label>
 <label>Needed before execution (one per line)<textarea rows={3} value={plan.missing_requirements.join('\n')} onChange={e=>field('missing_requirements',e.target.value.split('\n').filter(Boolean))}/></label>
 {plan.steps.map((step,index)=><fieldset key={step.id}><legend>Step {index+1}: {step.title}</legend><label>Title<input value={step.title} onChange={e=>stepField(index,'title',e.target.value)}/></label><label>Instructions<textarea rows={5} value={step.instructions} onChange={e=>stepField(index,'instructions',e.target.value)}/></label><label>How success is checked<textarea rows={2} value={step.acceptance} onChange={e=>stepField(index,'acceptance',e.target.value)}/></label>{step.path!==null&&step.path!==undefined&&<label>Workspace path<input value={step.path} onChange={e=>stepField(index,'path',e.target.value)}/></label>}<p className="muted">Operation: {step.kind.replaceAll('_',' ')}. Dependencies: {step.depends_on.join(', ')||'None'}.</p><button type="button" onClick={()=>remove(index)}>Remove step</button></fieldset>)}
 <button type="button" onClick={()=>{const id=`step_${Date.now()}`;update({...plan,steps:[...plan.steps,{id,title:'New step',kind:'model',instructions:'',path:null,argv:[],depends_on:plan.steps.length?[plan.steps.at(-1).id]:[],input_from:null,acceptance:'Describe the evidence needed to accept this step'}]})}}>Add step</button>
 </div>
}
