import React from 'react'
import useLiveData from '../hooks/useLiveData'

export default function Integrations() {
  const {data, error, refresh} = useLiveData('/integrations/adapters', 15000)
  return <div className="page-stack">
    <div className="page-heading"><div>
      <p className="eyebrow">Connectors</p><h1>Integrations and model discovery</h1>
      <p>Observe installed tools and configured models. Discovery cannot sign in, enable tools, or grant agent permissions.</p>
    </div><button onClick={refresh}>Refresh</button></div>
    {error && <p role="alert" className="notice error">{error}</p>}
    <section className="panel"><h2>Coding tools and engines</h2>
      <div className="grid-cards">{(data?.tools || []).map(tool =>
        <article className="card" key={tool.id}>
          <h3>{tool.name}</h3><p className="muted">{tool.protocol === 'acp' ? 'ACP adapter' : tool.protocol === 'native' ? 'Native adapter' : tool.protocol === 'http_api' ? 'HTTP engine' : 'CLI wrapper'}</p>
          <p><strong>{tool.installed ? 'Installed · Unverified' : 'Not installed'}</strong></p>
          <p className="muted">{tool.unavailable_reasons?.join('. ')}</p>
          <p className="muted">{tool.setup_hint}</p>
          {tool.documentation_url && <p><a href={tool.documentation_url} target="_blank" rel="noopener noreferrer">Official setup instructions</a></p>}
        </article>)}</div>
      {!data && !error && <p className="muted">Loading integration inventory…</p>}
    </section>
    <section className="panel"><h2>Configured models</h2>
      <p className="muted">A saved profile does not prove the provider is running or its model is available.</p>
      <div className="grid-cards">{(data?.models || []).map(model =>
        <article className="card" key={model.id}>
          <h3>{model.name}</h3><p className="muted">{model.provider} · {model.is_local ? 'Local' : 'Remote'} · {model.source}</p>
          <p><strong>Configured · Unverified</strong></p>
          <p className="muted">{model.unavailable_reasons?.join('. ')}</p>
        </article>)}</div>
      {data?.models?.length === 0 && <p className="muted">No configured model profiles were found.</p>}
    </section>
  </div>
}
