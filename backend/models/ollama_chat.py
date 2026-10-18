"""Native Ollama chat transport with the harness's OpenAI-shaped contract.

Protocol reference: https://docs.ollama.com/api/chat and Ollama api/types.go.
This converts messages only; it grants no tools or execution authority.
"""
import json
import time
from uuid import uuid4


class NativeChatProtocolError(RuntimeError):
    """Fixed transport diagnostic; never contains generated text or credentials."""


def request_body(profile, request, output_limit):
    choice = request.get('tool_choice')
    if choice not in (None, 'auto', 'none'):
        raise ValueError('Native Ollama does not support required or named tool_choice; select auto or none')
    if request.get('reasoning_effort') is not None:
        raise ValueError('Configure ollama_think on the model profile instead of reasoning_effort for native Ollama')
    messages, names = [], {}
    for original in request['messages']:
        role = original.get('role')
        if role not in {'system', 'user', 'assistant', 'tool'}:
            raise ValueError('Unsupported native Ollama message role')
        content = original.get('content')
        message = {'role': role, 'content': '' if content is None else content}
        if isinstance(content, list):
            texts, images = [], []
            for part in content:
                if not isinstance(part, dict):
                    raise ValueError('Message content parts must be objects')
                if part.get('type') == 'text' and isinstance(part.get('text'), str):
                    texts.append(part['text'])
                elif part.get('type') == 'image_url':
                    url = part.get('image_url', {}).get('url', '')
                    if not isinstance(url, str) or not url.startswith('data:image/') or ';base64,' not in url:
                        raise ValueError('Native Ollama images require embedded base64 image data')
                    import base64
                    encoded = url.split(';base64,', 1)[1]
                    try:
                        base64.b64decode(encoded, validate=True)
                    except ValueError as error:
                        raise ValueError('Invalid embedded image data') from error
                    images.append(encoded)
                else:
                    raise ValueError('Unsupported native Ollama message content part')
            message['content'] = '\n'.join(texts)
            if images:
                message['images'] = images
        if not isinstance(message['content'], str):
            raise ValueError('Chat content must be text or supported image parts')
        if original.get('reasoning_content') is not None:
            message['thinking'] = original['reasoning_content']
        if original.get('tool_calls'):
            calls = []
            for call in original['tool_calls']:
                function = call['function']
                args = function.get('arguments', {})
                if isinstance(args, str):
                    args = json.loads(args)
                if not isinstance(args, dict) or not isinstance(function.get('name'), str) or not function['name']:
                    raise ValueError('Tool calls need a function name and JSON object arguments')
                identifier = call.get('id')
                if not isinstance(identifier, str) or not identifier or identifier in names:
                    raise ValueError('Tool call IDs must be present and unique in the conversation')
                names[identifier] = function['name']
                calls.append({'id': identifier, 'function': {'name': function['name'], 'arguments': args}})
            message['tool_calls'] = calls
        if role == 'tool':
            identifier = original.get('tool_call_id')
            if identifier not in names:
                raise ValueError('Tool result must reference a preceding assistant tool call')
            message.update(tool_call_id=identifier, tool_name=names[identifier])
        messages.append(message)
    options = {'num_predict': output_limit}
    if 'num_ctx' in profile:
        options['num_ctx'] = profile['num_ctx']
    for field in ('temperature', 'top_p'):
        if request.get(field) is not None:
            options[field] = request[field]
    body = {'model': profile['model'], 'messages': messages, 'stream': False, 'options': options}
    if request.get('tools') and choice != 'none':
        body['tools'] = request['tools']
    if profile.get('ollama_think') is not None:
        body['think'] = profile['ollama_think']
    return body


def response_payload(profile, payload, request):
    message = payload.get('message')
    if not isinstance(message, dict) or message.get('role') != 'assistant' or payload.get('done') is not True:
        raise NativeChatProtocolError('Native Ollama returned no completed assistant message')
    result = {'role': 'assistant', 'content': message.get('content', '')}
    if not isinstance(result['content'], str):
        raise NativeChatProtocolError('Native Ollama returned invalid assistant text')
    if message.get('thinking'):
        result['reasoning_content'] = message['thinking']
    native_calls = message.get('tool_calls') or []
    if not isinstance(native_calls, list):
        raise NativeChatProtocolError('Native Ollama returned invalid tool calls')
    if native_calls and request.get('tool_choice') == 'none':
        raise NativeChatProtocolError('Native Ollama returned tool calls while tool_choice was none')
    if len(native_calls) > 1 and request.get('parallel_tool_calls') is False:
        raise NativeChatProtocolError('Native Ollama returned parallel calls for a single-call request; no calls accepted')
    if native_calls and payload.get('done_reason') == 'length':
        raise NativeChatProtocolError('Native Ollama tool response exhausted its output budget; no calls accepted')
    identifiers = {call.get('id') for m in request['messages'] for call in m.get('tool_calls', [])}
    calls = []
    for call in native_calls:
        function = call.get('function', {})
        if not isinstance(function.get('name'), str) or not function['name'] or not isinstance(function.get('arguments'), dict):
            raise NativeChatProtocolError('Native Ollama returned invalid structured tool arguments')
        identifier = call.get('id') or 'call_' + uuid4().hex
        if not isinstance(identifier, str) or identifier in identifiers:
            raise NativeChatProtocolError('Native Ollama returned duplicate or invalid tool call IDs')
        identifiers.add(identifier)
        calls.append({'id': identifier, 'type': 'function', 'function': {
            'name': function['name'], 'arguments': json.dumps(function['arguments'], ensure_ascii=False)}})
    if calls:
        result['tool_calls'] = calls
    prompt_tokens, completion_tokens = payload.get('prompt_eval_count', 0), payload.get('eval_count', 0)
    return {'id': 'chatcmpl-' + uuid4().hex, 'object': 'chat.completion', 'created': int(time.time()),
            'model': payload.get('model', profile['model']), 'choices': [{'index': 0, 'message': result,
                'finish_reason': 'tool_calls' if calls else ('length' if payload.get('done_reason') == 'length' else 'stop')}],
            'usage': {'prompt_tokens': prompt_tokens, 'completion_tokens': completion_tokens,
                      'total_tokens': prompt_tokens + completion_tokens}}
