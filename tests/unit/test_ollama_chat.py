import json
import pytest
from backend.models.ollama_chat import request_body, response_payload


PROFILE = {'model': 'configured', 'num_ctx': 4096, 'ollama_think': False}


def test_structured_output_schema_is_transported_without_granting_tools():
    schema={'type':'object','properties':{'steps':{'type':'array','items':{'enum':['normalize_line_endings','text_digest']}}},'required':['steps']}
    body=request_body(PROFILE,{'messages':[{'role':'user','content':'Design a workflow'}],
        'response_format':{'type':'json_schema','json_schema':{'name':'workflow','schema':schema}}},256)
    assert body['format']==schema and 'tools' not in body
    assert body['options']['num_predict']==256


@pytest.mark.parametrize('value',[{},'json',{'type':'xml'},{'type':'json_schema','json_schema':{'schema':[]}},
    {'type':'json_schema','json_schema':{'schema':{'description':'x'*32768}}}])
def test_invalid_or_unbounded_structured_formats_are_rejected(value):
    with pytest.raises(ValueError):request_body(PROFILE,{'messages':[{'role':'user','content':'data'}],'response_format':value},128)


def test_json_object_mode_preserves_profile_thinking_configuration():
    body=request_body(PROFILE,{'messages':[{'role':'user','content':'data'}],'response_format':{'type':'json_object'}},128)
    assert body['format']=='json' and body['think'] is False


def request():
    return {'messages': [{'role': 'user', 'content': 'Read the project'}],
            'tools': [{'type': 'function', 'function': {'name': 'read_file', 'parameters': {'type': 'object'}}}],
            'tool_choice': 'auto', 'parallel_tool_calls': False, 'temperature': 0.2}


def response(**kwargs):
    return {'message': {'role': 'assistant', 'content': '', 'tool_calls': [
        {'function': {'name': 'read_file', 'arguments': {'path': 'note.txt'}}}]},
            'done': True, 'done_reason': 'stop', 'prompt_eval_count': 10, 'eval_count': 4, **kwargs}


def test_native_options_and_structured_tool_roundtrip_preserve_linkage():
    initial = request()
    native = request_body(PROFILE, initial, 128)
    assert native['options'] == {'num_predict': 128, 'num_ctx': 4096, 'temperature': 0.2}
    assert native['think'] is False and native['stream'] is False
    adapted = response_payload(PROFILE, response(), initial)
    assert adapted['usage'] == {'prompt_tokens': 10, 'completion_tokens': 4, 'total_tokens': 14}
    assistant = adapted['choices'][0]['message']
    call = assistant['tool_calls'][0]
    assert call['id'] and json.loads(call['function']['arguments']) == {'path': 'note.txt'}
    initial['messages'] += [assistant, {'role': 'tool', 'tool_call_id': call['id'], 'content': '{"text":"checked"}'}]
    followup = request_body(PROFILE, initial, 128)
    assert followup['messages'][-2]['tool_calls'][0]['id'] == call['id']
    assert followup['messages'][-2]['tool_calls'][0]['function']['arguments'] == {'path': 'note.txt'}
    assert followup['messages'][-1]['tool_name'] == 'read_file'
    assert followup['messages'][-1]['tool_call_id'] == call['id']


def test_thinking_default_is_not_silently_changed_and_text_limit_reported():
    native = request_body({'model': 'plain'}, request(), 64)
    assert 'think' not in native and 'num_ctx' not in native['options']
    adapted = response_payload(PROFILE, response(message={'role': 'assistant', 'content': 'partial', 'thinking': 'private reasoning'}, done_reason='length'), request())
    assert adapted['choices'][0]['finish_reason'] == 'length'
    assert adapted['choices'][0]['message']['reasoning_content'] == 'private reasoning'


@pytest.mark.parametrize('kwargs', [{'tool_choice': 'required'}, {'tool_choice': {'type': 'function', 'function': {'name': 'read_file'}}}, {'reasoning_effort': 'high'}])
def test_unsupported_controls_fail_instead_of_being_ignored(kwargs):
    with pytest.raises(ValueError): request_body(PROFILE, {**request(), **kwargs}, 64)


def test_unlinked_tool_result_and_nonobject_arguments_rejected():
    with pytest.raises(ValueError, match='preceding'):
        request_body(PROFILE, {'messages': [{'role': 'tool', 'tool_call_id': 'unknown', 'content': 'fake'}]}, 64)
    history = {'messages': [{'role': 'assistant', 'content': '', 'tool_calls': [
        {'id': 'call1', 'function': {'name': 'read_file', 'arguments': '[]'}}]}]}
    with pytest.raises(ValueError): request_body(PROFILE, history, 64)


def test_incomplete_parallel_or_budget_truncated_calls_are_not_executable():
    with pytest.raises(RuntimeError): response_payload(PROFILE, response(done=False), request())
    with pytest.raises(RuntimeError, match='budget'): response_payload(PROFILE, response(done_reason='length'), request())
    payload = response(); payload['message']['tool_calls'] *= 2
    with pytest.raises(RuntimeError, match='parallel'): response_payload(PROFILE, payload, request())


def test_tool_choice_none_removes_offered_tools_and_rejects_calls():
    body = {**request(), 'tool_choice': 'none'}
    assert 'tools' not in request_body(PROFILE, body, 64)
    with pytest.raises(RuntimeError): response_payload(PROFILE, response(), body)
