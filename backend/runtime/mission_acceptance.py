"""Acceptance dispatch for exact owner-reviewed mission steps, never model claims."""


def validated_acceptance(engine, mission_id, version, step_id):
    try:
        mission = engine.missions.get(mission_id)
        if (type(version) is not int or mission['version'] != version
                or mission['approved_version'] != version
                or mission['status'] not in {'running', 'completed'}):
            raise ValueError('Stale or unapproved mission')
        step = next(s for s in mission['plan']['steps'] if s['id'] == step_id)
        if step['kind'] == 'function_check':
            from backend.runtime.bounded_function_tests import validated_acceptance as bounded
            return bounded(engine, mission_id, version, step_id)
        if step['kind'] != 'project_test':
            raise ValueError('Unsupported acceptance step')
        from backend.runtime.missions import MissionPlan, validate_plan
        from backend.runtime.project_tests import report
        validate_plan(MissionPlan.model_validate(mission['plan']))
        task = engine.tasks.get(mission['steps'][step_id]['task_id'])
        metadata = task['metadata']
        from uuid import uuid5, NAMESPACE_URL
        mission_key = f'{mission_id}:{version}:{step_id}'
        if task['id'] != str(uuid5(NAMESPACE_URL, 'kingdom-mission:' + mission_key)):
            raise ValueError('Different acceptance task identity')
        for key, value in {'mission_id': mission_id, 'mission_version': version, 'step_id': step_id,
                           '_mission_step_key': mission_key,
                           'project_test': step['project_test'], 'max_attempts': 1,
                           'tool_parameters': {'argv': step['argv']}}.items():
            if metadata.get(key) != value:
                raise ValueError('Reviewed project test binding changed')
        if metadata.get('offload') or metadata.get('execution_target') == 'remote':
            raise ValueError('Project acceptance requires retained local evidence')
        if task['prompt'] != (step['instructions'] or step['title']):
            raise ValueError('Reviewed test prompt changed')
        result = report(task)
        if result['tests_passed'] is not True:
            raise ValueError('No verified nonempty passing project suite')
        return {**result, 'accepted': True, 'mission_id': mission_id,
                'mission_version': version, 'step_id': step_id}
    except (KeyError, TypeError, StopIteration, OSError, ValueError) as error:
        raise ValueError('No current independently verified mission acceptance') from error
