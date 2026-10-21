export function formatWait(seconds) {
 const value=Math.max(0,Math.floor(Number(seconds)||0))
 return value<60?`${value}s`:`${Math.floor(value/60)}m ${value%60}s`
}
export function activityStages(activity) {
 return [
  {label:'Saved request',state:'recorded'},
  {label:'Model response',state:activity.status==='thinking'?'waiting':activity.turns>0?'received':'not started'},
  {label:'Tool execution',state:activity.verified_actions>0?'receipts available':'not verified'},
  {label:'Independent tests',state:activity.independent_tests_verified?'verified':'not verified'}
 ]
}
