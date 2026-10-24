"""Point commands/feedback for the original-application profile only.

Native evidence: CPOINT 0x7092b0 tests movement locks only on a position
change; 0x7095e0 has a 13000 ms timeout branch. Renderer 0x412340 distinguishes
commanded movement from loss of indication. The 2 s automatic feedback below
is a teaching parameter, NOT a measured mechanical duration of that program.
"""
from .commands import group_ids


class ReferencePoints:
    point_travel_seconds = 2.0
    point_timeout_seconds = 13.0

    def _switch_lock_fact(self, session, route, ignore_instance=None):
        for sid, position in route['switches'].items():
            point = session.switches[sid]
            owners = point['owners'] - {ignore_instance}
            if not owners:
                continue
            # A matching position does not waive any of the base occupancy,
            # indication, sealing, section lock or hostile-route checks.
            if point['position'] != position or point.get('moving') or any(
                owner not in session.routes or
                self.routes[session.routes[owner]['route_id']]['switches'].get(sid) != position
                for owner in owners
            ):
                return 'SWITCH_ROUTE_LOCKED', f'道岔 {sid} 已被其他进路锁闭，不能转换', [sid]
        return None

    def _start_points(self, session, demands, now):
        motions = self._state(session)['point_motions']
        for sid, position in demands.items():
            point = session.switches[sid]
            if point['position'] == position:
                continue
            point.update(represented=False, moving=True, target_position=position, movement_failed=False)
            motions[sid] = {'target': position, 'due': now + self.point_travel_seconds,
                            'deadline': now + self.point_timeout_seconds}
        if any(session.switches[sid].get('moving') for sid in demands):
            self._event(session, 'switch_command', '道岔转换命令已发出，等待各端到位表示；信号保持关闭')

    def _advance_points(self, session, now):
        motions = self._state(session)['point_motions']
        for sid, motion in list(motions.items()):
            point = session.switches[sid]
            if now >= motion['due'] and not point.get('indication_fault'):
                point.update(position=motion['target'], represented=True, moving=False,
                             target_position=None, movement_failed=False)
                del motions[sid]
                self._event(session, 'switch_indication', f"道岔 {sid} 收到{'反位' if point['position'] else '定位'}表示")
            elif now >= motion['deadline']:
                point.update(moving=False, target_position=None, movement_failed=True, represented=False)
                del motions[sid]
                self._event(session, 'switch_timeout', f'道岔 {sid} 转换表示超时，停止转换命令，信号不得开放')
        for instance in session.routes.values():
            if instance['status'] != 'setting':
                continue
            route = self.routes[instance['route_id']]
            if any(session.switches[sid].get('moving') for sid in instance['switches']):
                continue
            fact = self._blocking_fact(session, route, instance['id'])
            if fact:
                instance['status'] = 'closed_locked'
                self._close_route_signals(session, instance)
                self._event(session, 'route_setting_failed', f'进路选排未完成：{fact[1]}；锁闭保持', route['id'])
            else:
                self._open_reference_signals(session, instance)

    def _close_route_signals(self, session, instance):
        for name in self.routes[instance['route_id']]['segment_signals']:
            if session.signals[name].get('route') == instance['route_id']:
                session.signals[name].update(aspect=None, route=None)

    def _protect_point_signals(self, session):
        for instance in session.routes.values():
            if instance['status'] in {'released', 'cancelled', 'setting', 'manual_unlocking'}:
                continue
            route = self.routes[instance['route_id']]
            # Total guide locking deliberately tolerates missing indication;
            # its existing explicit guards remain in reference_runtime.
            if instance.get('mode') == 'guide' and instance['signal'] in self._state(session)['guide_locks']:
                continue
            if any(not session.switches[sid]['represented'] or
                   session.switches[sid]['position'] != pos for sid, pos in route['switches'].items()):
                if any(session.signals[n].get('aspect') is not None for n in route['segment_signals']):
                    self._close_route_signals(session, instance)
                    instance['status'] = 'closed_locked'
                    self._event(session, 'signal_close', '道岔表示不符，相关信号关闭；进路锁闭保持', route['id'])

    def _operate_points(self, session, command, now):
        kind, target = command['type'], command.get('target', '')
        feedback = kind in {'SET_SWITCH_INDICATION', 'RESTORE_SWITCH_INDICATION'}
        if kind == 'SWITCH_SINGLE_LOCK':
            ids = group_ids(self, target)
            if any(session.switches[sid].get('moving') for sid in ids):
                return self._reject(session, '道岔正在转换，请等待本端到位表示后单锁',
                                    reason_code='SWITCH_MOVING', devices=ids)
        if kind not in {'SWITCH_TOTAL_NORMAL', 'SWITCH_TOTAL_REVERSE'} and not feedback:
            return None
        # Commands operate the pair; feedback belongs to the explicitly named
        # end(s). Selecting 5 never silently changes 7's feedback.
        ids = target.split('/') if feedback else group_ids(self, target)
        def reject(code, text):
            return self._reject(session, text, reason_code=code, devices=ids)
        if not ids or any(sid not in session.switches for sid in ids):
            return reject('UNKNOWN_DEVICE', '道岔不存在')
        if feedback:
            for sid in ids:
                point = session.switches[sid]
                point['indication_fault'] = kind == 'SET_SWITCH_INDICATION'
                if point['indication_fault']:
                    point['represented'] = False
                elif not point.get('moving'):
                    point.update(represented=True, movement_failed=False)
            self._advance_points(session, now)
            self._protect_point_signals(session)
            message = f"{'/'.join(ids)} 本端：{'设置失表示' if kind == 'SET_SWITCH_INDICATION' else '恢复表示'}"
        else:
            states = [session.switches[sid] for sid in ids]
            throats = {s['throat'] for s in self.package['signals']
                       if s['name'] in self._state(session)['guide_locks']}
            if any(self.switch_defs[sid]['throat'] in throats for sid in ids):
                return reject('GUIDE_TOTAL_LOCKED', '引导总锁闭期间不能转换该咽喉道岔')
            occupied = [self.switch_defs[sid]['section'] for sid in ids
                        if session.sections[self.switch_defs[sid]['section']]['occupied']]
            if occupied:
                return reject('SECTION_OCCUPIED', '道岔组区段占用，不能转换')
            if any(p['manual_locked'] for p in states):
                return reject('SWITCH_MANUAL_LOCKED', '道岔组已单锁，不能转换')
            if any(p['owners'] for p in states):
                return reject('SWITCH_ROUTE_LOCKED', '道岔组已被进路锁闭，不能转换')
            if any(p.get('moving') for p in states):
                return reject('SWITCH_MOVING', '道岔组正在转换，请等待到位表示')
            if any(not p['represented'] for p in states):
                return reject('SWITCH_UNREPRESENTED', '道岔组无表示，不能转换')
            position = int(kind == 'SWITCH_TOTAL_REVERSE')
            self._start_points(session, dict.fromkeys(ids, position), now)
            message = f"{'/'.join(ids)} 道岔组：" + ('等待到位表示' if any(p.get('moving') for p in states) else '已在所需位置')
        self._event(session, kind, message)
        return {'accepted': True, 'reason_code': 'OK', 'message': message, 'snapshot': self._snapshot(session)}
