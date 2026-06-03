export const CoworkFlowPlugin = async () => {
  return {
    "experimental.chat.system.transform": async (_input, output) => {
      output.system.push(`<cowork-runtime host="opencode" adapter="opencode.task">
COWORK_ENTRY_CONTRACT_V1
Classify structured COWORK_DELEGATION_V1 and COWORK_DISPATCH_V1 envelopes before workflow recovery.
UNKNOWN entries must not start, resume, archive, commit, or dispatch subagents.
DELEGATED_SOFT entries are advisory and cannot complete Implement or Check.
</cowork-runtime>`)
    },
  }
}
