import React, {useState} from 'react'
import api from '../api'
import useLiveData from '../hooks/useLiveData'

function PlannerQuestion({item, list, busy, act}) {
  const [answer, setAnswer] = useState('')
  return <div>
    <p><strong>Kingdom needs your answer:</strong> {item.question}</p>
    <label>Your answer <textarea value={answer} maxLength={4000} onChange={e=>setAnswer(e.target.value)}/></label>
    <button disabled={busy || !answer.trim()} onClick={()=>act(()=>api.post(`/work-programmes/${list.id}/items/${item.key}/answer`, {answer, expected_revision:list.revision}))}>Save answer and reconsider</button>
    <p>Saving an answer does not approve execution. Automatic planning resumes if enabled; otherwise choose Propose next plan.</p>
  </div>
}

function ChatGPTHandoff({item, list, busy, act}) {
  const [reply, setReply] = useState('')
  return <div>
    <p>Waiting for ChatGPT. Direct connection is not established. Copy this request into ChatGPT, then paste its JSON response below. No other model will take over this request.</p>
    <label>Request for ChatGPT <textarea readOnly rows={8} value={item.planning_request}/></label>
    <label>ChatGPT JSON response <textarea rows={6} maxLength={100000} value={reply} onChange={e=>setReply(e.target.value)}/></label>
    <button disabled={busy || !reply.trim()} onClick={()=>act(()=>api.post(`/work-programmes/${list.id}/items/${item.key}/chatgpt-response`, {text:reply, expected_revision:list.revision}))}>Validate ChatGPT response</button>
    <p>Imported origin is your declaration. Kingdom still validates the plan and requires its existing approvals and tests.</p>
  </div>
}

