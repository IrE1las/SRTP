"""Vehicle/fault inputs and their release sequences, isolated from lessons."""
from .clock import monotonic
from .console_segments import FINISHED


class ConsoleTracks:
    def _track_cleared(self, session, instance, name, now):
        # Successor proof can arrive repeatedly as the vehicle advances. It
        # must not restart an already-proved section's green/release timers.
        if name not in instance['remaining'] or name in instance['release_due']:
            return
        instance['release_due'][name] = now+3
        instance['display_sections'] = [n for n in instance.get('display_sections', []) if n != name]
        self._state(session).setdefault('clearing_sections', {})[name] = now+self.clear_display_seconds
        route = self.routes[instance['route_id']]
        for sid in self.section_defs[name]['switches']:
            if sid in route['path_switches']:
                self._state(session).setdefault('clearing_branches', {})[sid] = {
                    'branches': [0, 2 if route['path_switches'][sid] else 1], 'due': now+self.clear_display_seconds}

    def _observe_track(self, session, name, previous_kind, kind, now):
        for instance in list(session.routes.values()):
            if instance['status'] in FINISHED:
                continue
            for segment in self._segments(instance):
                if segment['status'] in FINISHED:
                    continue
                route = self._segment_definition(segment)
                path, approach = route['sections'], route['approach_section']
                approaches = route.get('approach_sections', [approach] if approach else [])
                protected = any(check['section'] == name and not any(
                    session.switches[sid]['position'] == pos for sid,pos in check['clear_if_any'].items())
                    for check in route.get('clearance_checks', []))
                if protected and kind in {'vehicle','fault'}:
                    self._close_segment(session, instance, segment, 'signal_close',
                                        f"{segment['signal']} 超限绝缘防护区段 {name} 占用，信号关闭；锁闭保持")
                if segment.get('manual_due') is not None and kind == 'vehicle' and name in path:
                    segment.pop('manual_due')
                    segment['status'] = 'closed_locked'
                    self._event(session, 'manual_unlock_intrusion', f"{segment['signal']} 人工解锁期间车辆进入内方，停止延时解锁，锁闭保持", instance['route_id'])
                if kind == 'fault' and name in path:
                    # A basic shunt may terminate in an occupied/faulty
                    # non-point section. Internal circuits still prove clear.
                    terminal_exception = instance['kind'] != 'train' and name == path[-1] and not self.section_defs[name]['switches']
                    if not terminal_exception and not instance['mode'].startswith('guide'):
                        self._close_segment(session, instance, segment, 'signal_close',
                                            f"{segment['signal']} 因 {name} 故障关闭；本基本段锁闭保持")
                if kind == 'vehicle' and name in path:
                    instance['release_due'].pop(name, None)
                    if name not in segment['seen']:
                        segment['seen'].append(name)
                    if name == path[0]:
                        segment['entered'] = True
                        instance['train_started'] = True
                    if segment['entered']:
                        instance['progress'] = max(instance['progress'], instance['sections'].index(name))
                        if instance['kind'] == 'train' and name == path[0]:
                            self._close_segment(session, instance, segment, 'train_signal_close',
                                                f"{segment['signal']} 列车进入内方，正常关闭；锁闭保持")
                    # A downstream occupied circuit is the successor proof
                    # for a section which has already cleared.
                    for index, old in enumerate(path[:-1]):
                        if old in segment['cleared'] and path[index+1] in segment['seen'] and segment['entered']:
                            self._track_cleared(session, instance, old, now)
                if previous_kind == 'vehicle' and kind == 'clear':
                    approach_clear = not any(session.sections[n]['occupied'] for n in approaches)
                    if name in approaches and approach_clear and segment['entered'] and instance['kind'] != 'train':
                        self._close_segment(session, instance, segment, 'train_signal_close',
                                            f"{segment['signal']} 接近区段出清，正常关闭；锁闭保持")
                    if name in path and name in segment['seen'] and segment['entered']:
                        if name not in segment['cleared']:
                            segment['cleared'].append(name)
                        index = path.index(name)
                        successor = index == len(path)-1 or path[index+1] in segment['seen']
                        if successor:
                            self._track_cleared(session, instance, name, now)
                            if name == instance['sections'][-1]:
                                instance['progress'] = len(instance['sections'])
                        elif index == 0 and any(session.sections[n].get('occupancy_kind') == 'vehicle' for n in approaches):
                            # The consist entered the first circuit, then
                            # returned into its approach without reaching the
                            # next circuit: retain proof until approach clears.
                            segment['return_candidate'] = True
                    if name in approaches and segment.get('return_candidate') and approach_clear:
                        if not any(session.sections[n]['occupied'] for n in path):
                            segment['return_due'] = now+3
                            self._close_segment(session, instance, segment, 'train_signal_close',
                                                f"{segment['signal']} 车列中途返回，信号关闭，等待返回解锁")
            self._sync_segment_status(session, instance)

    def _operate_track(self, session, command):
        if command['type'] not in {'SET_SECTION_OCCUPANCY', 'CLEAR_SECTION_OCCUPANCY'}:
            return None
        name = command['target']
        kind = 'clear' if command['type'] == 'CLEAR_SECTION_OCCUPANCY' else command.get('payload', {}).get('kind')
        if name not in session.sections or kind not in {'clear', 'vehicle', 'fault'}:
            return self._reject(session, '请选择有效区段和占用类型', reason_code='INVALID_OCCUPANCY')
        track = session.sections[name]
        previous = track.get('occupancy_kind', 'clear')
        track.update(occupied=kind != 'clear', occupancy_kind=kind, occupancy_origin='student_command')
        track.pop('simulation_instance_id', None)
        self._event(session, command['type'], f"{name}：{'出清' if kind == 'clear' else '车辆占用' if kind == 'vehicle' else '故障占用'}")
        self._observe_track(session, name, previous, kind, monotonic())
        self._advance_guide_holds(session, monotonic())
        return {'accepted': True, 'message': session.last_message, 'snapshot': self._snapshot(session)}

    def _advance_return_releases(self, session, now):
        for instance in session.routes.values():
            if instance['status'] in FINISHED:
                continue
            for segment in self._segments(instance):
                route = self._segment_definition(segment)
                if segment.get('return_due') is not None and now >= segment['return_due']:
                    names = route['sections'] + route.get('approach_sections', [route['approach_section']] if route['approach_section'] else [])
                    if not any(session.sections[n]['occupied'] for n in names):
                        self._finish_segment(session, instance, segment)
                        self._event(session, 'return_unlock_complete', f"{segment['signal']} 中途返回，基本段一次解锁", instance['route_id'])
                # A mate required mechanically, but outside the running path,
                # is released with the last traversed end of that pair.
            definition = self.routes[instance['route_id']]
            for sid in instance['switches']:
                mate = self.switch_defs[sid]['mate']
                group = {sid, mate} - {''}
                path_members = [p for p in group if p in definition['path_switches']]
                still_used = any(self.switch_defs[p]['section'] in instance['remaining'] for p in path_members)
                if path_members and not still_used and self.switch_defs[sid]['section'] not in instance['remaining']:
                    session.switches[sid]['owners'].discard(instance['id'])
