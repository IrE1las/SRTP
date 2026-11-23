// Free-console toolbar, matching 标准站图/下方按钮.png. Shared assessed consoles
// retain standardDisplay.COMMANDS and their existing workflows.
import { COMMANDS } from './standardDisplay.js'
export function consoleCommands(locks=[]) {
  const total=(side,target,throat)=>({label:`${side}引导总锁`,type:locks.some(n=>throat.includes(n))?'GUIDE_TOTAL_UNLOCK':'GUIDE_TOTAL_LOCK',fixedTarget:target,sealed:true,active:locks.some(n=>throat.includes(n))})
  const names=['总取消','总人解','区故解','总定位','总反位','清除','单锁','单解','按钮封锁','按钮解封','道岔封锁','道岔解封']
  return [total('X','X',['X','XF','XD']),...names.map(label=>COMMANDS.find(c=>c.label===label)),total('S','S',['S','SF']),COMMANDS.find(c=>c.label==='重开信号')]
}
