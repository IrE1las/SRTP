import request from '@/utils/request'

const root = '/simulation-console'

export const getStationPackage = () => request.get(`${root}/station`)
export const createSimulationSession = (intervalAvailable = true, occupiedSections = []) => request.post(`${root}/sessions`, { interval_available: intervalAvailable, occupied_sections: occupiedSections })
export const getSimulationSnapshot = (sessionId) => request.get(`${root}/sessions/${sessionId}`)
export const getSimulationReplay = (sessionId) => request.get(`${root}/sessions/${sessionId}/replay`)
export const pressStationButton = (sessionId, button, version) => request.post(`${root}/sessions/${sessionId}/buttons`, { button, version })
export const clearStationSelection = (sessionId, version) => request.post(`${root}/sessions/${sessionId}/clear-selection`, { version })
export const advanceSimulationTrain = (sessionId, routeInstanceId, version) => request.post(`${root}/sessions/${sessionId}/advance`, { route_instance_id: routeInstanceId, version })
