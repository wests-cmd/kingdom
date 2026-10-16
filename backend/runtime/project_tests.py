"""Read-only test reports over existing governed, durable process tasks.

A passing report means the approved command reported a nonempty successful suite;
it does not certify source correctness, deployments or unattended authority.
"""
import re
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal


class ProjectTestDescriptor(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    project: Literal['threadmap', 'centipede', 'kingdom']
    source_revision: str = Field(pattern=r'^[0-9a-f]{40}$')
    runner: Literal['unittest', 'pytest']
    minimum_tests: int = Field(default=1, ge=1, le=100000)


def validate_metadata(metadata):
    descriptor = ProjectTestDescriptor.model_validate(metadata['project_test'])
    if metadata.get('tool') != 'process.run@1.0.0' or metadata.get('capability') != 'process.execute':
        raise ValueError('Project tests require the governed process.run tool and process.execute capability')
    # Never retry a command automatically: tests may have side effects.
    if metadata.get('max_attempts', 1) != 1:
        raise ValueError('Project test jobs require max_attempts=1')
    return descriptor


def report(task):
    spec = validate_metadata(task['metadata'])
    state = task['status'].lower()
    answer = dict(task_id=task['id'], project=spec.project, source_revision=spec.source_revision,
                  state=state, tests_passed=False, tests_run=None,
                  scope='Approved command test summary only; source revision is owner supplied, not independently attested')
    if state != 'completed':
        return answer
    results = (task.get('result') or {}).get('results', [])
    if len(results) != 1:
        return dict(answer, state='evidence_missing')
    item = results[0]
    outcome = item.get('outcome', {})
    if (item.get('status') != 'completed' or item.get('verification', {}).get('state') != 'VERIFIED'
            or outcome.get('kind') != 'native_tool' or outcome.get('tool') != 'process.run@1.0.0'):
        return dict(answer, state='evidence_missing')
    from backend.runtime.computer_tools import verify_receipt
    try:
        verify_receipt(task, outcome)
    except (ValueError, OSError, KeyError, TypeError):
        return dict(answer, state='evidence_invalid')
    output = outcome.get('output', {})
    if output.get('exit_code') != 0:
        return dict(answer, state='process_failed')
    if output.get('output_truncated') is not False:
        return dict(answer, state='summary_unavailable')
    text = output.get('output', '')
    if not isinstance(text, str):
        return dict(answer, state='summary_unavailable')
    if spec.runner == 'unittest':
        matches = re.findall(r'^Ran (\d+) tests? in [^\r\n]+\r?\n\s*\r?\nOK(?: \(skipped=(\d+)\))?\s*\Z', text, re.M)
        count = max(0, int(matches[0][0]) - int(matches[0][1] or 0)) if len(matches) == 1 else 0
    else:
        # Require the final pytest summary, with no failing/error/xpass components.
        summary = text.strip().splitlines()[-1] if text.strip() else ''
        matches = re.fullmatch(r'=*\s*(\d+) passed(?:, \d+ (?:skipped|deselected|xfailed|warnings?))* in [\d.]+s\s*=*', summary)
        count = int(matches[1]) if matches else 0
    answer['tests_run'] = count
    return dict(answer, state='tests_passed' if count >= spec.minimum_tests else 'no_nonempty_passing_suite',
                tests_passed=count >= spec.minimum_tests)
