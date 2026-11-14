"""Observable point -> track band -> signal stages, for reference sessions.

The short display interval is a simulation parameter requested for the replica,
not an original binary timing measurement. Resource reservations remain held
throughout; a cancelling route cannot authorize simulated train movement.
"""


class ReferenceSequence:
    route_display_seconds = 0.6

    def _begin_track_proving(self, session, instance, now):
        instance.update(status='track_proving',
                        display_sections=list(instance['remaining']) + instance['protection_sections'],
                        signal_open_due=now + self.route_display_seconds)
        self._event(session, 'route_track_lit', '道岔表示核对完成，进路轨道光带亮起；等待信号开放', instance['route_id'])

    def _cancel_problem(self, session, instance, child=None):
        if instance.get('manual_release_due') is not None:
            return 'UNLOCK_PENDING', '人工解锁倒计时中'
        approach = child['approach_section'] if child else instance['approach_section']
        if instance['train_started'] or (approach and session.sections[approach]['occupied']):
            return 'APPROACH_LOCKED', '该进路已接近或已行车，不能总取消'
        names = (child['sections'] if child else instance['sections']) + instance['protection_sections']
        if any(session.sections[name]['occupied'] for name in names):
            return 'SECTION_OCCUPIED', '进路区段仍占用，不能总取消'
        if any(name in self._state(session)['fault_releases'] for name in names):
            return 'UNLOCK_PENDING', '区故解倒计时期间不能总取消'
        return None

    def _request_reference_cancel(self, session, command, now):
        iid = command.get('target', '')
        instance = session.routes.get(iid)
        def reject(code, message):
            return self._reject(session, message, reason_code=code, devices=[iid])
        if not instance or instance['status'] in {'released', 'cancelled'}:
            return reject('ROUTE_NOT_LOCKED', '请选择仍锁闭的原进路')
        definition = self.routes[instance['route_id']]
        signal = command.get('payload', {}).get('signal', instance['signal'])
        child = None
        if definition['subroutes']:
            child = next((self.routes[cid] for cid in definition['subroutes']
                          if self.routes[cid]['signal'] == signal), None)
            if child is None:
                return reject('UNKNOWN_DEVICE', '请选择该组合进路的基本段始端')
            if child['id'] in instance.get('cancelled_subroutes', []):
                return reject('SEGMENT_CANCELLED', '该基本段已经取消')
        elif signal != instance['signal']:
            return reject('UNKNOWN_DEVICE', '请选择该进路的始端信号')
        problem = self._cancel_problem(session, instance, child)
        if problem:
            return reject(*problem)
        instance['cancel_pending'] = {'signal': signal, 'child': child['id'] if child else None,
                                      'phase': 'points', 'due': None}
        instance['status'] = 'cancelling'
        instance.pop('signal_open_due', None)
        self._event(session, 'route_cancel_start', '总取消已受理，停止行车授权；等待道岔转换结束后更新轨道光带和信号', definition['id'])
        if not any(session.switches[sid].get('moving') for sid in instance['switches']):
            self._cancel_track_display(session, instance, now)
        return {'accepted': True, 'reason_code': 'OK', 'message': session.last_message,
                'snapshot': self._snapshot(session)}

    def _retained_children(self, instance):
        pending = instance['cancel_pending']
        cancelled = set(instance.get('cancelled_subroutes', [])) | {pending['child']}
        return [self.routes[cid] for cid in self.routes[instance['route_id']]['subroutes'] if cid not in cancelled]

    def _cancel_track_display(self, session, instance, now):
        retained = self._retained_children(instance)
        keep = {name for child in retained for name in child['sections']}
        # A still-setting retained segment has no proved track band to retain.
        instance['display_sections'] = [name for name in instance.get('display_sections', []) if name in keep]
        instance['cancel_pending'].update(phase='signal', due=now + self.route_display_seconds)
        self._event(session, 'route_track_cancel', '道岔转换已结束，取消段轨道光带恢复；锁闭暂时保持，等待信号更新', instance['route_id'])

    def _advance_reference_sequences(self, session, now):
        for instance in session.routes.values():
            pending = instance.get('cancel_pending')
            if pending:
                if pending['phase'] == 'points':
                    if not any(session.switches[sid].get('moving') for sid in instance['switches']):
                        self._cancel_track_display(session, instance, now)
                    continue
                if now < pending['due']:
                    continue
                child = self.routes.get(pending['child'])
                problem = self._cancel_problem(session, instance, child)
                if problem:
                    self._close_route_signals(session, instance)
                    instance.update(status='closed_locked', display_sections=list(instance['remaining']))
                    del instance['cancel_pending']
                    self._event(session, 'route_cancel_blocked', f'取消未完成：{problem[1]}；信号关闭、锁闭保持', instance['route_id'])
                    continue
                self._complete_reference_cancel(session, instance)
            elif instance['status'] == 'track_proving' and now >= instance['signal_open_due']:
                fact = self._blocking_fact(session, self.routes[instance['route_id']], instance['id'])
                if fact:
                    instance['status'] = 'closed_locked'
                    self._close_route_signals(session, instance)
                    self._event(session, 'route_setting_failed', f'信号开放检查未通过：{fact[1]}；锁闭保持', instance['route_id'])
                else:
                    self._open_reference_signals(session, instance)
                instance.pop('signal_open_due', None)

    def _complete_reference_cancel(self, session, instance):
        pending = instance.pop('cancel_pending')
        definition = self.routes[instance['route_id']]
        signal = pending['signal']
        if session.signals[signal].get('instance_id') == instance['id']:
            session.signals[signal].update(aspect=None, route=None, instance_id=None, close_reason='CANCELLED')
        if pending['child']:
            instance.setdefault('cancelled_subroutes', []).append(pending['child'])
            retained = [self.routes[cid] for cid in definition['subroutes']
                        if cid not in instance['cancelled_subroutes']]
            keep_sections = {name for child in retained for name in child['sections']}
            keep_switches = {sid for child in retained for sid in child['switches']}
            for name in instance['sections']:
                if name not in keep_sections:
                    instance['remaining'].discard(name)
                    session.sections[name]['owners'].discard(instance['id'])
            for sid in instance['switches']:
                if sid not in keep_switches:
                    session.switches[sid]['owners'].discard(instance['id'])
            instance['status'] = 'closed_locked' if retained else 'cancelled'
        else:
            instance['status'] = 'cancelled'
            self._close_route_signals(session, instance)
        if instance['status'] == 'cancelled':
            for obj in [*session.sections.values(), *session.switches.values()]:
                obj['owners'].discard(instance['id'])
            instance.update(remaining=set(), release_due={}, display_sections=[])
        self._event(session, 'route_cancel_complete', f'{signal} 取消段信号关闭，对应锁闭已释放', instance['route_id'])
