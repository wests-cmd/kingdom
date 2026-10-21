// Local executions contain records; signed remote executions use one envelope.
export function taskEvidenceRecords(result) {
  if (Array.isArray(result?.results)) return result.results
  if (result?.output?.kind === 'native_tool' && typeof result.output.tool === 'string') {
    return [{outcome:result.output, verification:result.verification, executed_by:result.executed_by}]
  }
  return []
}

export function analysisSummary(record) {
  const outcome = record?.outcome || {}
  const verified = record?.verification?.state === 'VERIFIED'
  if (outcome.tool === 'text.analyze@1.0.0') {
    const words = Number.isInteger(outcome.output?.words) ? outcome.output.words : 'Unavailable'
    const characters = Number.isInteger(outcome.output?.characters) ? outcome.output.characters : 'Unavailable'
    return `${verified ? 'Verified text analysis' : 'Unverified text analysis'}: ${words} words; ${characters} characters.`
  }
  if (outcome.tool === 'code.python.analyze@1.0.0') {
    return `${verified && outcome.output?.valid_python === true ? 'Python syntax verified.' : 'Syntax has not been verified.'} Source code was analyzed without being executed.`
  }
  return null
}
