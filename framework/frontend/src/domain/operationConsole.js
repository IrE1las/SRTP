export function mergeConsole(previous, incoming) {
  if (incoming.snapshot || !previous?.snapshot) return incoming
  const timers = incoming.timers || {}, byId = new Map((timers.routes || []).map(item => [item.id, item]))
  return { ...incoming, snapshot: { ...previous.snapshot,
    selection_remaining_seconds: timers.selection_remaining_seconds ?? previous.snapshot.selection_remaining_seconds,
    fault_releases: timers.fault_releases ?? previous.snapshot.fault_releases,
    routes: (previous.snapshot.routes || []).map(item => ({ ...item, ...(byId.get(item.id) || {}) })),
    pending: incoming.pending } }
}
