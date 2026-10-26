import { hostRegistry } from '../lib/host-assets.js';
import { readPackageInfo } from '../lib/package-info.js';

export const INSPECT_SCHEMA_VERSION = 1;

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
      hosts.push({
        id: hostId,
        displayName: platform.displayName,
        component: componentName,
        ...normalizedRow(facts, cliVersion)
      });
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
  return `${row.id} (${row.displayName}, ${row.component}): ${row.status}${detail ? ` - ${detail}` : ''}\n`;
}
