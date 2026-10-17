import React,{useState} from 'react'
import api from '../api'
import useLiveData from '../hooks/useLiveData'

export default function PaymentAccounts(){
 const {data,refresh,error}=useLiveData('/payments/settings',15000)
 const [mode,setMode]=useState('test'),[key,setKey]=useState(''),[limit,setLimit]=useState(1000),[currency,setCurrency]=useState('usd'),[enabled,setEnabled]=useState(false),[notice,setNotice]=useState(''),[busy,setBusy]=useState(false)
 return <section className="panel"><h2>Linked payment accounts</h2>
  <p>Taking payments and buying things use different account permissions. This optional Stripe adapter creates payment intents on your receiving account. Buying from a store also needs that merchant's supported checkout adapter; a receiving account is not a universal shopping login.</p>
  <p>Provider: Stripe · {data?.has_credentials?'Credential stored':'Not connected'} · {data?.enabled?'Enabled':'Disabled'} · {data?.mode||'test'} mode.</p>
  {error&&<p role="alert">Payment settings could not be loaded.</p>}
  <form onSubmit={async e=>{e.preventDefault();setBusy(true);setNotice('');try{await api.put('/payments/settings',{mode,currency,max_amount_minor:Number(limit),enabled,api_key:key||null});setKey('');setNotice('Account settings saved. This does not make a payment.');refresh()}catch(err){setNotice(err.response?.data?.detail||'Account could not be saved.')}finally{setBusy(false)}}}>
   <label>Mode<select value={mode} onChange={e=>setMode(e.target.value)}><option value="test">Test · no real funds</option><option value="live">Live account</option></select></label>
   <label>Provider API credential<input type="password" autoComplete="off" value={key} onChange={e=>setKey(e.target.value)} placeholder="Enter here only; never paste into chat"/></label>
   <label>Currency<input pattern="[a-z]{3}" maxLength={3} value={currency} onChange={e=>setCurrency(e.target.value)}/></label>
   <label>Maximum per payment, in currency minor units<input type="number" min={1} max={100000000} value={limit} onChange={e=>setLimit(e.target.value)}/></label>
   <label><input type="checkbox" checked={enabled} onChange={e=>setEnabled(e.target.checked)}/>Enable this configured account</label>
   <button disabled={busy||!!error}>Save linked account</button>
  </form><p className="muted">Credentials stay encrypted on this Kingdom. Provider sign-in, account verification and payment authentication remain the provider's responsibility. Level 5 uses standing authorization within grants and this limit; lower levels require exact approval. Provider fees may apply.</p>
  {notice&&<p role="status">{notice}</p>}
 </section>
}
