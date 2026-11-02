"""One narrow scope reminder, not a model-operated approval channel."""
import hashlib
import urllib.parse

QUESTION='Would you like me to proceed with submitting these changes for review?'
REMINDER=('Return the final patch/diff artifact and test evidence within the original assignment only. '
          'Kingdom will independently review the exact returned patch. Do not create a pull request. '
          'Do not merge, deploy, publish a release, spend funds, change permissions or weaken checks. '
          'This is not approval for any new operation or for your own test claims.')


def remind_original_scope(service,job_id,opener=None):
    state=service.get_job(job_id)
    if state['phase']!='paused' or state.get('remote_state')!='AWAITING_USER_FEEDBACK':return state
    service._current_authority(state)
    page='';latest=None
    for _ in range(12):
        path=state['session']+'/activities?pageSize=25'+('&pageToken='+urllib.parse.quote(page,safe='') if page else '')
        data=service.request(path,opener=opener)
        for activity in data.get('activities',[]):
            if 'agentMessaged' not in activity and 'userMessaged' not in activity:continue
            stamp=activity.get('createTime');name=activity.get('name');message=activity.get('agentMessaged',{}).get('agentMessage')
            if not isinstance(stamp,str) or not isinstance(name,str) or len(name)>300:continue
            if latest is None or (stamp,name)>(latest[0],latest[1]):latest=(stamp,name,message)
        page=data.get('nextPageToken','')
        if not page:break
    if page or latest is None:return state
    message=latest[2]
    if not isinstance(message,str) or len(message)>24000 or not message.strip().endswith(QUESTION):return state
    ident=hashlib.sha256((state['session']+':'+latest[1]+':'+hashlib.sha256(message.encode()).hexdigest()).encode()).hexdigest()
    with service.db.get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        current=service.get_job(job_id)
        history=current.get('scope_reminders',[])
        if current['phase']!='paused' or current.get('session')!=state['session'] or len(history)>=3 or any(h['id']==ident for h in history):return current
        history.append({'id':ident,'outcome':'claimed_outcome_unconfirmed'})
        current['scope_reminders']=history;service._save_job(conn,current);conn.commit()
    outcome='unknown'
    try:
        current=service.get_job(job_id)
        if current['phase']!='paused':outcome='withdrawn_before_post'
        else:
            service._current_authority(current)
            response=service.request(current['session']+':sendMessage',{'prompt':REMINDER},opener=opener,timeout=min(30,current['deadline_at']-service.clock()))
            if response!={}:raise ValueError('Unexpected scope reminder acknowledgement')
            outcome='acknowledged'
    except Exception:
        # A lost acknowledgement is never a retry instruction.
        outcome='unknown'
    with service.db.get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE');current=service.get_job(job_id)
        record=next(r for r in current['scope_reminders'] if r['id']==ident);record['outcome']=outcome
        if current['phase']=='paused' and outcome=='acknowledged':
            current.update(phase='watching',backoff_until=0,reason='Original output scope restated; returned patch still requires independent verification')
        service._save_job(conn,current);conn.commit()
    service._announce(current)
    return current
