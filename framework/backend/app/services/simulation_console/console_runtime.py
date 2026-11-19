"""Free-practice behaviour only. Assessment/experiment runtimes are unchanged."""
from copy import copy, deepcopy

from .clock import monotonic
from .commands import group_ids
from .reference_runtime import ReferenceSimulationService
from .runtime import SimulationService
from .console_train import ConsoleTrain
from .console_signals import ConsoleSignals
from .console_segments import ConsoleSegments
from .console_tracks import ConsoleTracks


# Opposing diagonals of the two scissors crossovers. Protection constrains
# movement, without ever injecting a red track circuit indication.
CROSSOVERS = ((('6', '8'), ('10', '12')), (('13', '15'), ('9', '11')))
OPPOSITE = {sid: other for a, b in CROSSOVERS for group, other in ((a, b), (b, a)) for sid in group}


class ConsoleSimulationService(ConsoleTrain, ConsoleSignals, ConsoleTracks, ConsoleSegments, ReferenceSimulationService):
    def new_session(self, owner_id, interval_available=True, occupied_sections=None):
        aliases = self.package.get('section_aliases', {})
        occupied = list(dict.fromkeys(n for name in occupied_sections or [] for n in aliases.get(name, [name])))
        return super().new_session(owner_id, interval_available, occupied)

    def _indication_group_locked(self, session, ids):
        if any(session.switches[sid]['owners'] for sid in ids):
            return True
        # A new total-guide path has no ordinary point owners, but is still
        # an active route for the device-menu fault-injection restriction.
        return any(instance.get('mode') == 'guide_total' and instance['status'] not in {'released', 'cancelled'}
                   and any(sid in self.routes[instance['route_id']]['path_switches']
                           and self.switch_defs[sid]['section'] in instance['remaining'] for sid in ids)
                   for instance in session.routes.values())

    def _crossing_blockers(self, session, sid, demands=None):
        demands = demands or {}
        return [other for other in OPPOSITE.get(sid, ())
                if demands.get(other, session.switches[other].get('target_position')
                               if session.switches[other].get('moving')
                               else session.switches[other]['position']) != 0]

    def _blocking_fact(self, session, route, ignore_instance=None):
        guide = self._state(session)['guide_armed'] == route['signal'] or session.routes.get(ignore_instance, {}).get('mode', '').startswith('guide')
        for signal in route.get('segment_signals', [route['signal']]):
            if session.signals[signal].get('filament_ok') is False and not guide:
                return 'SIGNAL_FILAMENT_BROKEN', f'{signal} 灯丝断丝，不能开放信号', [signal]
        # Validate a private view: a compatible shunt owns only its own locks.
        view = copy(session)
        view.sections = {n: {**s, 'owners': set(s['owners'])} for n, s in session.sections.items()}
        view.switches = {n: {**s, 'owners': set(s['owners'])} for n, s in session.switches.items()}
        # A flank-clearance reservation is conditional. A new parallel route
        # may move the protecting points to the native relieving position;
        # do not mistake that reservation for an actual overlapping train path.
        # Point ownership/indication and every actual path lock are still proved.
        for name in route['sections']:
            for owner in list(view.sections[name]['owners'] - {ignore_instance}):
                instance = session.routes.get(owner)
                if not instance or name in instance['sections'] or name not in instance['protection_sections']:
                    continue
                other = self.routes[instance['route_id']]
                checks = [c for c in other['clearance_checks'] if c['section'] == name]
                if checks and all(any(route['switches'].get(sid, other['switches'].get(sid, session.switches[sid]['position'])) == pos
                                      for sid, pos in c['clear_if_any'].items()) for c in checks):
                    view.sections[name]['owners'].discard(owner)
        terminal = route['sections'][-1] if route['sections'] else None
        if terminal and route['kind'] != 'train' and not self.section_defs[terminal]['switches']:
            state = view.sections[terminal]
            if state.get('occupancy_kind') in {'vehicle', 'fault'}:
                state['occupied'] = False
            for owner in list(state['owners'] - {ignore_instance}):
                instance = session.routes.get(owner)
                if not instance or instance['kind'] == 'train':
                    continue
                other = self.routes[instance['route_id']]
                common = set(route['sections']) & set(instance['remaining'])
                if (other['sections'][-1] == terminal and common == {terminal}
                        and terminal not in instance['protection_sections']):
                    state['owners'].discard(owner)
        old_guide = self._state(session)['guide_armed']
        if guide:
            self._state(session)['guide_armed'] = route['signal']
        try:
            fact = super()._blocking_fact(view, route, ignore_instance)
        finally:
            self._state(session)['guide_armed'] = old_guide
        if fact:
            return fact
        for sid, position in route['switches'].items():
            blockers = self._crossing_blockers(session, sid, route['switches']) if position else []
            if blockers:
                return 'CROSSOVER_PROTECTED', f"道岔 {sid} 受交叉渡线 { '/'.join(blockers) } 防护，不能转至反位", [sid, *blockers]
        return None

    def _start_points(self, session, demands, now):
        super()._start_points(session, demands, now)
        for sid, position in demands.items():
            point = session.switches[sid]
            # First normalize the opposite diagonal, then move this one.
            if position and point.get('moving') and any(
                    session.switches[n]['position'] != 0 or session.switches[n].get('moving')
                    or not session.switches[n]['represented'] for n in OPPOSITE.get(sid, ())):
                self._state(session)['point_motions'][sid]['due'] = float('inf')
                point['waiting_protection'] = True

    def _advance_points(self, session, now):
        for sid, motion in self._state(session)['point_motions'].items():
            point = session.switches[sid]
            if point.get('waiting_protection') and all(
                    session.switches[n]['represented'] and not session.switches[n].get('moving')
                    and session.switches[n]['position'] == 0 for n in OPPOSITE.get(sid, ())):
                motion['due'] = now + self.point_travel_seconds
                point['waiting_protection'] = False
        super()._advance_points(session, now)

    def _operate_points(self, session, command, now):
        kind, target = command['type'], command.get('target', '')
        if kind in {'SET_SWITCH_INDICATION', 'RESTORE_SWITCH_INDICATION'}:
            ids = group_ids(self, target)
            if not ids:
                return self._reject(session, '道岔组不存在', reason_code='UNKNOWN_DEVICE')
            if kind == 'SET_SWITCH_INDICATION':
                if self._indication_group_locked(session, ids):
                    return self._reject(session, '道岔组任一端在进路内，不能设置整组失表示',
                                        reason_code='SWITCH_ROUTE_LOCKED', devices=ids)
                for sid in ids:
                    session.switches[sid].update(represented=False, indication_fault=True)
                self._advance_points(session, now)
                self._protect_point_signals(session)
                self._event(session, kind, f"{'/'.join(ids)} 道岔组：失去表示")
                return {'accepted':True, 'message':session.last_message, 'snapshot':self._snapshot(session)}
            command = {**command, 'target':'/'.join(ids)}
            target = command['target']
        flags = {'SWITCH_SINGLE_LOCK':('manual_locked', True), 'SWITCH_SINGLE_UNLOCK':('manual_locked', False),
                 'SWITCH_SEAL':('sealed', True), 'SWITCH_UNSEAL':('sealed', False)}
        if kind in flags:
            ids = group_ids(self, target)
            if not ids:
                return self._reject(session, '道岔组不存在', reason_code='UNKNOWN_DEVICE')
            if kind == 'SWITCH_SINGLE_LOCK' and any(session.switches[sid].get('moving') for sid in ids):
                return self._reject(session, '道岔仍在转换，请取得表示后再单锁', reason_code='SWITCH_MOVING')
            field, value = flags[kind]
            for sid in ids:
                session.switches[sid][field] = value
            self._event(session, kind, f"{'/'.join(ids)}：{'单锁' if kind=='SWITCH_SINGLE_LOCK' else '单解' if kind=='SWITCH_SINGLE_UNLOCK' else '封闭' if kind=='SWITCH_SEAL' else '解除封闭'}")
            return {'accepted':True, 'message':session.last_message, 'snapshot':self._snapshot(session)}
        if kind == 'RESTORE_SWITCH_INDICATION' and 'position' in command.get('payload', {}):
            position = command['payload']['position']
            ids = target.split('/')
            if type(position) is not int or position not in (0, 1) or any(s not in session.switches for s in ids):
                return self._reject(session, '请选择有效道岔及定位或反位', reason_code='INVALID_FEEDBACK')
            for sid in ids:
                self._state(session)['point_motions'].pop(sid, None)
                session.switches[sid].update(position=position, represented=True, indication_fault=False,
                                            moving=False, target_position=None, movement_failed=False,
                                            waiting_protection=False)
            self._protect_point_signals(session)
            self._advance_points(session, now)
            self._event(session, kind, f"{'/'.join(ids)} 道岔组：恢复{'反位' if position else '定位'}表示")
            return {'accepted': True, 'message': session.last_message, 'snapshot': self._snapshot(session)}
        if kind == 'SWITCH_TOTAL_REVERSE':
            ids = group_ids(self, target)
            blocked = [sid for sid in ids if self._crossing_blockers(session, sid)]
            if blocked:
                return self._reject(session, '交叉渡线防护：请先将另一渡线恢复定位',
                                    reason_code='CROSSOVER_PROTECTED', devices=blocked)
        return super()._operate_points(session, command, now)

    def operate_reference(self, session, command):
        guide = self._operate_guide(session, command)
        if guide is not None:
            return guide
        track = self._operate_track(session, command)
        if track is not None:
            return track
        segment = self._operate_segment(session, command)
        if segment is not None:
            return segment
        if command['type'] == 'SIMULATE_TRAIN_START':
            return self._start_train(session, command)
        if command['type'] in {'SIGNAL_FILAMENT_BREAK', 'SIGNAL_FILAMENT_RESTORE'}:
            target = command['target']
            if target not in session.signals:
                return self._reject(session, '信号机不存在', reason_code='UNKNOWN_DEVICE')
            good = command['type'] == 'SIGNAL_FILAMENT_RESTORE'
            session.signals[target]['filament_ok'] = good
            if not good:
                for instance in session.routes.values():
                    if instance['status'] not in {'released', 'cancelled'} and not instance['mode'].startswith('guide'):
                        for part in self._segments(instance):
                            if part['signal'] == target:
                                self._close_segment(session, instance, part, 'signal_close', f'{target} 正常信号灯丝断丝，信号关闭')
                if session.signals[target].get('aspect') != 'HB':
                    session.signals[target].update(aspect=None, route=None, instance_id=None)
            self._event(session, command['type'], f"{target}：{'灯丝完好' if good else '灯丝断丝，信号无法点亮，锁闭保持'}")
            return {'accepted': True, 'message': session.last_message, 'snapshot': self._snapshot(session)}
        if command['type'] == 'SIMULATE_TRAIN_STEP':
            instance = session.routes.get(command.get('payload', {}).get('route_instance_id'))
            if not instance or command['target'] not in instance['sections']:
                return self._reject(session, '该区段没有对应的行车进路', reason_code='ROUTE_TARGET_MISMATCH')
            return self.step_train(session.id, session.owner_id, instance['id'])
        return super().operate_reference(session, command)

    def _begin_track_proving(self, session, instance, now):
        super()._begin_track_proving(session, instance, now)
        # Clearance protection is checked/locked, but never part of the train
        # movement band. Do not paint 3DG or 25DG as a traversed section.
        instance['display_sections'] = list(instance['remaining'])

    def _release_due(self, session):
        super()._release_due(session)
        self._advance_trains(session, monotonic())
        self._advance_guide_holds(session, monotonic())
        SimulationService._release_due(self, session)
        self._advance_segment_releases(session, monotonic())
        self._advance_return_releases(session, monotonic())
        clearing = self._state(session).setdefault('clearing_sections', {})
        for name, due in list(clearing.items()):
            if due <= monotonic() or session.sections[name]['occupied']:
                del clearing[name]
                self._event(session, 'track_clear_display', f'{name} 出清显示结束')
        masks = self._state(session).setdefault('clearing_branches', {})
        for sid, mask in list(masks.items()):
            if mask['due'] <= monotonic():
                del masks[sid]

    def _snapshot(self, session):
        result = super()._snapshot(session)
        clearing = self._state(session).get('clearing_sections', {})
        for name, state in result['sections'].items():
            state['clearing'] = not state['occupied'] and clearing.get(name, 0) > monotonic()
        for sid, point in result['switches'].items():
            point['cross_protected'] = bool(self._crossing_blockers(session, sid))
            point['indication_fault_allowed'] = not self._indication_group_locked(session, group_ids(self, sid))
            section = self.switch_defs[sid]['section']
            actual = session.sections[section]
            branches = ['idle']*3
            for instance in session.routes.values():
                route = self.routes[instance['route_id']]
                if section not in instance.get('display_sections', []) or sid not in route['path_switches']:
                    continue
                if instance['id'] not in actual['owners']:
                    continue
                for branch in (0, 2 if route['path_switches'][sid] else 1):
                    branches[branch] = 'locked'
            mask = self._state(session).get('clearing_branches', {}).get(sid)
            if mask and mask['due'] > monotonic() and not actual['occupied']:
                for branch in mask['branches']:
                    branches[branch] = 'clearing'
            if actual['occupied']:
                instance = session.routes.get(actual.get('simulation_instance_id'))
                route = self.routes[instance['route_id']] if instance else None
                position = route['path_switches'].get(sid) if route else session.switches[sid]['position']
                if position is not None:
                    for branch in (0, 2 if position else 1):
                        branches[branch] = 'occupied'
            point['branch_displays'] = branches
            throat = self.switch_defs[sid]['throat']
            point['guide_total_locked'] = any(self._entry(n)['throat'] == throat for n in self._state(session)['guide_locks'])
        for route in result['routes']:
            instance = session.routes[route['id']]
            route.update(name=self.routes[route['route_id']]['name'], approach_section=instance['approach_section'],
                         auto_running=instance.get('auto_running', False))
            route['segments'] = [{**part, 'manual_remaining_seconds': max(0, int(part.get('manual_due', 0)-monotonic()+.99))}
                                 for part in self._segments(instance)]
            route['manual_remaining_seconds'] = max((p['manual_remaining_seconds'] for p in route['segments']), default=0)
            for part in route['segments']:
                result['signals'][part['signal']]['manual_remaining_seconds'] = part['manual_remaining_seconds']
            route['guide_remaining_seconds'] = max(0, int(instance.get('guide_deadline', 0)-monotonic()+.99))
            if instance['mode'].startswith('guide'):
                result['signals'][instance['signal']]['guide_remaining_seconds'] = route['guide_remaining_seconds']
        if session.history:
            session.history[-1] = deepcopy(result)
        return result
