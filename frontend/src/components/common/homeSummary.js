// A small, read-only home view over persisted task records.
// Never display raw prompts or treat a model reply as an external success.
import {normalizedTaskStatus, taskStatusInfo} from './userStatus.js'
import {taskEvidenceRecords} from './taskEvidence.js'

const ATTENTION = new Set(['waiting_approval','recovery_required','blocked','failed','denied','expired','unknown'])
const ACTIVE = new Set(['queued','pending','created','validating','waiting_authorization',
  'authorized','approved','leased','running','verifying','cancel_requested','paused'])
const FINISHED = new Set(['completed','succeeded','cancelled','canceled'])
const TOOL_TITLES = Object.freeze({
  'text.analyze@1.0.0': 'Text analysis',
  'code.python.analyze@1.0.0': 'Python syntax check',
  'build.run@1.0.0': 'Reviewed build',
  'provider.metadata@1.0.0': 'Provider metadata check'
})

export function homeTaskTitle(task) {
  const tool = task?.metadata?.tool
  return typeof tool === 'string' && Object.hasOwn(TOOL_TITLES,tool)
    ? TOOL_TITLES[tool] : 'Task'
}

export function homeTaskEvidence(task) {
  const state = normalizedTaskStatus(task?.status)
  if (!FINISHED.has(state) || ['cancelled','canceled'].includes(state)) return null
  if (!task?.result) return 'No result record available; completion cannot be verified here.'
  const records = taskEvidenceRecords(task.result)
  const verifiedReceipts = records.filter(r=>r?.verification?.state === 'VERIFIED').length
    + (records.length ? 0 : (task.result?.verification?.state === 'VERIFIED' ? 1 : 0))
  return verifiedReceipts
    ? `${verifiedReceipts} verified execution receipt${verifiedReceipts===1?'':'s'} recorded. Check the scope before accepting the result.`
    : 'No verified execution receipt shown. A model response alone cannot prove an external outcome.'
}

export function homeTaskGroups(tasks,limit=4) {
  if (!Array.isArray(tasks)) return null
  const rows=tasks.filter(item=>item && typeof item === 'object')
    .map((task,index)=>({task,index,ts:typeof task.created_at === 'string' && Number.isFinite(Date.parse(task.created_at))
      ? Date.parse(task.created_at) : 0}))
    .sort((a,b)=>b.ts-a.ts || b.index-a.index).map(row=>row.task)
  const result={attention:[],active:[],finished:[]}
  for (const task of rows) {
    const status=normalizedTaskStatus(task.status)
    // Unknown future lifecycle states must be reviewed, not silently considered completed.
    const target=ATTENTION.has(status)||!ACTIVE.has(status)&&!FINISHED.has(status)?'attention'
      : ACTIVE.has(status)?'active':'finished'
    if(result[target].length < limit) result[target].push(task)
  }
  return result
}

export function homeTaskSummary(task) {
  return taskStatusInfo(task?.status).label
}
