import React, {useState} from 'react'
import api from '../api'
import useLiveData from '../hooks/useLiveData'
import OrchestrationBoard from '../components/OrchestrationBoard'
import ApprovalsView from '../components/security/ApprovalsView'
import SwarmGraph from '../components/graphs/SwarmGraph'
import ComputerIdentity from '../components/ComputerIdentity'
import {plainLanguageOverview, taskCounts, taskStatusInfo} from '../components/common/userStatus'
import {homeTaskGroups, homeTaskTitle, homeTaskEvidence} from '../components/common/homeSummary'

function AdvancedHomeDetails() {
  const {data:hierarchy,error} = useLiveData('/hierarchy',10000)
  return <div className="home-advanced">
    <p className="muted">Advanced details use separate recorded inventories and activity reports. A connected computer or an agent response does not prove a task succeeded.</p>
    <ComputerIdentity data={hierarchy} error={error}/>
    <OrchestrationBoard/>
    <ApprovalsView/>
    <SwarmGraph/>
  </div>
}

function TaskRow({task,finished=false,onNavigate}) {
  const info=taskStatusInfo(task?.status)
  const evidence=finished ? homeTaskEvidence(task):null
  const date=task?.created_at ? new Date(task.created_at) : null
  const validDate=date && Number.isFinite(date.getTime())
  return <li className="home-task-row">
    <div className="home-task-title"><strong>{homeTaskTitle(task)}</strong><span className="status-chip">{info.label}</span></div>
    <p>{info.explanation}</p>
    {evidence && <p className="muted"><strong>Evidence:</strong> {evidence}</p>}
    {!finished && <p className="muted"><strong>Next:</strong> {info.next}</p>}
    <div className="home-task-footer"><small>{validDate ? date.toLocaleString() : 'Time not recorded'}</small>
      <button type="button" onClick={()=>onNavigate?.('Tasks')}>Open task details</button></div>
  </li>
}

function WorkSection({heading,description,tasks,dataReady,finished=false,onNavigate,emptyMessage}) {
  return <section className="panel home-work-section" aria-label={heading}>
    <div className="section-heading">
      <div><h2>{heading}</h2><p className="muted">{description}</p></div>
      <button type="button" onClick={()=>onNavigate?.('Tasks')}>All tasks</button>
    </div>
    {!dataReady ? <p role="status">Task information not available yet.</p>
      : tasks.length ? <ul className="home-task-list">{tasks.map((task,index)=>
        <TaskRow key={task.id || index} task={task} onNavigate={onNavigate} finished={finished}/>)}</ul>
      : <p className="muted">{emptyMessage}</p>}
  </section>
}

