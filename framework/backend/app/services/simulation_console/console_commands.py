"""Operator-console commands; permission checks live at the HTTP boundary."""
import os
from time import monotonic

from .commands import execute
from .runtime import SimulationError


SEALED_COMMANDS = {'MANUAL_UNLOCK_ROUTE', 'SIGNAL_SEAL', 'SIGNAL_UNSEAL', 'SIGNAL_LIGHT_OFF',
                   'SECTION_FAULT_UNLOCK', 'GUIDE_ARM', 'GUIDE_TOTAL_LOCK', 'GUIDE_TOTAL_UNLOCK',
                   'BLOCK_ACCIDENT_RESET', 'BLOCK_TOTAL_AUX', 'BLOCK_DEPARTURE_AUX', 'BLOCK_RECEPTION_AUX'}


def operate(service, session_id, owner_id, command, version):
    session = service._get(session_id, owner_id)
    with session.mutex:
        service._expire_selection(session)
        service._release_due(session)
        service._verify_version(session, version)
        kind, target = command['type'], command.get('target', '')
        if kind in SEALED_COMMANDS and command.get('pin') != os.getenv('SIMULATOR_TRAINING_PIN', '0000'):
            return service._reject(session, '教学操作口令不正确，命令未执行', reason_code='INVALID_PIN')
        if hasattr(service, 'operate_reference'):
            result = service.operate_reference(session, command)
            if result is not None:
                return result
            if kind in {'SWITCH_TOTAL_NORMAL', 'SWITCH_TOTAL_REVERSE'}:
                throats = {s['throat'] for s in service.package['signals']
                           if s['name'] in service._state(session)['guide_locks']}
                ids = target.split('/')
                if any(service.switch_defs.get(sid, {}).get('throat') in throats for sid in ids):
                    return service._reject(session, '引导总锁闭期间不能转换该咽喉道岔', reason_code='GUIDE_TOTAL_LOCKED')
        if kind in {'SIGNAL_SEAL', 'SIGNAL_UNSEAL', 'SIGNAL_LIGHT_ON', 'SIGNAL_LIGHT_OFF'}:
            state = session.signals.get(target)
            if state is None:
                return service._reject(session, '请选择本站信号机', reason_code='UNKNOWN_DEVICE')
            if kind == 'SIGNAL_LIGHT_OFF' and state.get('aspect') is not None:
                return service._reject(session, '开放信号不能执行灭灯', reason_code='SIGNAL_OPEN')
            field = 'sealed' if kind.startswith('SIGNAL_S') or kind == 'SIGNAL_UNSEAL' else 'lit'
            value = kind in {'SIGNAL_SEAL', 'SIGNAL_LIGHT_ON'}
            state[field] = value
            if kind == 'SIGNAL_SEAL':
                # Button sealing inhibits future input; it does not cancel an established route.
                message = f'{target} 按钮已封锁；原进路状态保持'
            else:
                message = f'{target}：'+{'SIGNAL_UNSEAL': '按钮解封', 'SIGNAL_LIGHT_ON': '点灯', 'SIGNAL_LIGHT_OFF': '灭灯'}[kind]
            service._event(session, kind, message)
            return {'accepted': True, 'message': message, 'snapshot': service._snapshot(session)}
        if kind == 'MANUAL_UNLOCK_ROUTE':
            route = session.routes.get(target)
            if not route or route['status'] in {'released', 'cancelled'}:
                return service._reject(session, '请选择仍锁闭的原进路', reason_code='ROUTE_NOT_LOCKED')
            if route.get('manual_release_due') is not None:
                return service._reject(session, '该进路已在人工解锁倒计时中', reason_code='UNLOCK_PENDING')
            occupied = [name for name in route['sections'] + route['protection_sections'] if session.sections[name]['occupied']]
            if occupied:
                return service._reject(session, '进路区段仍占用，不能开始人工解锁', reason_code='SECTION_OCCUPIED', devices=occupied)
            definition = next(item for item in service.package['signals'] if item['name'] == route['signal'])
            delay = definition.get('manual_unlock_seconds', 30 if route['kind'] != 'train' else 180)
            session.signals[route['signal']].update(aspect=None, route=None, close_reason='MANUAL_UNLOCK')
            route.update(status='manual_unlocking', manual_release_due=monotonic()+delay)
            service._event(session, 'manual_unlock_start', f'{route["signal"]} 关闭，人工解锁倒计时 {delay} 秒；锁闭保持', route['route_id'])
            return {'accepted': True, 'message': session.last_message, 'snapshot': service._snapshot(session)}
        return execute(service, session, command)
