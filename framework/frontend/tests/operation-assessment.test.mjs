import test from 'node:test'
import assert from 'node:assert/strict'
import { mergeConsole } from '../src/domain/operationConsole.js'

test('light polling preserves the station while updating countdowns and pending controls',()=>{
  const old={snapshot:{version:5,signals:{XD:{aspect:'U'}},routes:[{id:'r',status:'manual_unlocking',manual_remaining_seconds:20}],selection_remaining_seconds:9}}
  const incoming={revision:2,state_version:5,snapshot:null,pending:null,timers:{selection_remaining_seconds:8,routes:[{id:'r',manual_remaining_seconds:19}],fault_releases:{a:10}}}
  const result=mergeConsole(old,incoming)
  assert.deepEqual(result.snapshot.signals,old.snapshot.signals)
  assert.equal(result.snapshot.routes[0].manual_remaining_seconds,19)
  assert.equal(result.snapshot.selection_remaining_seconds,8)
  assert.equal(old.snapshot.routes[0].manual_remaining_seconds,20)
  assert.equal(result.pending,null)
})

test('initialization and changed station snapshots replace old state without losing a new full response',()=>{
  const incoming={revision:3,snapshot:{version:6,signals:{XD:{aspect:'U'}}}}
  assert.equal(mergeConsole(null,incoming),incoming)
  assert.equal(mergeConsole({snapshot:{version:4}},incoming),incoming)
})