export default function WorkProgrammePanel() {
  const {data, error: readError, refresh} = useLiveData('/work-programmes', 5000)
  const {data: modelProfiles} = useLiveData('/workspace/model-profiles', 30000)
  const [text, setText] = useState(''), [project, setProject] = useState('kingdom')
  const [profile, setProfile] = useState('auto'), [busy, setBusy] = useState(false), [error, setError] = useState('')
  const [key, setKey] = useState(() => `list-${crypto.randomUUID()}`)
  const [revision, setRevision] = useState('')
  const [plannerMode, setPlannerMode] = useState('deliberative')
  const [routing, setRouting] = useState('local')
  const act = async operation => {
    setBusy(true); setError('')
    try {await operation(); await refresh()}
    catch (e) {setError(e.response?.data?.detail || 'Could not update this list. Reload its saved checkpoint.')}
    finally {setBusy(false)}
  }
  return <section className="panel" style={{minWidth:0, overflowWrap:'anywhere'}}>
    <h2>Describe the work in sections</h2>
    <p>Write a heading ending with a colon, then one outcome per line. Kingdom saves the list, proposes plans, and checks reviewed results. Each section needs a separately reviewed integration test before the next section can run.</p>
    <p>Automatic planning does not approve plans or enable execution. Enable reviewed work separately in the work list. Missing tools and failed checks stay visible.</p>
    {(error || readError) && <p role="alert">{error || 'Could not read saved programmes.'}</p>}
    <label>Project <select value={project} onChange={e=>setProject(e.target.value)}>{['kingdom','threadmap','centipede'].map(p=><option key={p}>{p}</option>)}</select></label>
    <label>Planner <select value={plannerMode} onChange={e=>setPlannerMode(e.target.value)}><option value="deliberative">Two plans → critique both → one improved plan</option><option value="chatgpt">ChatGPT — manual handoff until connected</option><option value="configured_chat">Single configured chat model</option></select></label>
    {plannerMode==='deliberative' && <><label>Planning models <select value={routing} onChange={e=>setRouting(e.target.value)}><option value="local">Local only (default)</option><option value="cloud">Cloud preferred, local fallback</option><option value="mixed">Mixed local and cloud</option></select></label><p>Up to three eligible connections per stage. Busy or usage-limited connections can fall back; Local only never selects cloud-labelled connections. Cloud and Mixed share the task and planning outputs with configured cloud models. Two plans may use the same model if only one is available.</p></>}
    <label>{plannerMode!=='configured_chat' ? 'Execution model' : 'Chat planner and execution model'} <select value={profile} onChange={e=>setProfile(e.target.value)}><option value="auto">Choose an available configured model</option>{(modelProfiles?.profiles||[]).filter(p=>plannerMode==='chatgpt'||!`${p.id} ${p.model}`.toLowerCase().includes('codex')).map(p=><option key={p.id} value={p.id}>{p.name||p.id}</option>)}</select></label>
    {plannerMode==='chatgpt' && <p>ChatGPT mode waits for an external response and never uses the execution model as a planner fallback. This does not sign into ChatGPT automatically.</p>}
    <details><summary>Project test source</summary>
      <label>Reviewed source commit (required for project tests) <input value={revision} maxLength={40} onChange={e=>setRevision(e.target.value)} placeholder="40-character commit"/></label>
      <p>The commit is your declaration. Test receipts do not attest the checkout automatically. Without a reviewed commit, project tests remain blocked.</p>
    </details>
    <label>Work to do <textarea value={text} maxLength={24000} rows={6} onChange={e=>setText(e.target.value)} placeholder={'Recovery:\n- Preserve queued conversations after restart\n- Cancel without duplicate work'}/></label>
    <button disabled={busy || !text.trim() || (revision!=='' && !/^[a-fA-F0-9]{40}$/.test(revision))} onClick={()=>act(async()=>{await api.post('/work-programmes',{project,idempotency_key:key,text,model_profile:profile,planner_mode:plannerMode,planner_routing:routing,source_revision:revision||null});setKey(`list-${crypto.randomUUID()}`);setText('')})}>Save this list</button>
    {(data || []).map(list=><article key={list.id} className="record-detail">
      <h3>{list.project} · {list.status}</h3>
      <p>Planner: {list.planner_mode==='deliberative' ? `Two plans, critique, synthesis · ${list.planner_routing||'local'}` : list.planner_mode==='chatgpt' ? 'ChatGPT (external handoff)' : 'Configured chat model'}</p>
      <p>{list.auto_plan ? (list.planner_mode==='chatgpt' ? 'Kingdom prepares the next eligible ChatGPT request automatically and waits for its response.' : 'Kingdom proposes the next eligible plan automatically.') : 'Automatic planning paused.'}</p>
      <button disabled={busy} onClick={()=>act(()=>api.post(`/work-programmes/${list.id}/settings`,{enabled:!list.auto_plan,expected_revision:list.revision}))}>{list.auto_plan ? 'Pause planning' : 'Enable automatic planning'}</button>
      <button disabled={busy} onClick={()=>act(()=>api.post(`/work-programmes/${list.id}/plan-next`,{expected_revision:list.revision}))}>{list.planner_mode==='chatgpt' ? 'Prepare next ChatGPT request' : 'Propose next plan'}</button>
      {list.sections.map((section,i)=><section key={i}>
        <h4>{section.title} · {section.status}</h4>
        {[...section.items, section.integration].map(item=><details key={item.key}>
          <summary>{item.title} · {item.planning.replaceAll('_',' ')} · {item.work_status.replaceAll('_',' ')}</summary>
          <p>{item.reason}</p>
          {(item.blocked_reasons || []).map((reason,n)=><p key={n}>{reason}</p>)}
          {item.planning==='awaiting_answer' && <PlannerQuestion item={item} list={list} busy={busy} act={act}/>}
          {item.planning==='awaiting_chatgpt' && <ChatGPTHandoff item={item} list={list} busy={busy} act={act}/>}
          {(item.clarifications||[]).map((entry,n)=><p key={n}>Question: {entry.question}<br/>Answer: {entry.answer}</p>)}
          {item.planning_stages && <details><summary>Plans, critique and model routing</summary><pre style={{whiteSpace:'pre-wrap'}}>{JSON.stringify(item.planning_stages,null,2)}</pre></details>}
          {item.planning==='blocked' && !item.mission_id && (item.planning_attempts||0)<3 && <button disabled={busy} onClick={()=>act(()=>api.post(`/work-programmes/${list.id}/items/${item.key}/retry-planning`,{expected_revision:list.revision}))}>Allow another planning attempt</button>}
          {item.proposal && <><p>Review the exact commands, paths, changes and acceptance scope before approval. A passing command only proves its reviewed test summary.</p><pre style={{whiteSpace:'pre-wrap'}}>{JSON.stringify(item.proposal,null,2)}</pre></>}
          {item.planning==='needs_review' && <button disabled={busy} onClick={()=>act(()=>api.post(`/work-programmes/${list.id}/items/${item.key}/approve`,{expected_revision:list.revision}))}>Approve this exact plan</button>}
          {item.evidence && <pre style={{whiteSpace:'pre-wrap'}}>{JSON.stringify(item.evidence,null,2)}</pre>}
        </details>)}
      </section>)}
    </article>)}
  </section>
}
