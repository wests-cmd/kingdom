// Provider-neutral request; provider-specific reasoning belongs to the saved profile.
export function parallelChatRequest(messages) {
  return {messages, stream:false, max_tokens:1024, temperature:0}
}
