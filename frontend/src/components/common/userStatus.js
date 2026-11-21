// Read-only explanations of actual Kingdom state. Never infer work completion
// from model text, network connectivity, or an allocated worker.
const STATES = Object.freeze({
  queued: {
    label: 'Waiting in line',
    explanation: 'Kingdom saved the task, but execution has not started.',
    next: 'Start Runtime if it is stopped. Check worker availability if this stays queued.'
  },
  waiting_approval: {
    label: 'Waiting for your approval',
    explanation: 'This action is paused until you review the exact request.',
    next: 'Review the pending request under Security Approvals. Approve only if you recognize the action.'
  },
  leased: {
    label: 'Assigned to a worker',
    explanation: 'A worker has a task lease. This does not prove execution or a successful result.',
    next: 'Watch for execution and verification. A disconnected worker may require recovery.'
  },
  running: {
    label: 'In progress',
    explanation: 'Kingdom recorded that execution started. The result has not been confirmed.',
    next: 'Check back for a completed result or a failure. You can inspect task details.'
  },
  recovery_required: {
    label: 'Recovery needs review',
    explanation: 'Kingdom recorded a problem that requires recovery before the work can continue.',
    next: 'Review the task, original failure, and recovery options before retrying.'
  },
  completed: {
    label: 'Recorded as completed',
    explanation: 'The task reached the completed state. Check its result and verification evidence.',
    next: 'Inspect the recorded output and verification. External outcomes may still need separate proof.'
  },
  failed: {
    label: 'Failed',
    explanation: 'The task did not complete successfully.',
    next: 'Check the failure explanation and developer diagnostics if needed before retrying.'
  },
  cancelled: {
    label: 'Cancelled',
    explanation: 'Kingdom recorded this task as cancelled.',
    next: 'Create a new task if you still need the work performed.'
  },
  canceled: {
    label: 'Cancelled',
    explanation: 'Kingdom recorded this task as cancelled.',
    next: 'Create a new task if you still need the work performed.'
  },
  pending: {
    label: 'Pending',
    explanation: 'The task is not confirmed as running or complete.',
    next: 'Review its details and required approvals.'
  },
  blocked: {
    label: 'Blocked',
    explanation: 'The task cannot continue under its current conditions.',
    next: 'Review the reported blocker and any required approvals.'
  },
  paused: {
    label: 'Paused',
    explanation: 'The task is paused; this is not a completed result.',
    next: 'Review why it stopped before resuming.'
  }
})

export function normalizedTaskStatus(value) {
  return typeof value === 'string' ? value.trim().toLowerCase().replaceAll('-', '_') : ''
}

export function taskStatusInfo(value) {
  return STATES[normalizedTaskStatus(value)] || {
    label: 'Status unavailable',
    explanation: 'Kingdom returned a state this view cannot explain yet. Do not assume the task is complete.',
    next: 'Open task details or developer diagnostics for its recorded state.'
  }
}

// Only count task state values received from the task API. Unknown state stays
// unknown; do not silently classify it as running, finished or successful.
export function taskCounts(tasks) {
  if (!Array.isArray(tasks)) return null
  const result = {queued: 0, running: 0, approvals: 0, recovery: 0,
    completed: 0, failed: 0, cancelled: 0, unknown: 0}
  for (const task of tasks) {
    const status = normalizedTaskStatus(task?.status)
    if (status === 'queued' || status === 'pending') result.queued++
    else if (status === 'running' || status === 'leased') result.running++
    else if (status === 'waiting_approval') result.approvals++
    else if (status === 'recovery_required' || status === 'blocked' || status === 'paused') result.recovery++
    else if (status === 'completed') result.completed++
    else if (status === 'failed') result.failed++
    else if (status === 'cancelled' || status === 'canceled') result.cancelled++
    else result.unknown++
  }
  return result
}

