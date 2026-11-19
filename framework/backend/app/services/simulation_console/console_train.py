"""Free-console vehicle movement along proved paths, on insulated DG boundaries."""
from .clock import monotonic


class ConsoleTrain:
    train_step_seconds = 2.0
    clear_display_seconds = 1.0

    def _train_problem(self, session, instance):
        if instance['status'] in {'setting', 'track_proving', 'cancelling', 'clearing',
                                  'released', 'cancelled', 'closed_locked', 'manual_unlocking'}:
            return 'ROUTE_NOT_RUNNABLE', '当前进路状态不能模拟行车'
        if instance.get('cancel_pending'):
            return 'CANCEL_PENDING', '进路取消中，不能模拟行车'
        if any(s.get('manual_due') for s in self._segments(instance)):
            return 'UNLOCK_PENDING', '人工解锁期间不能模拟行车'
        current = instance.get('vehicle_sections', [])
        if any(session.sections[n].get('occupancy_kind') == 'fault' for n in current):
            return 'TRACK_FAULT', '车辆所在区段故障，自动行车已暂停'
        route = self.routes[instance['route_id']]
        if any(not session.switches[sid]['represented'] or session.switches[sid].get('moving')
               or session.switches[sid]['position'] != route['path_switches'][sid]
               for n in current for sid in self.section_defs[n]['switches'] if sid in route['path_switches']):
            return 'SWITCH_UNREPRESENTED', '车辆路径道岔失去表示或位置不符，自动行车暂停'
        return None

    def _move_train(self, session, instance, now):
        problem = self._train_problem(session, instance)
        if problem:
            return self._reject(session, problem[1], reason_code=problem[0])
        route = self.routes[instance['route_id']]
        progress = instance['progress']
        groups = route['movement_groups']
        if progress == -2:
            following = [instance['approach_section']]
            next_progress = -1
        else:
            group = next((g for g in groups if max(instance['sections'].index(n) for n in g) > progress), [])
            following = list(group)
            next_progress = max((instance['sections'].index(n) for n in group), default=len(instance['sections']))
        for name in following:
            state = session.sections[name]
            for sid in self.section_defs[name]['switches']:
                if sid in route['path_switches'] and (not session.switches[sid]['represented']
                        or session.switches[sid].get('moving') or session.switches[sid]['position'] != route['path_switches'][sid]):
                    return self._reject(session, f'{sid} 道岔失去表示或位置不符，不能模拟通过；已有占用及锁闭保持',
                                        reason_code='SWITCH_UNREPRESENTED', devices=[sid])
            if any(name == self._segment_definition(part)['sections'][0] and part['status'] in {'closed_locked','manual_unlocking'}
                   for part in self._segments(instance)):
                return self._reject(session, '前方基本段信号关闭，不能模拟通过', reason_code='SEGMENT_SIGNAL_CLOSED')
            if state['occupied']:
                return self._reject(session, f'{name} 已占用，自动行车暂停；锁闭保持',
                                    reason_code='TRACK_FAULT' if state.get('occupancy_kind') == 'fault' else 'SECTION_OCCUPIED', devices=[name])
        previous = instance.get('vehicle_sections', [])
        if not following and not previous:
            return self._reject(session, '仿真车辆未进入进路，不能宣布出清', reason_code='NO_SIMULATED_TRAIN')
        for name in following:
            session.sections[name].update(occupied=True, occupancy_kind='vehicle', occupancy_origin='simulation',
                                          simulation_instance_id=instance['id'])
        clearing = self._state(session).setdefault('clearing_sections', {})
        masks = self._state(session).setdefault('clearing_branches', {})
        for name in previous:
            state = session.sections[name]
            # Never erase an externally injected fault or someone else's train.
            if state.get('simulation_instance_id') != instance['id'] or state.get('occupancy_kind') != 'vehicle':
                continue
            state.update(occupied=False, occupancy_kind='clear', occupancy_origin='simulation')
            state.pop('simulation_instance_id', None)
            clearing[name] = now + self.clear_display_seconds
            for sid in self.section_defs[name]['switches']:
                if sid in route['path_switches']:
                    masks[sid] = {'branches': [0, 2 if route['path_switches'][sid] else 1],
                                  'due': now+self.clear_display_seconds}
            if name in instance['sections']:
                instance['display_sections'] = [n for n in instance.get('display_sections', []) if n != name]
                instance['release_due'][name] = now + 3
        for name in following:
            self._observe_track(session, name, 'clear', 'vehicle', now)
        for name in previous:
            if not session.sections[name]['occupied']:
                self._observe_track(session, name, 'vehicle', 'clear', now)
        instance.update(progress=next_progress, train_started=True, vehicle_sections=following)
        instance['status'] = 'approaching' if progress == -2 else 'running' if following else 'clearing'
        # Train/guide signals close on first entry; shunt signals remain until
        # the simulated consist has cleared the first DG, then close.
        if progress != -2:
            for signal in route['segment_signals']:
                child = next((self.routes[c] for c in route['subroutes'] if self.routes[c]['signal'] == signal), route)
                entry = child['sections'][0]
                passed = entry in following if instance['kind'] == 'train' else entry in previous
                if passed or not following:
                    if session.signals[signal].get('instance_id') == instance['id']:
                        session.signals[signal].update(aspect=None, route=None, instance_id=None)
                        self._event(session, 'train_signal_close', f'{signal} 随车辆越过正常关闭，锁闭保持', route['id'])
        self._event(session, 'train_move' if following else 'train_exit',
                    f"车辆{'进入 '+ '、'.join(following) if following else '出清末端，等待正常解锁'}", route['id'])
        return {'accepted': True, 'message': session.last_message, 'snapshot': self._snapshot(session)}

    def step_train(self, session_id, owner_id, instance_id, version=None):
        """Compatibility endpoint; the page starts the automatic sequence."""
        session = self._get(session_id, owner_id)
        with session.mutex:
            self._release_due(session)
            self._verify_version(session, version)
            instance = session.routes.get(instance_id)
            if not instance:
                return self._reject(session, '进路实例不存在', reason_code='UNKNOWN_ROUTE')
            if instance.get('auto_running'):
                return self._reject(session, '该进路正在自动行车', reason_code='TRAIN_ALREADY_RUNNING')
            return self._move_train(session, instance, monotonic())

    def _start_train(self, session, command):
        instance = session.routes.get(command.get('payload', {}).get('route_instance_id'))
        if not instance or command['target'] not in [*instance['sections'], instance['approach_section']]:
            return self._reject(session, '该设备没有对应的行车进路', reason_code='ROUTE_TARGET_MISMATCH')
        if instance.get('auto_running'):
            return self._reject(session, '该进路已经在自动行车', reason_code='TRAIN_ALREADY_RUNNING')
        problem = self._train_problem(session, instance)
        if problem:
            return self._reject(session, problem[1], reason_code=problem[0])
        instance.update(auto_running=True, auto_due=monotonic()+self.train_step_seconds)
        self._event(session, 'train_start', '自动模拟行车已启动，每 2 秒前进一个实际轨道区段', instance['route_id'])
        return {'accepted': True, 'message': session.last_message, 'snapshot': self._snapshot(session)}

    def _advance_trains(self, session, now):
        for instance in session.routes.values():
            while instance.get('auto_running') and instance['auto_due'] <= now:
                due = instance['auto_due']
                result = self._move_train(session, instance, due)
                if not result['accepted'] or instance['status'] == 'clearing':
                    instance.update(auto_running=False, auto_due=None)
                else:
                    instance['auto_due'] = due + self.train_step_seconds
