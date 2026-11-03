// Host session and project variables point at the developer's own agent
// session. A test fixture that binds its own session must not inherit them:
// the runtime's environment layer outranks the fixture payload, and hook shims
// resolve their project root from these hints, so the test would render the
// developer's live task instead of the fixture's.
const HOST_SESSION_ENV = new Set([
  'ZCODE_SESSION_ID',
  'ZCODE_PROCESS_LABEL',
  'ZCODE_PROJECT_DIR',
  'OPENCODE_SESSION_ID',
  'CLAUDE_SESSION_ID',
  'CLAUDE_CODE_SESSION_ID',
  'CLAUDE_PROJECT_DIR',
  'CODEX_SESSION_ID',
  'CODEX_THREAD_ID',
  'DSH_SESSION_ID',
  'QODER_SESSION_ID',
  'QODER_PROJECT_DIR',
  'QODER_WORKING_DIR',
]);


export function isHostSessionEnv(key) {
  return key.startsWith('COWORK_FLOW_') || HOST_SESSION_ENV.has(key);
}


export function scrubHostSessionEnv(env = process.env) {
  return Object.fromEntries(
    Object.entries(env).filter(([key]) => !isHostSessionEnv(key))
  );
}


// In-place variant for tests that mutate this process's environment (spawned
// children inherit it). Returns the removed values for a later restore.
export function removeHostSessionEnv(env = process.env) {
  const saved = {};
  for (const key of Object.keys(env)) {
    if (isHostSessionEnv(key)) {
      saved[key] = env[key];
      delete env[key];
    }
  }
  return saved;
}


export function restoreHostSessionEnv(saved, env = process.env) {
  // Restore means the pre-scrub state, so a host variable the test itself set
  // must be dropped rather than kept alongside the saved values.
  for (const key of Object.keys(env)) {
    if (isHostSessionEnv(key)) {
      delete env[key];
    }
  }
  Object.assign(env, saved);
}
