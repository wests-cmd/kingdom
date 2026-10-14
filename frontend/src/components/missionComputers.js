export const canChooseComputer = step => ['text_check','python_check'].includes(step.kind)

export function eligibleMissionComputers(nodes) {
  return (nodes || []).filter(node => !node.is_local &&
    ['APPROVED','CONNECTED'].includes(node.node_state) &&
    (node.granted_capabilities || []).includes('compute'))
}

export function setStepComputer(step,computerId) {
  if (!canChooseComputer(step)) return step
  const next={...step}
  if(computerId) next.computer_id=computerId
  else delete next.computer_id
  return next
}
