import React from 'react'
import useLiveData from '../hooks/useLiveData'
export default function Routing() {
 const {data,error,updated} = useLiveData('/models',10000)
 return <div className="page-stack"><div className="page-heading"><div><p className="eyebrow">Model connections</p><h1>Routing</h1><p>Actual provider configuration and usage from the running model service.</p></div><span className="sync-note">{updated ? updated.toLocaleTimeString() : 'Loading…'}</span></div>{error && <p role="alert" className="notice error">{error}</p>}
  {data && <><div className="grid-cards"><div className="card"><div className="card-title">Selected provider</div><div className="card-value">{data.default_provider === 'disabled' ? 'Not configured' : data.default_provider}</div></div><div className="card"><div className="card-title">Requests this session</div><div className="card-value">{data.usage?.requests ?? 'Unavailable'}</div></div><div className="card"><div className="card-title">Tokens this session</div><div className="card-value">{data.usage ? data.usage.prompt_tokens + data.usage.completion_tokens : 'Unavailable'}</div></div></div>
   <section className="panel"><h2>Provider health</h2><div className="record-detail"><h3>Ollama</h3><pre>{JSON.stringify(data.ollama,null,2)}</pre></div><div className="record-detail"><h3>OpenAI-compatible server</h3><p>{data.openai_compatible?.configured ? 'Server address and credentials are configured.' : 'No server address and credentials are configured.'}</p></div><p className="muted">Latency and cost estimates are not measured here. Built-in text and syntax analysis work without an AI provider.</p></section></>}
 </div>
}
