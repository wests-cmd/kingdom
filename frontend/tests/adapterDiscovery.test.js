import { test } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

test('AdapterDiscovery component presents truthful unverified status and distinctions', () => {
  const file = path.resolve('frontend/src/components/AdapterDiscovery.jsx')
  const content = fs.readFileSync(file, 'utf8')

  // Verify that the component does not simply display 'Ready' merely for installed binaries
  assert.ok(content.includes('Installed (Unverified)'))
  assert.ok(content.includes('Connected'))
  assert.ok(content.includes('ACP Compliance:'))
  assert.ok(content.includes('Planner Ready:'))
  assert.ok(content.includes('Configured Model Profiles & Capability Readiness'))
  assert.ok(content.includes('tool.unavailable_reasons'))
  assert.ok(content.includes('model.unavailable_reasons'))
})
