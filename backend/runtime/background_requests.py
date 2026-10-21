"""Bounded browser-independent request advancement; no permission changes or blind retries."""
import asyncio


class BackgroundRequests:
    def __init__(self, service):
        self.service, self.active = service, {}

    def status(self):
        return {'active_request_ids': list(self.active), 'max_parallel': 1,
                'notice': 'Runs on this Kingdom server. Closing the browser does not stop work. Server restart requires review, not automatic replay.'}

    def start(self, ident):
        current = self.service().get(ident)
        if ident in self.active: return self.status()
        if self.active: raise ValueError('This Kingdom background slot is occupied')
        if current['status'] not in {'queued', 'ready'}: raise ValueError('Inspect retained evidence before continuing this request')
        self.service().update(ident, {'background_owner': 'server'}, expected={'queued', 'ready'})
        self.active[ident] = asyncio.create_task(self._run(ident))
        return self.status()

    async def _run(self, ident):
        loop = asyncio.get_running_loop()
        deadline = loop.time() + 310
        max_chunks = 6
        original_agent_session_id = None

        try:
            for chunk in range(max_chunks):
                remaining = deadline - loop.time()
                if remaining <= 0:
                    raise TimeoutError()

                service = self.service()

                await asyncio.wait_for(
                    service.run(ident),
                    timeout=remaining,
                )

                current = service.get(ident)
                status = current.get('status')
                agent_session_id = current.get('agent_session_id')

                if chunk == 0:
                    original_agent_session_id = agent_session_id
                elif agent_session_id != original_agent_session_id:
                    break

                if status != 'waiting_review':
                    break

                if current.get('error'):
                    break

                if current.get('pending_approvals'):
                    break

                if chunk + 1 >= max_chunks:
                    break

                if not original_agent_session_id:
                    break

                agent = service.agents.get(original_agent_session_id)
                if not agent:
                    break

                if agent.get('status') != 'ready':
                    break

                if agent.get('error'):
                    break

                if agent.get('pending'):
                    break

                if deadline - loop.time() <= 0:
                    raise TimeoutError()

        except (asyncio.CancelledError, TimeoutError):
            self.service().update(
                ident,
                {
                    'status': 'waiting_review',
                    'error': 'Background execution interrupted; inspect agent and tool checkpoints before resuming',
                },
                expected={'running'},
            )
        except Exception:
            self.service().update(
                ident,
                {
                    'status': 'failed',
                    'error': 'Background request failed; inspect retained checkpoints',
                },
                expected={'running'},
            )
        finally:
            self.active.pop(ident, None)

    async def stop(self):
        tasks = list(self.active.values())
        for task in tasks: task.cancel()
        if tasks: await asyncio.gather(*tasks, return_exceptions=True)