import test from 'node:test'
import assert from 'node:assert/strict'
import { resolveBackendOrigin } from '../src/backendLocation.js'

test('local and existing same-origin installs retain their endpoints', () => {
  assert.equal(resolveBackendOrigin('', { development: true }), 'http://localhost:8000')
  assert.equal(resolveBackendOrigin(undefined, { origin: 'https://kingdom.example' }), 'https://kingdom.example')
  assert.equal(resolveBackendOrigin(undefined, { origin: 'http://127.0.0.1:8012' }), 'http://127.0.0.1:8012')
  assert.equal(resolveBackendOrigin(undefined, { origin: 'http://192.168.1.2:8012' }), 'http://192.168.1.2:8012')
})

test('public remote endpoint accepts HTTPS and excludes accidental credentials or routing data', () => {
  assert.equal(resolveBackendOrigin(' https://api.kingdom.example/ '), 'https://api.kingdom.example')
  for (const value of ['https://token@api.example', 'https://api.example/api', 'https://api.example?token=secret', 'https://api.example/#secret', 'http://api.example', 'file:///tmp/backend']) {
    assert.throws(() => resolveBackendOrigin(value))
  }
})
