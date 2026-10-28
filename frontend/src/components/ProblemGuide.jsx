import React from 'react'
import useLiveData from '../hooks/useLiveData'

export default function ProblemGuide() {
  const {data,error}=useLiveData('/problems',10000)
  const open=(data?.incidents||[]).filter(item=>item.status==='open')
  return <section className="panel">
    <h2>Problem guide</h2>
    <p>Failures are linked to their original work and routed to an Apprentice role. Repair notes keep the normal planning, permission and independent test checks.</p>
    {error ? <p role="alert">Problem reports are unavailable. Check the original work list.</p> : !data ? <p>Reading problem reports…</p> : <>
      <p>{open.length} open reports. A routed report does not mean a worker has started or fixed it.</p>
      {data.capacity_reached && <p role="alert">The report limit has been reached. Review existing reports before adding more.</p>}
      {open.slice(0,12).map(item=><details key={item.id}><summary>{item.category.replaceAll('_',' ')} → {item.assigned_role}</summary>
        <p>{item.action}</p><p>Work reference: {item.correlation_id}</p><p>{item.work_id ? 'Repair note saved in the work list.' : 'Waiting to save a repair note.'}</p>
      </details>)}
      <p>Shows this Knight’s observations. Reliability targets and remote coverage require measured evidence.</p>
    </>}
  </section>
}
