import test from 'node:test'
import assert from 'node:assert/strict'
import { ExamJournal, enterExam, secondsLeft, clockText, examPayload, beijingInput, beijingTime, examFormErrors } from '../src/domain/exams.js'

function setup() {
  const entries = new Map()
  const storage = { getItem: key => entries.get(key) ?? null, setItem: (key, value) => entries.set(key, value) }
  let time = Date.parse('2030-01-02T04:00:00Z'), id = 0
  const make = () => new ExamJournal(storage, 'attempt', () => time, () => 'event-' + ++id)
  return { make, storage, advance: ms => { time += ms } }
}

test('fullscreen refusal never calls begin; allowed fullscreen precedes begin', async () => {
  let calls = []
  await assert.rejects(enterExam(async () => { calls.push('fullscreen'); throw new Error('denied') }, async () => { calls.push('begin') }))
  assert.deepEqual(calls, ['fullscreen'])
  calls = []
  assert.equal(await enterExam(async () => calls.push('fullscreen'), async () => { calls.push('begin'); return 'attempt' }), 'attempt')
  assert.deepEqual(calls, ['fullscreen', 'begin'])
})

test('first exit survives refresh without a second exit or a new timeout', () => {
  const fixture = setup(), first = fixture.make()
  first.observe(false)
  const out = structuredClone(first.pending[0])
  fixture.advance(59000)
  const refreshed = fixture.make(); refreshed.observe(false)
  assert.deepEqual(refreshed.pending, [out])
  refreshed.observe(true)
  assert.deepEqual(refreshed.pending.map(e => e.kind), ['exit', 'restore'])
  assert.equal(Date.parse(refreshed.pending[1].occurred_at) - Date.parse(out.occurred_at), 59000)
  refreshed.observe(false)
  assert.deepEqual(refreshed.pending.map(e => e.kind), ['exit', 'restore', 'exit'])
})

test('offline events retain IDs and event times; acknowledgment preserves events created in flight', () => {
  const fixture = setup(), journal = fixture.make()
  journal.observe(false)
  const request = structuredClone(journal.pending)
  fixture.advance(20000); journal.observe(true)
  fixture.advance(45000)
  const reconnected = fixture.make()
  assert.deepEqual(reconnected.pending[0], request[0])
  reconnected.acknowledge(request.map(e => e.event_id))
  assert.equal(reconnected.pending.length, 1)
  assert.equal(reconnected.pending[0].kind, 'restore')
  reconnected.acknowledge(request.map(e => e.event_id))
  assert.equal(reconnected.pending.length, 1)
})

test('network-only outage adds no exit; separate clients merge durable pending events', () => {
  const fixture = setup(), one = fixture.make(), two = fixture.make()
  one.observe(true); two.observe(true)
  assert.deepEqual(one.pending, [])
  one.observe(false); two.observe(false)
  assert.equal(two.pending.length, 1)
  fixture.advance(1000); two.observe(true)
  one.acknowledge([])
  assert.equal(one.pending.length, 2)
})

test('corrupt or unwritable journal blocks rather than discarding pending events', () => {
  const fixture = setup()
  fixture.storage.setItem('attempt', '{broken')
  assert.throws(fixture.make)
  const storage = {getItem: () => null, setItem: () => { throw new Error('storage disabled') }}
  const journal = new ExamJournal(storage, 'attempt', Date.now, () => 'id')
  assert.throws(() => journal.observe(false), /storage disabled/)
})

test('deadline display clamps at zero and uses the server deadline after reload', () => {
  const deadline = '2030-01-02T04:05:00+00:00', start = Date.parse('2030-01-02T04:00:00Z')
  assert.equal(secondsLeft(deadline, start), 300)
  assert.equal(secondsLeft(deadline, start + 299999), 1)
  assert.equal(secondsLeft(deadline, start + 300000), 0)
  assert.equal(secondsLeft(deadline, start + 360000), 0)
  assert.equal(clockText(59), '0:59'); assert.equal(clockText(300), '5:00')
})

test('Beijing form produces explicit timezone independent of the host timezone', () => {
  const payload = examPayload({name:' 考试 ',classes:['信号一班'], version_id:3, opens_at:'2030-01-02T12:00', closes_at:'2030-01-02T13:00', duration_minutes:30})
  assert.equal(payload.opens_at, '2030-01-02T12:00:00+08:00')
  assert.equal(beijingInput('2030-01-02T04:00:00Z'), '2030-01-02T12:00')
  assert.match(beijingTime('2030-01-02T04:00:00Z'), /12:00:00/)
  assert.equal(payload.name, '考试')
})

test('publish validation rejects reversed or expired times and invalid durations at their fields',()=>{
  const form={name:'考试',classes:['一班'],version_id:3,opens_at:'2030-01-02T12:00',closes_at:'2030-01-02T13:00',duration_minutes:30}
  assert.deepEqual(examFormErrors(form,Date.parse('2030-01-02T04:00:00Z')), {})
  assert.match(examFormErrors({...form,closes_at:form.opens_at},0).closes_at,/晚于开放时间/)
  assert.match(examFormErrors(form,Date.parse('2030-01-03T00:00:00Z')).closes_at,/晚于当前时间/)
  for(const duration of [null,0,-1,1.5,10081])assert.ok(examFormErrors({...form,duration_minutes:duration},0).duration_minutes)
})
