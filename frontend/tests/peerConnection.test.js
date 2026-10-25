import test from 'node:test'
import assert from 'node:assert/strict'
import {peerConnectionLabel} from '../src/components/common/peerConnection.js'

test('a failed outbound route does not hide fresh authenticated incoming reports', () => {
  assert.equal(peerConnectionLabel('retrying', {node_state:'CONNECTED', last_heartbeat:90}, 100), 'Connected · receiving peer reports')
})

test('stale, future and disconnected reports cannot imply a current connection', () => {
  for (const peer of [{node_state:'CONNECTED',last_heartbeat:1}, {node_state:'CONNECTED',last_heartbeat:110}, {node_state:'DISCONNECTED',last_heartbeat:99}]) {
    assert.equal(peerConnectionLabel('retrying', peer, 100), 'Retrying connection')
  }
})

test('temporary membership expiry takes precedence over the last report', () => {
  assert.equal(peerConnectionLabel('membership_expired', {node_state:'CONNECTED',last_heartbeat:99}, 100), 'Temporary membership ended')
})
