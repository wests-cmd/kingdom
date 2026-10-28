"""Reviewed workflow mechanics. Model selections remain unapproved proposals."""
from backend.runtime.standing_review import relative_path


def compile_function_copy(data, outcome):
    if set(data)!={'blueprint','source','target'} or data['blueprint']!='function_copy.v1':
        raise ValueError('Unknown blueprint or parameters')
    source,target=relative_path(data['source']),relative_path(data['target'])
    if source==target:raise ValueError('Copy requires a distinct destination')
    return {'plan':{'title':'Copy and verify bounded function','objective':outcome,
        'deliverables':[target],'steps':[
            {'id':'source','title':'Read accepted source','kind':'read_file','path':source,'acceptance':'Verified source read'},
            {'id':'write','title':'Write independent copy','kind':'write_file','path':target,'depends_on':['source'],
             'input_from':'source','acceptance':'Verified copy write'},
            {'id':'read','title':'Read back the copy','kind':'read_file','path':target,'depends_on':['write'],
             'acceptance':'Verified copy digest'},
            {'id':'check','title':'Immutable function cases','kind':'function_check','depends_on':['write','read'],
             'input_from':'read','repair_source':'write','case_profile':'bounded_batch_size.v1',
             'acceptance':'All immutable cases pass; no broader repository claim'}]},'acceptance_step':'check'}
