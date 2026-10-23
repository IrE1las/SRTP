"""Runtime used only by the recovered original-application station.

The teaching/experiment SimulationService and its workbook keep their existing
behaviour. Local block peers model an external input, not a hardware protocol.
"""
from copy import deepcopy
from time import monotonic

from .runtime import SimulationService


class ReferenceSimulationService(SimulationService):
    def __init__(self, package):
        self.reference_states = {}
        super().__init__(package)

    def _state(self, session):
        return self.reference_states.setdefault(session.id, {
            'blocks': {b['signal']: {**b, 'permission': session.interval_available,
                         'phase': 'permitted' if session.interval_available else 'idle',
                         'direction': 'departure', 'pending_direction': None}
                       for b in self.package['blocks']},
            'guide_locks': [], 'guide_armed': None, 'fault_releases': {},
        })

    def _snapshot(self, session):
        result = super()._snapshot(session)
        state = self._state(session)
        result.update(blocks=deepcopy(state['blocks']), guide_locks=list(state['guide_locks']),
                      guide_armed=state['guide_armed'],
                      fault_releases={name:max(0, int(due-monotonic()+0.99))
                                      for name,due in state['fault_releases'].items()})
        for item in result['routes']:
            original=session.routes[item['id']]
            item['mode']=original.get('mode','normal')
            item['segment_signals']=self.routes[original['route_id']]['segment_signals']
            item['cancelled_segments']=list(original.get('cancelled_subroutes',[]))
            item['guide_remaining_seconds']=max(0,int(original.get('guide_deadline',0)-monotonic()+0.99))
        # Base snapshots intentionally know nothing about this station's state.
        if session.history:
            session.history[-1] = deepcopy(result)
        return result

    def _conditional_sections(self, session, route):
        return [check['section'] for check in route.get('clearance_checks', [])
                if not any(route['switches'].get(sid,session.switches[sid]['position'])==pos
                           for sid,pos in check['clear_if_any'].items())]

    def _blocking_fact(self, session, route, ignore_instance=None):
        state = self._state(session)
        instance=session.routes.get(ignore_instance,{})
        guide = state['guide_armed'] == route['signal'] or instance.get('mode')=='guide'
        if route['signal'] in state['guide_locks'] and not guide:
            return 'GUIDE_TOTAL_LOCKED', '该咽喉处于引导总锁闭，不能办理正常进路', [route['signal']]
        # Total guide lock applies to the entire throat, including shunt starts.
        throats = {s['throat'] for s in self.package['signals'] if s['name'] in state['guide_locks']}
        if not guide and any(self.switch_defs[sid].get('throat') in throats for sid in route['switches']):
            return 'GUIDE_TOTAL_LOCKED', '该咽喉处于引导总锁闭', list(state['guide_locks'])
        if guide:
            if route['attribute'] != 11:
                return 'GUIDE_RECEIVING_ONLY', '引导只办理接车进路', [route['signal']]
            for sid,pos in route['switches'].items():
                if session.switches[sid]['position'] != pos:
                    return 'GUIDE_POINT_POSITION', '请先将引导进路道岔操纵至所需位置', [sid]
        block = state['blocks'].get(route.get('block_signal'))
        if block and (not block['permission'] or block['direction']!='departure'):
            return 'BLOCK_PERMISSION_REQUIRED', '对应区间尚未取得发车许可，请办理闭塞或辅助操作', [block['signal']]
        for signal in route.get('segment_signals', [route['signal']]):
            if session.signals[signal].get('sealed'):
                return 'SIGNAL_BUTTON_SEALED', f'{signal} 按钮已封锁', [signal]
            if session.signals[signal].get('lit', True) is False:
                return 'SIGNAL_UNLIT', f'{signal} 灭灯', [signal]
        # Guide reception tolerates a simulated track circuit fault, while
        # known vehicle occupancy and clearance protection remain enforced.
        temporarily_clear = []
        temporarily_represented = []
        if guide:
            for name in route['sections']:
                if session.sections[name].get('occupancy_kind')=='fault':
                    session.sections[name]['occupied']=False
                    temporarily_clear.append(name)
            if route['signal'] in state['guide_locks']:
                for sid in route['switches']:
                    if not session.switches[sid]['represented']:
                        temporarily_represented.append(sid)
                        session.switches[sid]['represented']=True
        try:
            # Per-block permission supersedes the base service's global preset.
            original_interval = session.interval_available
            if block:
                session.interval_available = block['permission']
            fact = super()._blocking_fact(session, route, ignore_instance)
        finally:
            session.interval_available = original_interval
            for name in temporarily_clear:
                session.sections[name]['occupied']=True
            for sid in temporarily_represented:
                session.switches[sid]['represented']=False
        if fact:
            return fact
        # Evaluate native clearance conditions against the positions that will
        # be selected, rather than stale pre-arrangement point positions.
        for check in route.get('clearance_checks', []):
            clear = any(route['switches'].get(sid,session.switches[sid]['position'])==pos
                        for sid,pos in check['clear_if_any'].items())
            if not clear and session.sections[check['section']]['occupied']:
                return 'CLEARANCE_OCCUPIED', f"超限绝缘防护区段 {check['section']} 占用", [check['section']]
        return None

    def _arrange(self, session, route):
        guide = self._state(session)['guide_armed']==route['signal']
        definition = {**route, 'aspect':'HB'} if guide else route
        result = super()._arrange(session, definition)
        if result['accepted']:
            instance = next(reversed(session.routes.values()))
            instance['mode'] = 'guide' if guide else 'normal'
            if guide:
                instance['guide_deadline']=monotonic()+15
            for signal in route.get('segment_signals', []):
                aspect = 'HB' if guide else 'B' if route['kind']!='train' else route['aspect']
                session.signals[signal].update(aspect=aspect, route=route['id'])
            self._state(session)['guide_armed']=None
            if guide:
                self._event(session,'guide_open',f"{route['signal']} 引导信号开放，进路保持锁闭",route['id'])
        result['snapshot']=self._snapshot(session)
        return result

    def select_button(self, session_id, owner_id, button, version=None):
        session=self._get(session_id,owner_id)
        with session.mutex:
            self._release_due(session)
            self._expire_selection(session)
            self._verify_version(session,version)
            if button not in self.buttons:
                return self._reject(session,'按钮不在原应用站场中',reason_code='UNKNOWN_DEVICE')
            signal=self.buttons[button].get('signal')
            if session.signals.get(signal,{}).get('sealed'):
                return self._reject(session,f'{signal} 按钮已封锁',reason_code='SIGNAL_BUTTON_SEALED',devices=[signal])
            proposed=session.selected+[button]
            exact=[r for r in self.package['routes'] if r['button_sequence']==proposed]
            if not exact:
                return super().select_button(session_id,owner_id,button,version)
            # Preserve all original alternatives instead of rejecting a valid
            # sequence because the teaching workbook had a different route.
            usable=[r for r in exact if not self._blocking_fact(session,r)]
            candidates=usable or exact
            selected=min(candidates,key=lambda r:(sum(session.switches[sid]['position']!=pos
                         for sid,pos in r['switches'].items()),r['source_row']))
            if len(exact)>1:
                self._event(session,'route_alternative',f"同按钮序列选排原文件第 {selected['source_row']} 行",selected['id'])
            return self._arrange(session,selected)

    def _expire_selection(self, session):
        before=bool(session.selected)
        super()._expire_selection(session)
        if before and not session.selected:
            self._state(session)['guide_armed']=None

    def clear_selection(self, session_id, owner_id, version=None):
        session=self._get(session_id,owner_id)
        with session.mutex:
            self._verify_version(session,version)
            self._state(session)['guide_armed']=None
            return super().clear_selection(session_id,owner_id,version)

    def _release_due(self, session):
        super()._release_due(session)
        state=self._state(session)
        for name,due in list(state['fault_releases'].items()):
            if monotonic()<due or session.sections[name]['occupied']:
                continue
            # Section release never erases another section's locks or occupancy.
            for owner in list(session.sections[name]['owners']):
                route=session.routes.get(owner)
                if route:
                    route['remaining'].discard(name)
                    route['release_due'].pop(name,None)
                    if not route['remaining']:
                        route['status']='released'
                        for other in [*session.sections.values(),*session.switches.values()]:
                            other['owners'].discard(owner)
            session.sections[name]['owners'].clear()
            for sid in self.section_defs[name]['switches']:
                session.switches[sid]['owners'].clear()
            del state['fault_releases'][name]
            self._event(session,'fault_unlock_complete',f'{name} 区故解延时完成')
        for instance in session.routes.values():
            if instance.get('mode')=='guide' and instance.get('guide_deadline',0)<=monotonic():
                if session.signals[instance['signal']].get('aspect')=='HB':
                    session.signals[instance['signal']].update(aspect=None,route=None)
                    instance['status']='closed_locked'
                    self._event(session,'guide_expired','引导信号保持超时，信号关闭、锁闭保持',instance['route_id'])
            if instance['status'] in {'released','cancelled'}:
                definition=self.routes[instance['route_id']]
                for signal in definition.get('segment_signals',[]):
                    if session.signals[signal].get('route')==instance['route_id']:
                        session.signals[signal].update(aspect=None,route=None)
                if not instance.get('block_cycle_complete') and instance.get('train_started'):
                    block=state['blocks'].get(definition.get('block_signal'))
                    if block and block['type']=='semi':
                        block.update(permission=False,phase='idle')
                    instance['block_cycle_complete']=True

    def step_train(self, session_id, owner_id, instance_id, version=None):
        session=self._get(session_id,owner_id)
        with session.mutex:
            persistent={name:{k:v for k,v in value.items() if k in {'sealed','lit'}}
                        for name,value in session.signals.items()}
            instance=session.routes.get(instance_id)
            if instance:
                definition=self.routes[instance['route_id']]
                next_index=instance['progress']+1
                if next_index>=0 and next_index<len(instance['sections']):
                    name=instance['sections'][next_index]
                    if session.sections[name].get('occupancy_kind')=='fault':
                        return self._reject(session,'轨道故障尚未恢复，请先恢复表示再模拟行车',reason_code='TRACK_FAULT',devices=[name])
            result=super().step_train(session_id,owner_id,instance_id,version)
            for name,fields in persistent.items():
                session.signals[name].update(fields)
            if result['accepted'] and instance:
                for cid in definition['subroutes']:
                    child=self.routes[cid]
                    entry=child['sections'][0]
                    if entry in instance['sections'] and instance['progress']>=instance['sections'].index(entry):
                        session.signals[child['signal']].update(aspect=None,route=None)
            result['snapshot']=self._snapshot(session)
            return result

    def operate_reference(self, session, command):
        """Called under console_commands' mutex/version/PIN checks."""
        kind,target=command['type'],command.get('target','')
        state=self._state(session)
        def reject(code,message):
            return self._reject(session,message,reason_code=code,devices=[target])
        def success(message):
            self._event(session,kind,message)
            return {'accepted':True,'reason_code':'OK','message':message,'snapshot':self._snapshot(session)}
        if kind in {'CANCEL_ROUTE','REPEAT_OPEN_SIGNAL'}:
            instance=session.routes.get(target,{})
            if any(name in state['fault_releases'] for name in instance.get('sections',[])):
                return reject('UNLOCK_PENDING','区故解倒计时期间不能总取消或重开信号')
            if kind=='CANCEL_ROUTE' and instance.get('mode')=='guide':
                return reject('GUIDE_CANCEL_REQUIRES_MANUAL','取消引导须使用总人解并确认口令')
            if kind=='REPEAT_OPEN_SIGNAL' and instance.get('cancelled_subroutes'):
                return reject('PARTIALLY_CANCELLED','组合进路已有基本段取消，请完成取消后重新选排')
        if kind=='REPEAT_OPEN_SIGNAL' and session.routes.get(target,{}).get('mode')=='guide':
            return reject('GUIDE_REOPEN_REQUIRED','引导信号须通过引导办理、确认口令后重开')
        if kind=='CANCEL_ROUTE':
            instance=session.routes.get(target)
            definition=self.routes.get(instance['route_id']) if instance else None
            if definition and definition['subroutes'] and instance['status'] not in {'released','cancelled'}:
                if instance.get('manual_release_due') is not None:
                    return reject('UNLOCK_PENDING','人工解锁倒计时中')
                signal=command.get('payload',{}).get('signal',instance['signal'])
                children=[self.routes[cid] for cid in definition['subroutes']]
                child=next((c for c in children if c['signal']==signal),None)
                if not child:
                    return reject('UNKNOWN_DEVICE','请选择该组合进路的基本段始端')
                cancelled=instance.setdefault('cancelled_subroutes',[])
                if child['id'] in cancelled:
                    return reject('SEGMENT_CANCELLED','该基本段已经取消')
                approach=child['approach_section']
                if instance['train_started'] or (approach and session.sections[approach]['occupied']):
                    return reject('APPROACH_LOCKED','该基本段已接近或进路已行车')
                if any(session.sections[n]['occupied'] for n in child['sections']):
                    return reject('SECTION_OCCUPIED','基本段区段仍占用')
                cancelled.append(child['id'])
                retained=[c for c in children if c['id'] not in cancelled]
                keep_sections={n for c in retained for n in c['sections']}
                keep_switches={sid for c in retained for sid in c['switches']}
                for name in child['sections']:
                    if name not in keep_sections:
                        instance['remaining'].discard(name)
                        session.sections[name]['owners'].discard(target)
                for sid in instance['switches']:
                    if sid not in keep_switches:
                        session.switches[sid]['owners'].discard(target)
                session.signals[signal].update(aspect=None,route=None)
                instance['status']='closed_locked' if retained else 'cancelled'
                if not retained:
                    for obj in [*session.sections.values(),*session.switches.values()]:
                        obj['owners'].discard(target)
                    instance['remaining'].clear()
                return success(f'{signal} 基本段取消完成；'+('其余基本段保持锁闭' if retained else '组合进路全部取消'))
        if kind=='SECTION_FAULT_UNLOCK':
            if target not in session.sections:
                return reject('UNKNOWN_DEVICE','请选择区段')
            track=session.sections[target]
            if track['occupied']:
                return reject('SECTION_OCCUPIED','请先确认并恢复区段空闲；区故解不会清除占用')
            if not track['owners']:
                return reject('SECTION_NOT_LOCKED','该区段没有进路锁闭')
            if target in state['fault_releases']:
                return reject('UNLOCK_PENDING','该区段已在区故解倒计时中')
            for owner in track['owners']:
                instance=session.routes.get(owner)
                if instance:
                    for signal in self.routes[instance['route_id']]['segment_signals']:
                        session.signals[signal].update(aspect=None,route=None)
                    instance['status']='closed_locked'
            state['fault_releases'][target]=monotonic()+30
            return success(f'{target} 相关信号关闭，区故解倒计时 30 秒，锁闭保持')
        if kind in {'GUIDE_ARM','GUIDE_MAINTAIN','GUIDE_TOTAL_LOCK','GUIDE_TOTAL_UNLOCK'}:
            signal=next((s for s in self.package['signals'] if s['name']==target and s.get('entry')),None)
            if not signal:
                return reject('GUIDE_RECEIVING_ONLY','请选择进站信号机')
            throat=signal['throat']
            if kind in {'GUIDE_ARM','GUIDE_MAINTAIN'}:
                existing=next((r for r in session.routes.values() if r['status'] not in {'released','cancelled'} and r['signal']==target),None)
                if kind=='GUIDE_MAINTAIN' and (not existing or session.signals[target]['aspect']!='HB'):
                    return reject('GUIDE_NOT_OPEN','引导未开放，请重新办理引导并确认口令')
                if existing:
                    state['guide_armed']=target
                    fact=self._blocking_fact(session,self.routes[existing['route_id']],existing['id'])
                    state['guide_armed']=None
                    if fact:
                        return self._reject(session,fact[1],reason_code=fact[0],devices=fact[2])
                    existing.update(mode='guide',guide_deadline=monotonic()+15,status='signal_open')
                    session.signals[target].update(aspect='HB',route=existing['route_id'])
                    return success(f'{target} 引导信号保持 15 秒；继续办理保持可延续开放')
                if session.signals[target].get('sealed'):
                    return reject('SIGNAL_BUTTON_SEALED','始端按钮已封锁')
                state['guide_armed']=target
                session.selected=[target+'LA']
                session.selection_deadline=monotonic()+15
                return success(f'{target} 已选择引导始端，请选择接车终端；道岔须预先就位')
            active=[r for r in session.routes.values() if r['status'] not in {'released','cancelled'}
                    and any(self.switch_defs[sid].get('throat')==throat for sid in r['switches'])]
            if active:
                return reject('THROAT_ROUTE_LOCKED','该咽喉仍有锁闭进路，请先解锁')
            if kind=='GUIDE_TOTAL_LOCK':
                if target not in state['guide_locks']:
                    state['guide_locks'].append(target)
            else:
                state['guide_locks']=[name for name in state['guide_locks']
                                      if next(s for s in self.package['signals'] if s['name']==name)['throat']!=throat]
            return success(f'{target} 咽喉引导总锁闭'+('建立' if kind=='GUIDE_TOTAL_LOCK' else '解除'))
        if kind.startswith('BLOCK_'):
            block=state['blocks'].get(target)
            if not block:
                return reject('UNKNOWN_DEVICE','请选择区间闭塞设备')
            section=next(s['approach_section'] for s in self.package['routes']
                         if s['signal']==target and s['attribute']==11)
            active=any(r['status'] not in {'released','cancelled'} and
                       (self.routes[r['route_id']].get('block_signal')==target or r['signal']==target)
                       for r in session.routes.values())
            if active or session.sections[section]['occupied']:
                return reject('BLOCK_BUSY','区间占用或关联进路仍锁闭，闭塞状态保持')
            if kind=='BLOCK_REQUEST':
                if block['type']!='semi':
                    return reject('BLOCK_TYPE','闭塞请求用于半自动闭塞')
                block.update(permission=False,phase='requested',pending_direction='departure')
            elif kind in {'BLOCK_DEPARTURE_AUX','BLOCK_RECEPTION_AUX'}:
                if block['type']!='auto':
                    return reject('BLOCK_TYPE','辅助方向操作用于自动闭塞')
                block.update(permission=False,phase='awaiting_peer',pending_direction='departure' if kind=='BLOCK_DEPARTURE_AUX' else 'reception')
            elif kind=='BLOCK_PEER_ACCEPT':
                if block['phase'] not in {'requested','awaiting_peer'}:
                    return reject('BLOCK_SEQUENCE','本站尚未发送闭塞或辅助请求')
                block.update(permission=True,direction=block['pending_direction'],pending_direction=None,phase='permitted')
            elif kind in {'BLOCK_RESET','BLOCK_ACCIDENT_RESET','BLOCK_TOTAL_AUX'}:
                block.update(permission=False,phase='idle',pending_direction=None)
            else:
                return reject('UNKNOWN_COMMAND','未知闭塞命令')
            label={'idle':'未闭塞','requested':'请求中','awaiting_peer':'等待邻站','permitted':'已许可'}[block['phase']]
            return success(f'{target} 闭塞：{label}；邻站输入由本地教学模拟提供')
        return None
