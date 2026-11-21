// Owner-facing summaries over recorded evidence only.
// Keep arbitrary event payloads, model prose and task prompts out of notifications.
import {taskEvidenceRecords} from './taskEvidence.js'
import {eventInfo} from './userStatus.js'

export function safeRecordedTime(value) {
  const date=typeof value==='number'
    ? new Date(value < 1e11 ? value*1000 : value)
    : typeof value==='string' ? new Date(value) : new Date(NaN)
  return Number.isFinite(date.getTime()) ? date.toLocaleString() : 'Time unavailable'
}

const APPROVED_TOOLS=new Set([
  'workspace.write@1.0.0','workspace.package@1.0.0','build.run@1.0.0',
  'process.run@1.0.0','computer.screenshot@1.0.0'
])
function shortItem(value,max=180){
  return typeof value==='string' && value.length>0
    ? value.replace(/[\r\n\t]/g,' ').slice(0,max) : null
}
export function taskChangeReport(task) {
  const state=typeof task?.status==='string'?task.status.toLowerCase():''
  const records=taskEvidenceRecords(task?.result)
  const lines=[]
  for(const record of records) {
    const tool=record?.outcome?.tool
    const output=record?.outcome?.output
    const verified=record?.verification?.state==='VERIFIED'
    // A verified model response is still not an execution receipt.
    if(!verified || !APPROVED_TOOLS.has(tool) || !output || typeof output!=='object') continue
    if(tool==='build.run@1.0.0') {
      for(const [name,artifact] of Object.entries(output.artifacts||{}).slice(0,20)){
        if(typeof artifact?.sha256==='string' && /^[a-f0-9]{64}$/i.test(artifact.sha256)) {
          const filename=shortItem(name)
          if(filename) lines.push({label:'Checksum-verified build artifact',detail:filename})
        }
      }
      continue
    }
    if(tool.startsWith('workspace.') && shortItem(output.path))
      lines.push({label:tool==='workspace.write@1.0.0'?'Recorded workspace write':'Recorded workspace package',detail:shortItem(output.path)})
    if(tool==='process.run@1.0.0' && Number.isInteger(output.exit_code))
      lines.push({label:'Recorded process exit code',detail:String(output.exit_code)})
    if(tool==='computer.screenshot@1.0.0')
      lines.push({label:'Verified screenshot receipt',detail:'A screenshot artifact was recorded'})
    if(lines.length>=20) break
  }
  return {
    hasResult:!!task?.result,
    finished:state==='completed'||state==='succeeded',
    lines:lines.slice(0,20),
    notice:lines.length
      ? 'These receipts show only the stated actions. They are not a Git diff, complete test run or proof that an external application now works.'
      : 'No independently verified file-change report is present. A task status or AI response cannot establish what changed.'
  }
}
const NOTICE_TYPES=new Set([
  'task.failed','task.completed','task.cancelled','task.recovery_required',
  'governance.approval_required','runtime.scheduler_tick_error'
])
const IMPORTANT=new Set(['task.failed','task.recovery_required','governance.approval_required','runtime.scheduler_tick_error'])
export function notificationItems(events,limit=30) {
  if(!Array.isArray(events)) return null
  const used=new Set()
  return events.filter(event=>{
    if(!event || typeof event!=='object' || !NOTICE_TYPES.has(event.event_type))return false
    const id=event.event_id
    if(typeof id!=='string'||!id||used.has(id))return false
    used.add(id);return true
  }).slice().reverse().slice(0,limit).map(event=>({
    id:event.event_id,
    title:eventInfo(event.event_type).title,
    explanation:eventInfo(event.event_type).explanation,
    when:safeRecordedTime(event.timestamp),
    important:IMPORTANT.has(event.event_type),
    // Do not leak event payloads or arbitrary task prompts into notifications.
    taskId:typeof event.task_id==='string'?event.task_id:null
  }))
}
export function healthSummary({hardware,orchestration,models}) {
  const hardwareReady=!!hardware && typeof hardware==='object'
  const peers=orchestration?.counts
  const inventory=orchestration?.inventory
  const profiles=Array.isArray(models?.profiles)?models.profiles:null
  return {
    cpuCores:hardwareReady&&Number.isInteger(hardware.cpu_cores)?hardware.cpu_cores:null,
    availableRamGB:hardwareReady&&Number.isFinite(hardware.memory_available_gb)?hardware.memory_available_gb:null,
    diskFreeGB:hardwareReady&&Number.isFinite(hardware.disk_free_gb)?hardware.disk_free_gb:null,
    connectedPeers:Number.isInteger(peers?.connected_peers)?peers.connected_peers:null,
    pairedPeers:Number.isInteger(peers?.paired_knights)?peers.paired_knights:null,
    inventoryComplete:typeof inventory?.complete==='boolean'?inventory.complete:null,
    configuredModels:profiles?profiles.length:null
  }
}
