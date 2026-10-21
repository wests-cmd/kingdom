"""Owner-facing projection of execution evidence; model prose never proves progress."""
import platform
import socket
import time

ERRORS = {
    'desktop_observation_expired': ('The screen observation expired before input. No input was dispatched.', 'Take a fresh screen observation and re-plan against the current controls.'),
    'invalid_tool_arguments': ('The model supplied invalid tool arguments. No operation was dispatched.', 'Review the tool schema and send a scoped correction.'),
    'invalid_tool_call': ('The model requested an unavailable tool or an invalid call identity.', 'Review the available tools and correct the model request.'),
    'model_protocol_error': ('The model response did not follow the required tool protocol.', 'Inspect the model connection and send one scoped correction; do not replay actions.'),
    'model_unavailable': ('The selected model could not serve this request.', 'Check the model connection, context budget and availability.'),
    'turn_interrupted': ('The model turn was interrupted. Its checkpoint is retained.', 'Review retained tool receipts before continuing; do not blindly repeat actions.'),
    'dispatch_rejected': ('The model response or tool dispatch needs review.', 'Open technical details and review the retained checkpoint before continuing.'),
}

class AgentRejection(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(ERRORS[code][0])


def activity_summary(state, tasks, now=None):
    now = time.time() if now is None else now
    status = state['status']
    operations = []
    for record in state.get('pending', []):
        task = tasks.get(record['task_id'])
        operations.append({'task_id': record['task_id'], 'tool': record['name'],
            'status': str(task.get('status','unknown')).lower() if task else 'not_dispatched',
            'worker': task.get('assigned_to') if task else None})
    waiting_approval = any(p['status']=='waiting_approval' for p in operations)
    labels = {'ready':'Ready to continue', 'thinking':'Waiting for model',
        'waiting_tools':'Waiting for tool execution', 'needs_review':'Needs review',
        'completed':'Response finished', 'cancelled':'Stopped', 'budget_exhausted':'Turn budget reached'}
    label = 'Approval needed' if waiting_approval else labels.get(status,'Check status')
    started = state.get('model_started_at') or state.get('updated_at') or now
    wait = max(0, int(now-started)) if status=='thinking' else 0
    # Count only server-collected receipts, never an assistant's completion claim.
    verified = state.get('verified_action_count')
    if verified is None:
        verified=0
        for message in state.get('messages',[]):
            if message.get('role')!='tool':continue
            try:
                import json
                receipt=json.loads(message.get('content',''))
                if receipt.get('task_id') and receipt.get('verification_scope') and 'output' in receipt:
                    verified+=1
            except (ValueError,TypeError):pass
    receipts=[]
    import json
    for index,message in enumerate(state.get('messages',[])):
        if message.get('role')!='tool':continue
        try:
            receipt=json.loads(message.get('content',''))
            if not receipt.get('task_id') or not receipt.get('verification_scope'):continue
            previous=state['messages'][index-1] if index else {}
            call=next((call for call in previous.get('tool_calls',[]) if call.get('id')==message.get('tool_call_id')),None)
            name=call.get('function',{}).get('name') if call else None
            receipts.append((name,receipt.get('output',{})))
        except (ValueError,TypeError,AttributeError):pass
    reads=sum(name=='workspace_read' for name,_ in receipts)
    writes=sum(name=='workspace_write' for name,_ in receipts)
    empty=any(name=='workspace_list' and isinstance(output,dict) and output.get('entries')==[] for name,output in receipts)
    checks = list(state.get('required_tools',[]))
    attention = ''
    if status=='thinking' and wait>=30:
        attention='The model is slow to respond. No new tool execution is confirmed by waiting; you can stop and retain the checkpoint.'
    elif not checks:
        attention='No required execution checks were set. A finished response alone does not prove the requested work was done.'
    if empty and not reads:
        attention='An inspected directory was empty and no existing source file was read. A written diagnosis is not evidence that the original failure was investigated.'
    code = state.get('error_code')
    blocker, recovery = ERRORS.get(code, ('This job needs review. Its checkpoint and task evidence are retained.', 'Inspect the retained evidence and provide a scoped correction.'))
    if not state.get('error') and status not in {'needs_review','budget_exhausted'}:blocker=''
    if waiting_approval: next_action='Review the exact operation in Approvals & permissions.'
    elif status=='thinking': next_action='Wait for the model response, or stop the job. Do not submit a duplicate.'
    elif status=='waiting_tools': next_action='Wait for the listed tool task, or inspect it in Tasks.'
    elif status=='needs_review': next_action=recovery
    elif status=='completed': next_action='Review the actual result and independent tests before accepting the work.'
    elif status=='cancelled': next_action='Inspect any already-running tool task before creating another job.'
    else:next_action='Continue the saved job when ready; this state is not background execution.'
    return {'id':state['id'],'status':status,'status_label':label,'updated_at':state.get('updated_at'),
        'model_connection':state.get('model_profile'), 'selected_connection':state.get('selected_profile'),
        'selected_model':state.get('selected_model'), 'tool_host':socket.gethostname(), 'tool_platform':platform.system(),
        'workspace':state.get('workspace','.'), 'model_wait_seconds':wait, 'model_started_at':state.get('model_started_at'),
        'model_finished_at':state.get('model_finished_at'), 'turns':state.get('turns',0),'max_turns':state.get('max_turns',0),
        'verified_actions':verified,'source_reads':reads,'file_writes':writes,'empty_directory_observed':empty,'acceptance_checks':checks,'independent_tests_verified':False,
        'evidence_summary':f'{verified} tool action(s) have retained execution receipts. Independent code tests are still required.' if verified else 'No tool execution has been verified for this job.',
        'attention':attention,'blocker':blocker,'error_code':code,'next_action':next_action,'operations':operations,
        'events':[{key:event.get(key) for key in ('at','kind','tool','task_id') if event.get(key) is not None} for event in state.get('activity_events',[])][-40:]}
