// Host session variables point at the developer's own agent session. A test
// fixture that binds its own session must not inherit them: the runtime's
// environment layer outranks the fixture payload, so the hook would render the
// developer's live task instead of the fixture's and the assertions below it
// would be meaningless.
const HOST_SESSION_ENV = new Set([
  'ZCODE_SESSION_ID',
  'ZCODE_PROCESS_LABEL',
  'OPENCODE_SESSION_ID',
  'CLAUDE_SESSION_ID',
  'CLAUDE_CODE_SESSION_ID',
  'CODEX_SESSION_ID',
  'CODEX_THREAD_ID',
  'DSH_SESSION_ID',
  'QODER_SESSION_ID',
]);


export function isHostSessionEnv(key) {
  return key.startsWith('COWORK_FLOW_') || HOST_SESSION_ENV.has(key);
}


export function scrubHostSessionEnv(env = process.env) {
  return Object.fromEntries(
    Object.entries(env).filter(([key]) => !isHostSessionEnv(key))
  );
}
