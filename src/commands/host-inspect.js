import { hostRegistry } from '../lib/host-assets.js';
import { readPackageInfo } from '../lib/package-info.js';

export const INSPECT_SCHEMA_VERSION = 2;

export const INSPECT_STATUSES = Object.freeze([
  'installed',
  'missing',
  'stale',
  'broken',
  'unsupported'
]);


function normalizedRow(facts, cliVersion) {
  const installed = facts.status === 'installed';
  const stale = installed && facts.version !== null && facts.version !== cliVersion;
  return {
    status: stale ? 'stale' : facts.status,
    version: facts.version ?? null,
    payloadPath: facts.payloadPath ?? null,
    detailPath: facts.detailPath ?? null,
    registeredSource: facts.registeredSource ?? null,
    enabled: facts.enabled ?? null,
    reason: stale
      ? `installed ${facts.version} but the CLI runs ${cliVersion}`
      : facts.reason ?? null
  };
}


// A component may install more than one user-level edition (today only
// qoder); its reader returns one facts object per present edition. Single
// edition components keep returning one object.
function componentFacts(facts) {
  return Array.isArray(facts) ? facts : [facts];
}


function unsupportedRow(hostId, componentName) {
  return {
    status: 'unsupported',
    version: null,
    payloadPath: null,
    detailPath: null,
    registeredSource: null,
    enabled: null,
    reason: `${hostId} component ${componentName} does not expose an installed-state reader`
  };
}


// Read-only aggregation. Each component owns its installation layout and
// exposes the facts; this module only normalizes them against the running CLI.
export async function inspectHosts(components, hostIds, { env = process.env } = {}) {
  const { version: cliVersion } = await readPackageInfo();
  const hosts = [];
  for (const hostId of hostIds) {
    const platform = hostRegistry.platform(hostId);
    const host = components[hostId];
    for (const [componentName, component] of Object.entries(host.components)) {
      // `all` is a composition of the components below it, not a separate
      // installed artifact.
      if (componentName === 'all') {
        continue;
      }
      const facts = typeof component.inspect === 'function'
        ? await component.inspect({ env })
        : unsupportedRow(hostId, componentName);
      for (const instance of componentFacts(facts)) {
        hosts.push({
          id: hostId,
          displayName: platform.displayName,
          component: componentName,
          ...normalizedRow(instance, cliVersion),
          ...(instance.variant ? { variant: instance.variant } : {})
        });
      }
    }
  }
  return {
    schemaVersion: INSPECT_SCHEMA_VERSION,
    cliVersion,
    hosts
  };
}


export function renderInspectLine(row) {
  const detail = [
    row.version ? `version ${row.version}` : null,
    row.detailPath || row.payloadPath,
    row.enabled === false ? 'not enabled' : null,
    row.reason
  ].filter(Boolean).join('; ');
  const name = row.variant === 'cn' ? `${row.displayName} CN` : row.displayName;
  return `${row.id} (${name}, ${row.component}): ${row.status}${detail ? ` - ${detail}` : ''}\n`;
}
