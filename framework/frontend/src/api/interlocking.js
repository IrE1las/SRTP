import request from '@/utils/request'

export function seedDefaultStation() {
  return request.post('/interlocking/stations/seed-default')
}

export function resetStationState(stationId) {
  return request.post(`/interlocking/stations/${stationId}/reset-state`)
}

export function getStationDetail(stationId) {
  return request.get(`/interlocking/stations/${stationId}/detail`)
}

export function getStationSnapshot(stationId) {
  return request.get(`/interlocking/stations/${stationId}/snapshot`)
}

export function checkRoute(payload) {
  return request.post('/interlocking/routes/check', payload)
}

export function arrangeRoute(payload) {
  return request.post('/interlocking/routes/arrange', payload)
}

export function cancelRoute(payload) {
  return request.post('/interlocking/routes/cancel', payload)
}

export function operateSwitch(payload) {
  return request.post('/interlocking/switches/operate', payload)
}

export function updateSectionOccupancy(payload) {
  return request.post('/interlocking/sections/occupancy', payload)
}

export function manualUnlock(payload) {
  return request.post('/interlocking/unlock/manual', payload)
}
