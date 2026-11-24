import test from 'node:test'
import assert from 'node:assert/strict'
import {privateBrowserPreviewTask} from '../src/privateBrowserPreview.js'

test('private preview submits one read-only browser task, not host input', () => {
  const task = privateBrowserPreviewTask('https://Example.org/path?a=1')
  assert.equal(task.metadata.tool, 'computer.browser.run@1.0.0')
  assert.equal(task.metadata.tool_parameters.start_url, 'https://example.org/path?a=1')
  assert.deepEqual(task.metadata.tool_parameters.allowed_hosts, ['example.org'])
  assert.deepEqual(task.metadata.tool_parameters.actions, [])
  assert.equal(task.metadata.capability, undefined)
})

for (const bad of [
  '', 'example.org', 'http://example.org/', 'file:///etc/passwd',
  'https://localhost/', 'https://127.0.0.1/', 'https://example.org:8443/',
  'https://bob:pass@example.org/', 'https://example.org/#password',
  'https://user@example.org/', 'https://*.example.org/',
  'https://example.org/?token=secret',
  'https://example.org/?api_key=secret',
  'https://example.org/' + 'x'.repeat(2100),
]) {
  test('private preview refuses invalid or risky URL ' + bad.slice(0, 40), () => {
    assert.throws(() => privateBrowserPreviewTask(bad), Error)
  })
}
