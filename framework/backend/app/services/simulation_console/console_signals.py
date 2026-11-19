"""Entry guide controls: route locking and throat total locking are distinct."""
from .clock import monotonic
from uuid import uuid4


class ConsoleSignals:
    def _guide_candidates(self, session, target):
        return [r for r in self.package['routes'] if r['signal'] == target and r['attribute'] == 11
                and all(session.switches[sid]['position'] == pos and not session.switches[sid].get('moving')
                        for sid, pos in r['switches'].items())]

    def _route_guide(self, session, target, maintain=False):
        existing = next((r for r in session.routes.values() if r['signal'] == target
                         and r['status'] not in {'released', 'cancelled'}), None)
        if maintain:
            if not existing or session.signals[target].get('aspect') != 'HB':
                return self._reject(session, '引导已关闭，请重新按引导按钮并确认口令', reason_code='GUIDE_NOT_OPEN')
            self._update_guide_hold(session, existing, monotonic(), reset=True)
            self._event(session, 'guide_hold', f'{target} 引导保持', existing['route_id'])
            return {'accepted': True, 'message': session.last_message, 'snapshot': self._snapshot(session)}
        candidates = self._guide_candidates(session, target)
        if not candidates:
            return self._reject(session, '当前道岔位置不能连通接车股道，请先将接车路径道岔就位', reason_code='GUIDE_POINT_POSITION')
        state = self._state(session)
        state['guide_armed'] = target
        try:
            usable = [(r, self._blocking_fact(session, r, existing['id'] if existing else None)) for r in candidates]
            chosen = next((r for r, fact in usable if not fact), None)
            if not chosen:
                fact = usable[0][1]
                return self._reject(session, fact[1], reason_code=fact[0], devices=fact[2])
            if existing:
                if existing['sections'] != chosen['sections']:
                    return self._reject(session, '原锁闭进路与当前道岔路径不一致，请先处理原锁闭', reason_code='SIGNAL_ROUTE_LOCKED')
                existing['mode'] = 'guide_route'
                self._open_reference_signals(session, existing)
                return {'accepted': True, 'message': session.last_message, 'snapshot': self._snapshot(session)}
            return self._arrange(session, chosen)
        finally:
            state['guide_armed'] = None
            session.selected = []
            session.selection_deadline = None

    def _update_guide_hold(self, session, instance, now, reset=False):
        first = instance['sections'][0]
        fault = session.sections[first].get('occupancy_kind') == 'fault'
        if fault:
            if reset or not instance.get('guide_deadline'):
                instance['guide_deadline'] = now+15
        else:
            instance.pop('guide_deadline', None)

    def _advance_guide_holds(self, session, now):
        for instance in session.routes.values():
            if not instance['mode'].startswith('guide') or instance['status'] in {'released', 'cancelled'}:
                continue
            if session.signals[instance['signal']].get('aspect') != 'HB':
                continue
            self._update_guide_hold(session, instance, now)
            if instance.get('guide_deadline') is not None and now >= instance['guide_deadline']:
                for segment in self._segments(instance):
                    self._close_segment(session, instance, segment, 'guide_close', f"{segment['signal']} 内方首区段故障，引导保持15秒到时关闭")
                    segment['status'] = 'closed_locked'
                self._sync_segment_status(session, instance)

    def _entry(self, target):
        return next((s for s in self.package['signals'] if s['name'] == target and s.get('entry')), None)

    def _total_locked(self, session, target):
        signal = self._entry(target)
        return bool(signal and any(self._entry(name)['throat'] == signal['throat']
                                   for name in self._state(session)['guide_locks']))

    def _operate_guide(self, session, command):
        kind, target = command['type'], command['target']
        signal = self._entry(target)
        state = self._state(session)
        total_instance = next((r for r in session.routes.values() if r['mode'] == 'guide_total'
                               and r['status'] not in {'released', 'cancelled'}
                               and (r['id'] == target or r['signal'] == target)), None)
        if kind == 'MANUAL_UNLOCK_ROUTE' and total_instance:
            for segment in self._segments(total_instance):
                self._close_segment(session, total_instance, segment, 'guide_close',
                                    f"{total_instance['signal']} 引导信号关闭；咽喉引导总锁仍保持")
                segment['status'] = 'closed_locked'
            total_instance.update(status='closed_locked', auto_running=False, auto_due=None)
            self._event(session, 'guide_close', f'{target} 引导信号关闭；咽喉引导总锁仍保持')
            return {'accepted': True, 'message': session.last_message, 'snapshot': self._snapshot(session)}
        if kind == 'GUIDE_TOTAL_LOCK' and signal:
            if any(s['throat'] == signal['throat'] and session.signals[s['name']].get('aspect') is not None
                   for s in self.package['signals']):
                return self._reject(session, '请先关闭本咽喉已开放信号，再办理引导总锁', reason_code='THROAT_SIGNAL_OPEN')
            if any(p.get('moving') for sid, p in session.switches.items() if self.switch_defs[sid]['throat'] == signal['throat']):
                return self._reject(session, '道岔仍在转换，请先确认位置再办理总锁', reason_code='SWITCH_MOVING')
            if not self._total_locked(session, target):
                state['guide_locks'].append(target)
            self._event(session, kind, f'{target} 咽喉引导总锁闭建立；信号保持关闭')
            return {'accepted': True, 'message': session.last_message, 'snapshot': self._snapshot(session)}
        if kind == 'GUIDE_TOTAL_UNLOCK' and signal:
            if any(s['entry'] and s['throat'] == signal['throat'] and session.signals[s['name']].get('aspect') == 'HB'
                   for s in self.package['signals']):
                return self._reject(session, '请先用总人解关闭该咽喉的引导信号，再解除引导总锁', reason_code='GUIDE_SIGNAL_OPEN')
            sections = {p['section'] for p in self.package['switches'] if p['throat'] == signal['throat']}
            sections |= {r['sections'][0] for r in self.package['routes'] if r['attribute'] == 11
                         and self._entry(r['signal']) and self._entry(r['signal'])['throat'] == signal['throat']}
            if any(session.sections[n].get('occupancy_kind') == 'vehicle' for n in sections):
                return self._reject(session, '该咽喉仍有车辆，须确认列车完整进入股道、咽喉出清后解除总锁', reason_code='THROAT_OCCUPIED')
            state['guide_locks'] = [n for n in state['guide_locks'] if self._entry(n)['throat'] != signal['throat']]
            for instance in session.routes.values():
                if instance['mode'] != 'guide_total' or self._entry(instance['signal'])['throat'] != signal['throat']:
                    continue
                if 'before_total_mode' in instance:
                    instance['mode'] = instance.pop('before_total_mode')
                elif instance['status'] not in {'released', 'cancelled'}:
                    for segment in self._segments(instance):
                        self._finish_segment(session, instance, segment, 'cancelled')
                    instance['status'] = 'cancelled'
            self._event(session, kind, f'{target} 咽喉引导总锁解除，原有手动单锁及进路锁闭分别保留')
            return {'accepted': True, 'message': session.last_message, 'snapshot': self._snapshot(session)}
        if kind not in {'GUIDE_ARM', 'GUIDE_MAINTAIN'} or not signal:
            return None
        if not self._total_locked(session, target):
            return self._route_guide(session, target, kind == 'GUIDE_MAINTAIN')
        if any(s['entry'] and s['name'] != target and s['throat'] == signal['throat']
               and session.signals[s['name']].get('aspect') == 'HB' for s in self.package['signals']):
            return self._reject(session, '同一咽喉已有引导信号开放', reason_code='GUIDE_THROAT_BUSY')
        if kind == 'GUIDE_MAINTAIN':
            return self._route_guide(session, target, True)
        indication = session.signals[target]
        if indication.get('lit', True) is False or indication.get('sealed'):
            return self._reject(session, '信号机灭灯或按钮封锁，不能开放引导', reason_code='SIGNAL_UNAVAILABLE')
        # Direction comes only from the pre-set branches. Missing indication
        # does not prevent total-guide opening, but blocks simulated passage
        # when the vehicle actually reaches that point.
        candidates = [r for r in self.package['routes'] if r['signal'] == target and r['attribute'] == 11
                      and all(session.switches[sid]['position'] == pos and not session.switches[sid].get('moving')
                              for sid, pos in r['path_switches'].items())]
        if not candidates:
            return self._reject(session, '当前道岔不能连通接车股道，请先解除总锁并核实道岔位置', reason_code='GUIDE_POINT_POSITION')
        chosen = min(candidates, key=lambda r:r['source_row'])
        if session.sections[chosen['sections'][0]].get('occupancy_kind') == 'vehicle':
            return self._reject(session, '信号机内方已有车辆，不能重开引导信号', reason_code='SECTION_OCCUPIED')
        existing = next((r for r in session.routes.values() if r['signal'] == target
                         and r['status'] not in {'released', 'cancelled'}), None)
        if existing:
            if existing['sections'] != chosen['sections']:
                return self._reject(session, '原锁闭路径与当前道岔接续不符，须先处理原进路', reason_code='SIGNAL_ROUTE_LOCKED')
            if existing['mode'] != 'guide_total':
                existing['before_total_mode'] = existing['mode']
            existing['mode'] = 'guide_total'
        else:
            approach = chosen['approach_section']
            existing = {'id':str(uuid4()), 'route_id':chosen['id'], 'kind':'train', 'signal':target,
                        'sections':list(chosen['sections']), 'protection_sections':[], 'approach_section':approach,
                        'remaining':set(chosen['sections']), 'switches':list(chosen['switches']),
                        'progress':-2 if approach else -1, 'status':'setting', 'release_due':{},
                        'display_sections':[], 'train_started':False, 'mode':'guide_total'}
            session.routes[existing['id']] = existing
        self._open_reference_signals(session, existing)
        session.selected = []
        session.selection_deadline = None
        lamp = '灯丝断丝，信号无法点亮；' if not indication.get('filament_ok', True) else ''
        self._event(session, 'guide_open', f"{target} 引导总锁：{lamp}按既定道岔接车至 {chosen['sections'][-1]}；路径上失表示道岔禁止模拟车通过")
        return {'accepted': True, 'message': session.last_message, 'snapshot': self._snapshot(session)}

