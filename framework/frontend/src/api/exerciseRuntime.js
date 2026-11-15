import request from '@/utils/request'

export function arrangeRouteInSession(data) {
  return request.post('/exercise-runtime/routes/arrange', data)
}

export function operateSwitchInSession(data) {
  return request.post('/exercise-runtime/switches/operate', data)
}

export function updateSectionOccupancyInSession(data) {
  return request.post('/exercise-runtime/sections/occupancy', data)
}

export function cancelRouteInSession(data) {
  return request.post('/exercise-runtime/routes/cancel', data)
}

export function manualUnlockInSession(data) {
  return request.post('/exercise-runtime/unlock/manual', data)
}
