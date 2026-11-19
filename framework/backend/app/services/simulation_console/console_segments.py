"""Basic-route state within a compound route, for the free console only.

An input failure belongs to the basic segment it protects. Normal occupancy,
repeat opening and manual release must not close or release a different segment.
"""
from copy import deepcopy
from .clock import monotonic


FINISHED = {'released', 'cancelled'}


class ConsoleSegments:
    def select_button(self, session_id, owner_id, button, version=None):
        session = self._get(session_id, owner_id)
        with session.mutex:
            self._release_due(session)
            self._expire_selection(session)
            self._verify_version(session, version)
            proposed = session.selected+[button]
            exact = [r for r in self.package['routes'] if r['button_sequence'] == proposed]
            if not exact and button in self.buttons:
                aliases = [r for r in self.package['routes'] if r['button_sequence'][:-1] == proposed[:-1]
                           and button in r.get('terminal_aliases', [])]
                if aliases:
                    signal = self.buttons[button].get('signal')
                    if session.signals.get(signal, {}).get('sealed'):
                        return self._reject(session, f'{signal} 按钮已封锁', reason_code='SIGNAL_BUTTON_SEALED')
                    usable = [r for r in aliases if not self._blocking_fact(session, r)]
                    route = deepcopy(min(usable or aliases, key=lambda r:(sum(session.switches[sid]['position'] != pos
                                           for sid,pos in r['switches'].items()), r['source_row'])))
                    route.update(id=f"{route['id']}@{button}", source_route_id=route['id'],
                                 terminal_signal=button[:-2], button_sequence=proposed,
                                 name=f"{route['signal']}>{button[:-2]}")
                    self.routes[route['id']] = route
                    return self._arrange(session, route)
            return super().select_button(session_id, owner_id, button, version)

    def _arrange(self, session, route):
        result = super()._arrange(session, route)
        if result['accepted']:
            instance = next(reversed(session.routes.values()))
            self._segments(instance)
            if instance['mode'] == 'guide':
                instance['mode'] = 'guide_route'
            result['snapshot'] = self._snapshot(session)
        return result

    def _segments(self, instance):
        if 'segments' not in instance:
            route = self.routes[instance['route_id']]
            children = [self.routes[c] for c in route['subroutes'] if not self.routes[c]['subroutes']]
            children = children or [route]
            children.sort(key=lambda c: min(instance['sections'].index(n) for n in c['sections'] if n in instance['sections']))
            instance['segments'] = [{'route_id': r['id'], 'signal': r['signal'], 'status': 'setting',
                                     'entered': False, 'seen': [], 'cleared': []} for r in children]
        return instance['segments']

    def _segment_definition(self, segment):
        return self.routes[segment['route_id']]

    def _close_segment(self, session, instance, segment, kind, message):
        signal = session.signals[segment['signal']]
        if signal.get('instance_id') == instance['id'] and signal.get('aspect') is not None:
            signal.update(aspect=None, route=None, instance_id=None)
            self._event(session, kind, message, instance['route_id'])
        if kind == 'signal_close':
            segment['status'] = 'closed_locked'
        elif segment['status'] not in FINISHED:
            segment['status'] = 'running'
        self._sync_segment_status(session, instance)

    def _sync_segment_status(self, session, instance):
        active = [s for s in self._segments(instance) if s['status'] not in FINISHED]
        if not active:
            instance.update(status='released', remaining=set(), release_due={}, display_sections=[])
            for value in [*session.sections.values(), *session.switches.values()]:
                value['owners'].discard(instance['id'])
        elif not instance.get('cancel_pending') and instance['status'] not in {'setting', 'track_proving'}:
            if all(s['status'] == 'manual_unlocking' for s in active):
                instance['status'] = 'manual_unlocking'
            elif any(session.signals[s['signal']].get('instance_id') == instance['id'] and
                     session.signals[s['signal']].get('aspect') is not None for s in active):
                instance['status'] = 'running' if instance['train_started'] else 'signal_open'
            elif all(s['status'] == 'closed_locked' for s in active):
                instance['status'] = 'closed_locked'

    def _open_reference_signals(self, session, instance):
        route = self.routes[instance['route_id']]
        for segment in self._segments(instance):
            if segment['status'] in FINISHED or segment['status'] == 'manual_unlocking':
                continue
            session.signals[segment['signal']].update(aspect='HB' if instance['mode'].startswith('guide') else route['aspect'],
                                                     route=route['id'], instance_id=instance['id'])
            segment['status'] = 'signal_open'
        instance['status'] = 'signal_open'
        if instance['mode'].startswith('guide'):
            self._update_guide_hold(session, instance, monotonic(), reset=True)
        guide = instance['mode'].startswith('guide')
        display = '引导已办理，灯丝断丝无法点亮信号' if guide and not session.signals[instance['signal']].get('filament_ok', True) else '引导红白灯开放' if guide else '信号开放'
        self._event(session, 'guide_open' if guide else 'signal_open', f"{route['name']} {display}", route['id'])

    def _protect_point_signals(self, session):
        for instance in session.routes.values():
            if instance['status'] in FINISHED | {'setting', 'track_proving'}:
                continue
            if instance.get('mode') == 'guide_total':
                continue
            for segment in self._segments(instance):
                if segment['status'] in FINISHED | {'manual_unlocking'}:
                    continue
                route = self._segment_definition(segment)
                if any((not session.switches[sid]['represented'] or session.switches[sid]['position'] != pos)
                       and instance['id'] in session.switches[sid]['owners'] for sid, pos in route['switches'].items()):
                    self._close_segment(session, instance, segment, 'signal_close',
                                        f"{segment['signal']} 道岔表示不符，信号关闭；本基本段锁闭保持")

    def _finish_segment(self, session, instance, segment, status='released'):
        route = self._segment_definition(segment)
        self._close_segment(session, instance, segment, 'segment_signal_close', f"{segment['signal']} 关闭")
        segment['status'] = status
        segment.pop('manual_due', None)
        if segment['route_id'] in self.routes[instance['route_id']]['subroutes']:
            key = 'cancelled_subroutes' if status == 'cancelled' else 'released_subroutes'
            if segment['route_id'] not in instance.setdefault(key, []):
                instance[key].append(segment['route_id'])
        retained = [self._segment_definition(s) for s in self._segments(instance) if s['status'] not in FINISHED]
        keep_sections = {n for r in retained for n in r['sections']}
        keep_switches = {sid for r in retained for sid in r['switches']}
        for name in route['sections']:
            if name not in keep_sections:
                session.sections[name]['owners'].discard(instance['id'])
                instance['remaining'].discard(name)
                instance['release_due'].pop(name, None)
                instance['display_sections'] = [n for n in instance.get('display_sections', []) if n != name]
        for sid in route['switches']:
            if sid not in keep_switches:
                session.switches[sid]['owners'].discard(instance['id'])
        self._sync_segment_status(session, instance)

    def _cancel_problem(self, session, instance, child=None):
        selected = next((s for s in self._segments(instance) if s['route_id'] == (child or self.routes[instance['route_id']])['id']), None)
        if selected is None:
            return 'UNKNOWN_SEGMENT', '请选择仍锁闭的基本段始端'
        if selected['status'] in FINISHED:
            return 'SEGMENT_RELEASED', '该基本段已经解锁'
        if selected.get('manual_due'):
            return 'UNLOCK_PENDING', '该基本段正在人工解锁'
        route = self._segment_definition(selected)
        approaches = route.get('approach_sections', [route['approach_section']] if route['approach_section'] else [])
        if selected['entered'] or any(session.sections[n]['occupied'] for n in approaches):
            return 'APPROACH_LOCKED', '该基本段已接近或已行车，不能总取消'
        names = [n for n in route['sections'] if n in instance['remaining']] + instance['protection_sections']
        if any(session.sections[n]['occupied'] for n in names):
            return 'SECTION_OCCUPIED', '基本段仍占用，不能总取消'
        if any(n in self._state(session)['fault_releases'] for n in names):
            return 'UNLOCK_PENDING', '本基本段正在区故解计时'
        if instance['mode'].startswith('guide'):
            return 'GUIDE_CANCEL_REQUIRES_MANUAL', '引导进路须使用总人解'
        return None

    def _complete_reference_cancel(self, session, instance):
        pending = instance.pop('cancel_pending')
        segment = next(s for s in self._segments(instance) if s['signal'] == pending['signal'])
        self._finish_segment(session, instance, segment, 'cancelled')
        if all(s['status'] == 'cancelled' for s in self._segments(instance)):
            instance['status'] = 'cancelled'
        self._event(session, 'route_cancel_complete', f"{pending['signal']} 基本段取消完成，其余基本段保持", instance['route_id'])

    def _operate_segment(self, session, command):
        kind = command['type']
        if kind == 'SECTION_FAULT_UNLOCK':
            track = session.sections.get(command['target'])
            if not track:
                return self._reject(session, '请选择有效轨道区段', reason_code='UNKNOWN_DEVICE')
            if not track['owners']:
                return self._reject(session, '该区段没有进路锁闭', reason_code='SECTION_NOT_LOCKED')
            if any(session.routes.get(owner, {}).get('cancel_pending') for owner in track['owners']):
                return self._reject(session, '相关基本段取消顺序执行中', reason_code='CANCEL_PENDING')
            closed = False
            for owner in list(track['owners']) if track else []:
                instance = session.routes.get(owner)
                if not instance:
                    continue
                for segment in self._segments(instance):
                    if command['target'] not in self._segment_definition(segment)['sections']:
                        continue
                    signal = session.signals[segment['signal']]
                    if signal.get('aspect') is not None and signal.get('instance_id') == instance['id']:
                        self._close_segment(session, instance, segment, 'section_fault_signal_close',
                                            f"{segment['signal']} 因区故解操作关闭；本次只关信号，锁闭保持")
                        segment['status'] = 'closed_locked'
                        instance.update(auto_running=False, auto_due=None)
                        self._sync_segment_status(session, instance)
                        closed = True
            if closed:
                return {'accepted': True, 'reason_code':'SIGNAL_CLOSED_LOCKS_HELD', 'snapshot':self._snapshot(session), 'message':session.last_message}
            if track['occupied']:
                return self._reject(session, '须先确认并恢复所选区段空闲，区故解不清除占用', reason_code='SECTION_OCCUPIED')
            releases = self._state(session)['fault_releases']
            if command['target'] in releases:
                return self._reject(session, '所选区段正在区故解计时', reason_code='UNLOCK_PENDING')
            releases[command['target']] = monotonic()+30
            self._event(session, kind, f"{command['target']} 对应信号已关闭，所选区段区故解计时30秒，其余基本段保持")
            return {'accepted':True, 'message':session.last_message, 'snapshot':self._snapshot(session)}
        if kind not in {'REPEAT_OPEN_SIGNAL', 'MANUAL_UNLOCK_ROUTE'}:
            return None
        instance = session.routes.get(command['target'])
        if not instance or instance['status'] in FINISHED:
            return self._reject(session, '请选择仍锁闭的进路', reason_code='ROUTE_NOT_LOCKED')
        if instance.get('cancel_pending'):
            return self._reject(session, '取消顺序执行中', reason_code='CANCEL_PENDING')
        signal = command.get('payload', {}).get('signal', instance['signal'])
        segment = next((s for s in self._segments(instance) if s['signal'] == signal and s['status'] not in FINISHED), None)
        if not segment:
            return self._reject(session, '该始端没有仍锁闭的基本段', reason_code='SEGMENT_RELEASED')
        route = self._segment_definition(segment)
        if segment.get('manual_due'):
            return self._reject(session, '基本段正在人工解锁', reason_code='UNLOCK_PENDING')
        if any(n in self._state(session)['fault_releases'] for n in route['sections']):
            return self._reject(session, '本基本段正在区故解计时', reason_code='UNLOCK_PENDING')
        if kind == 'REPEAT_OPEN_SIGNAL':
            if instance['mode'].startswith('guide'):
                return self._reject(session, '请按对应引导按钮重新办理引导', reason_code='GUIDE_REOPEN_REQUIRED')
            if segment['status'] != 'closed_locked' or segment['entered']:
                return self._reject(session, '基本段未因故关闭或已经行车', reason_code='SIGNAL_NOT_CLOSED')
            if (any(instance['id'] not in session.sections[n]['owners'] for n in route['sections'])
                    or any(instance['id'] not in session.switches[sid]['owners'] for sid in route['switches'])):
                return self._reject(session, '基本段已有区段解锁，须重新选排进路', reason_code='SEGMENT_PARTLY_RELEASED')
            fact = self._blocking_fact(session, route, instance['id'])
            if fact:
                return self._reject(session, fact[1], route['id'], fact[0], fact[2])
            session.signals[signal].update(aspect=self.routes[instance['route_id']]['aspect'],
                                           instance_id=instance['id'], route=instance['route_id'])
            segment['status'] = 'signal_open'
            self._sync_segment_status(session, instance)
            self._event(session, kind, f'{signal} 重复开放，本基本段锁闭保持', instance['route_id'])
        else:
            if any(session.sections[n]['occupied'] for n in route['sections']):
                return self._reject(session, '请先确认基本段车辆出清、故障恢复空闲，再办理人工解锁', reason_code='SECTION_OCCUPIED')
            self._close_segment(session, instance, segment, 'manual_signal_close', f'{signal} 人工解锁，先关闭信号')
            delay = 180 if instance['kind'] == 'train' else 30
            segment.update(status='manual_unlocking', manual_due=monotonic()+delay)
            instance.update(auto_running=False, auto_due=None)
            self._sync_segment_status(session, instance)
            self._event(session, 'manual_unlock_start', f'{signal} 基本段人工解锁计时 {delay} 秒，锁闭保持', instance['route_id'])
        return {'accepted': True, 'snapshot': self._snapshot(session), 'message': session.last_message}

    def _advance_segment_releases(self, session, now):
        for instance in session.routes.values():
            if instance['status'] in FINISHED:
                continue
            for segment in self._segments(instance):
                route = self._segment_definition(segment)
                if segment.get('manual_due') is not None and now >= segment['manual_due']:
                    if not any(session.sections[n]['occupied'] for n in route['sections']):
                        self._finish_segment(session, instance, segment)
                        self._event(session, 'manual_unlock_complete', f"{segment['signal']} 基本段人工解锁完成", instance['route_id'])
                elif segment['entered'] and segment['status'] not in FINISHED and not any(n in instance['remaining'] for n in route['sections']):
                    self._finish_segment(session, instance, segment)
