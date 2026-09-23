// A usage error is the caller's mistake — an unknown command, an unknown flag,
// a missing value — not a failed operation. It carries its own exit code so a
// script can tell "you called me wrong" from "the work failed".
export class UsageError extends Error {
  constructor(message) {
    super(message);
    this.name = 'UsageError';
  }
}


// Flags are declared per command rather than scanned loosely. The installers
// used to look for the flags they knew with `args.includes(...)` and silently
// ignore everything else, so a typo like `--forcee` ran the command as if the
// flag had not been passed at all.
//
// The spec comes from the command registry: `boolean`, `value` and
// `repeatable` are flag tokens including their leading dashes, and `positional`
// bounds the non-flag arguments.
export function parseFlags(args, spec = {}) {
  const boolean = new Set(spec.boolean ?? []);
  const value = new Set(spec.value ?? []);
  const repeatable = new Set(spec.repeatable ?? []);
  const positionalSpec = spec.positional ?? {};
  const { min = 0, max = 0 } = positionalSpec;
  const flags = {};
  const positionals = [];

  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (!arg.startsWith('--')) {
      positionals.push(arg);
      continue;
    }
    const separator = arg.indexOf('=');
    const name = separator === -1 ? arg : arg.slice(0, separator);
    if (boolean.has(name)) {
      if (separator !== -1) {
        throw new UsageError(`${name} does not take a value`);
      }
      flags[name] = true;
      continue;
    }
    if (!value.has(name)) {
      throw new UsageError(`Unknown option: ${name}`);
    }
    let flagValue;
    if (separator !== -1) {
      flagValue = arg.slice(separator + 1);
    } else {
      flagValue = args[index + 1];
      index += 1;
    }
    if (flagValue === undefined || flagValue === '' || flagValue.startsWith('--')) {
      throw new UsageError(`Missing value for ${name}`);
    }
    if (repeatable.has(name)) {
      flags[name] = [...(flags[name] ?? []), flagValue];
    } else {
      flags[name] = flagValue;
    }
  }

  if (positionals.length < min) {
    throw new UsageError(`Missing required argument: ${positionalSpec.name ?? 'argument'}`);
  }
  if (positionals.length > max) {
    throw new UsageError(`Unexpected argument: ${positionals[max]}`);
  }
  return { flags, positionals };
}


// Pull one value-carrying flag out of argv and hand the rest through untouched.
// `host add` needs the host's component before it can pick an installer, but
// every other flag belongs to that installer and has to reach it verbatim —
// re-serializing a parsed flag set would silently drop whatever the parser
// here does not know about.
export function extractValueFlag(args, name) {
  const rest = [];
  let value = null;
  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === name || arg.startsWith(`${name}=`)) {
      const inline = arg === name ? null : arg.slice(name.length + 1);
      const candidate = inline ?? args[index + 1];
      if (candidate === undefined || candidate === '' || candidate.startsWith('--')) {
        throw new UsageError(`Missing value for ${name}`);
      }
      value = candidate;
      if (inline === null) {
        index += 1;
      }
      continue;
    }
    rest.push(arg);
  }
  return { value, rest };
}
