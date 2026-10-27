import request from '@/utils/request'
export function createTheoryConsoleClient(questionKey) {
  if (!/^lab-0[1-4]-0[1-3]$/.test(questionKey)) throw new Error('本专题不使用联锁仿真操作台')
  const root = '/lab-topics/questions/' + encodeURIComponent(questionKey) + '/console'
  const session = id => root + '/sessions/' + encodeURIComponent(id)
  return {
    getStationPackage: () => request.get(root + '/station'),
    createSimulationSession: (intervalAvailable=true,occupiedSections=[]) => request.post(root+'/sessions',{interval_available:intervalAvailable,occupied_sections:occupiedSections}),
    getSimulationSnapshot: id => request.get(session(id)),
    getSimulationReplay: id => request.get(session(id)+'/replay'),
    pressStationButton: (id,button,version) => request.post(session(id)+'/buttons',{button,version}),
    clearStationSelection: (id,version) => request.post(session(id)+'/clear-selection',{version}),
    advanceSimulationTrain: (id,routeInstanceId,version) => request.post(session(id)+'/advance',{route_instance_id:routeInstanceId,version}),
    operateConsole: (id,command,version) => request.post(session(id)+'/commands',{...command,version}),
  }
}
