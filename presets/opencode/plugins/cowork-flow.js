// opencode plugin adapter for cowork-flow.
//
// opencode iterates EVERY export of this module and calls it as a plugin
// factory, then iterates the hooks object each one returns. So this file
// exports exactly one function and nothing else — the logic lives in
// ../cowork-flow/plugin-core.js. Re-exporting a helper from here crashes the
// host during bootstrap (test/opencode-plugin.test.js pins this).
import {
  buildInjectedDigest,
  buildRuntimeWorkflowState,
  editedFilePath,
  findRepoRoot,
  injectShellEnv,
  registerPayloadSkills,
  runEditSpecCheck
} from "../cowork-flow/plugin-core.js"

export const CoworkFlowPlugin = async () => {
  return {
    // Registers the payload's own skills directory when this file is the
    // machine-level install, and is a no-op for the project install, which has
    // no skills/ sibling. See registerPayloadSkills for why this works.
    "config": async (config) => {
      registerPayloadSkills(config)
    },
    "shell.env": async (input, output) => {
      injectShellEnv(input, output)
    },
    "experimental.chat.system.transform": async (input, output) => {
      output.system.push([buildInjectedDigest(input), buildRuntimeWorkflowState(input)].filter(Boolean).join("\n\n"))
    },
    "tool.execute.after": async (input, output) => {
      const filePath = editedFilePath(input)
      if (!filePath) {
        return
      }
      const warning = await runEditSpecCheck(findRepoRoot(input), filePath)
      if (warning) {
        output.output = [output.output, warning].filter(Boolean).join("\n")
      }
    },
  }
}