export default function Dashboard({onNavigate,interfaceMode='easy'}) {
  const statusFeed=useLiveData('/status',3000)
  const tasksFeed=useLiveData('/tasks',3000)
  const securityFeed=useLiveData('/security/status',5000)
  const [advancedOverride,setAdvancedOverride]=useState(null)
  const advanced=advancedOverride===null ? interfaceMode==='advanced' : advancedOverride
  const [busy,setBusy]=useState(false)
  const [actionError,setActionError]=useState('')
  const runtime=statusFeed.data
  const tasks=Array.isArray(tasksFeed.data)?tasksFeed.data:null
  const security=securityFeed.data
  const dataReady=runtime && tasks && security && !statusFeed.error && !tasksFeed.error && !securityFeed.error
  const lastUpdated=(statusFeed.updated && tasksFeed.updated && securityFeed.updated)
    ? new Date(Math.min(statusFeed.updated.getTime(),tasksFeed.updated.getTime(),securityFeed.updated.getTime())) : null
  const connection=[statusFeed.error,tasksFeed.error,securityFeed.error].some(Boolean)
    ? 'OFFLINE' : dataReady ? 'LIVE' : 'CONNECTING'
  const overview=plainLanguageOverview({connection,lastUpdated,runtime,security,tasks})
  const counts=taskCounts(tasks)
  const groups=homeTaskGroups(tasks)
  const current=!!dataReady
  const pendingApprovals=current && Number.isInteger(security?.pending_approvals_count)
    ? security.pending_approvals_count : null

  async function refreshAll(){
    await Promise.all([statusFeed.refresh(),tasksFeed.refresh(),securityFeed.refresh()])
  }
  async function changeRuntime(action) {
    if (!current || busy) return
    setBusy(true);setActionError('')
    try {await api.post(action==='start'?'/start':'/stop');await refreshAll()}
    catch {setActionError('Kingdom could not confirm this runtime command. Check the Runtime status and connection before retrying.')}
    finally {setBusy(false)}
  }

  return <div className="home-control-center">
    <header className="home-welcome">
      <div><p className="eyebrow">Your workspace</p><h1>Home</h1>
        <p className="muted">See what needs you, what is happening, and what Kingdom actually recorded as finished.</p></div>
      <button type="button" onClick={refreshAll}>Refresh information</button>
    </header>

    <section className="panel home-overview" aria-label="Kingdom system status">
      <div className="section-heading">
        <div><h2>Kingdom right now</h2>
          <p className="muted">{lastUpdated?`Last synchronized at ${lastUpdated.toLocaleTimeString()}`:'Waiting for a complete status report'}</p>
        </div>
        <span className="status-chip">{connection==='LIVE'?'Information current':connection==='OFFLINE'?'Update failed':'Connecting'}</span>
      </div>
      <p role="status" className="home-headline"><strong>{overview.headline}</strong></p>
      <p>{overview.explanation}</p>
      <p><strong>Next step:</strong> {overview.next}</p>
      {(statusFeed.error || tasksFeed.error || securityFeed.error) && <p role="alert">
        One or more status sources could not refresh. Previous values may be out of date. Do not assume any action completed.</p>}
      <div className="home-summary-grid" aria-label="Status at a glance">
        <div className="card"><div className="card-title">Runtime</div><div className="card-value">
          {!current?'Unknown':runtime.running===true?'ACTIVE':runtime.running===false?'STOPPED':'Unknown'}</div>
          <small>{current?'Task processing switch on this computer':'Cannot confirm the current state'}</small>
        </div>
        <div className="card"><div className="card-title">Waiting / assigned</div><div className="card-value">
          {current&&counts?counts.queued+counts.running:'—'}</div><small>Not verified as finished</small>
        </div>
        <div className="card"><div className="card-title">Security requests</div><div className="card-value">
          {pendingApprovals??'—'}</div><small>Actions requiring your decision</small>
        </div>
        <div className="card"><div className="card-title">Recorded as finished</div><div className="card-value">
          {current&&counts?counts.completed:'—'}</div><small>Check each result's evidence</small>
        </div>
      </div>
      <div className="action-row">
        <button type="button" className="primary-red" disabled={!current || busy || runtime.running!==false}
          onClick={()=>changeRuntime('start')}>Start Runtime</button>
        <button type="button" disabled={!current || busy || runtime.running!==true}
          onClick={()=>changeRuntime('stop')}>Stop Runtime</button>
        <button type="button" onClick={()=>onNavigate?.('Tasks')}>Create a task</button>
        <button type="button" onClick={()=>onNavigate?.('Workbench')}>Talk & work</button>
      </div>
      {actionError && <p role="alert">{actionError}</p>}
    </section>

    <section className="panel home-work-section" aria-label="Needs your attention">
      <div className="section-heading"><div><h2>Needs your attention</h2>
        <p className="muted">Decisions, failures, or work that cannot safely continue.</p></div>
        <button type="button" onClick={()=>onNavigate?.('Governance')}>Review approvals</button></div>
      {!current ? <p role="status">Waiting for current approval and task information.</p> : <>
        {pendingApprovals>0 && <div className="home-attention-message" role="status">
          <strong>{pendingApprovals} security request{pendingApprovals===1?'':'s'} waiting for review.</strong>
          <p>Open Approvals & permissions to check the action, scope, and requesting computer before deciding.</p>
          <button type="button" onClick={()=>onNavigate?.('Governance')}>Review each request</button>
        </div>}
        {groups?.attention.length ? <ul className="home-task-list">
          {groups.attention.map((task,index)=><TaskRow key={task.id || index} task={task} onNavigate={onNavigate}/>)}
        </ul> : pendingApprovals===0 ? <p className="muted">No recorded task alerts or pending security requests in this snapshot.</p> : null}
        {counts?.unknown>0 && <p className="muted">{counts.unknown} task state{counts.unknown===1?' is':'s are'} unknown. Check the full task record before interpreting the result.</p>}
        <button type="button" onClick={()=>onNavigate?.('Recovery')}>Review recovery options</button>
      </>}
    </section>

    <WorkSection heading="Working now" description="Tasks queued, assigned, or executing. Assigned does not mean completed."
      tasks={groups?.active || []} dataReady={current} onNavigate={onNavigate}
      emptyMessage="No tasks are recorded as waiting or in progress."/>
    <WorkSection heading="Recently finished" description="Recorded task outcomes and the evidence available for each."
      tasks={groups?.finished || []} dataReady={current} onNavigate={onNavigate} finished
      emptyMessage="No completed or cancelled tasks recorded yet."/>

    <section className="panel" aria-label="More information">
      <div className="section-heading"><div><h2>More information</h2>
        <p className="muted">Your computers, permission settings and technical details are available when needed.</p></div></div>
      <div className="action-row">
        <button type="button" onClick={()=>onNavigate?.('Nodes')}>Connected computers</button>
        <button type="button" onClick={()=>onNavigate?.('Governance')}>Permissions</button>
        <button type="button" onClick={()=>onNavigate?.('Recovery')}>Recovery</button>
        <button type="button" aria-expanded={advanced} onClick={()=>setAdvancedOverride(!advanced)}>
          {advanced?'Hide technical details':'Show technical details'}</button>
      </div>
      {advanced && <AdvancedHomeDetails/>}
    </section>
  </div>
}
