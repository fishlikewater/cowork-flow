// opencode plugin adapter for cowork-flow.
//
// opencode calls EVERY export of this module as a plugin
// factory and then every hook of the object it returns, so
// this file exports exactly one function and nothing else;
// the logic lives in ../cowork-flow/plugin-core.js. A
// re-exported helper would be called as a plugin and break
// host bootstrap.
import {
  injectShellEnv,
  registerPayloadSkills,
  renderViaInject
} from "../cowork-flow/plugin-core.js"

export const CoworkFlowPlugin = async () => {
  return {
    // Registers the payload skills directory for the
    // machine-level install, and is a no-op for the
    // project install, which has no skills/ sibling.
    "config": async (config) => {
      registerPayloadSkills(config)
    },
    "shell.env": async (input, output) => {
      injectShellEnv(input, output)
    },
    // The injection itself: the shim forwards the event to
    // the project's Python runtime (inject.py --host
    // opencode) and pushes whatever it printed into the
    // system transform. A missing/failing runtime stays
    // silent and never breaks prompt assembly.
    "experimental.chat.system.transform": async (input, output) => {
      const text = await renderViaInject(input)
      if (text) {
        output.system.push(text)
      }
    },
  }
}