export function plainLanguageOverview({connection, lastUpdated, runtime, security, tasks}) {
  const counts = taskCounts(tasks)
  if (!lastUpdated) return {
    headline: 'Getting Kingdom status…',
    explanation: 'The dashboard has not received its first complete status snapshot.',
    next: 'The information below will appear after a successful refresh.',
    counts: null, stale: false
  }
  if (connection !== 'LIVE') return {
    headline: 'Connection lost — information may be old',
    explanation: 'Kingdom could not refresh the dashboard. Previous task counts and statuses are not current.',
    next: 'Check whether the local Kingdom service is running, then refresh this page.',
    counts, stale: true
  }
  if (runtime?.running !== true) return {
    headline: 'Runtime is stopped',
    explanation: 'Kingdom is reachable, but it is not currently processing new tasks.',
    next: 'Choose Start Runtime when you are ready for approved tasks to run.',
    counts, stale: false
  }
  if (runtime?.scheduler_running === false) return {
    headline: 'Task processing needs attention',
    explanation: 'The runtime reports running, but the scheduler is not running.',
    next: 'Open Runtime, inspect the service status, and review any reported failures.',
    counts, stale: false
  }
  if ((Number.isInteger(security?.pending_approvals_count) ? security.pending_approvals_count : 0) > 0 || (counts?.approvals || 0) > 0) return {
    headline: 'Your approval is needed',
    explanation: 'Kingdom has requests waiting for review. They will not be treated as approved automatically.',
    next: 'Read each request under Security Approvals, including its action and parameters.',
    counts, stale: false
  }
  if ((counts?.recovery || 0) > 0) return {
    headline: 'Some work needs recovery',
    explanation: 'One or more tasks are paused, blocked or marked as requiring recovery.',
    next: 'Open the Tasks section below and review the affected work before retrying.',
    counts, stale: false
  }
  if ((counts?.running || 0) > 0) return {
    headline: 'Kingdom is processing work',
    explanation: 'Tasks are running or assigned. No completion is claimed until results and evidence are recorded.',
    next: 'Follow the task statuses below to see what has actually finished.',
    counts, stale: false
  }
  if ((counts?.queued || 0) > 0) return {
    headline: 'Tasks are waiting to start',
    explanation: 'Work is queued, but none of these tasks is confirmed as running.',
    next: 'Check task requirements, worker availability and any approval requests.',
    counts, stale: false
  }
  return {
    headline: 'Kingdom is ready for approved work',
    explanation: 'The runtime reports running. No task is currently recorded as queued or running in this snapshot.',
    next: 'Open Tasks to submit a built-in analysis or review your recorded results.',
    counts, stale: false
  }
}

const EVENTS = Object.freeze({
  'task.queued': {
    title: 'A task was added to the queue',
    explanation: 'The request was saved. Execution has not been confirmed.'
  },
  'task.waiting_approval': {
    title: 'A task is waiting for approval',
    explanation: 'Review the exact request before deciding whether it can continue.'
  },
  'task.running': {
    title: 'Task execution started',
    explanation: 'This records a start, not a successful finish.'
  },
  'task.completed': {
    title: 'Task marked completed',
    explanation: 'Check the task result and verification evidence to understand what was actually done.'
  },
  'task.failed': {
    title: 'A task failed',
    explanation: 'The task did not complete successfully. Review the failure record.'
  },
  'task.cancelled': {
    title: 'A task was cancelled',
    explanation: 'Kingdom recorded a cancellation, not a completed result.'
  },
  'governance.approval_required': {
    title: 'Kingdom requested your approval',
    explanation: 'An action is waiting for your authorization. Inspect the request before approving.'
  },
  'runtime.started': {
    title: 'Runtime was started',
    explanation: 'Task processing is enabled. This does not prove any particular task finished.'
  },
  'runtime.stopped': {
    title: 'Runtime was stopped',
    explanation: 'New task processing was stopped; confirm the status of any ongoing work separately.'
  }
})
export function eventInfo(value) {
  return typeof value === 'string' && Object.hasOwn(EVENTS, value)
    ? EVENTS[value]
    : {title: 'Kingdom recorded a system event',
       explanation: 'This event has no beginner explanation yet. Its recorded type is available under technical details.'}
}
