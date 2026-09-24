import { readFile, rename, rm, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

import { hostRegistry } from './host-assets.js';


// The payload declaration in the host asset manifest is the single source for
// where a plugin payload lives inside the package and what its manifest is
// called. Machine install locations stay in the installers: this declaration
// ships into projects, which cannot resolve them.
export function pluginPayload(host) {
  const payload = hostRegistry.platformPayload(host);
  if (!payload?.manifest) {
    throw new Error(
      `Host platform ${host} declares no plugin payload manifest; `
      + 'only payload-hosting hosts have an install command'
    );
  }
  return payload;
}


// For a host whose plugin format carries no manifest at all: the installer still
// resolves its directory from the same declaration, but there is nothing to
// stamp a version into. This deliberately does not go through `pluginPayload()`
// — that function refusing a manifestless payload is what stops a
// version-stamping installer from silently skipping its stamp.
export function payloadSourceDir(host) {
  const payload = hostRegistry.platformPayload(host);
  if (!payload) {
    throw new Error(
      `Host platform ${host} declares no plugin payload; `
      + 'only payload-hosting hosts have an install command'
    );
  }
  return payload.sourceDir;
}


// The host records a version for the installed payload, so every plugin
// installer stamps the installed manifest with the package version — otherwise
// a payload installed from a checkout keeps whatever version its source
// manifest happened to carry. Written the way scripts/release.sh stamps it
// (key order preserved, two-space indent, trailing newline) so the two agree
// byte for byte, and renamed into place so a partially written manifest is
// never readable.
export async function stampPayloadManifest(dir, manifest, version) {
  const manifestPath = join(dir, ...manifest.split('/'));
  let parsed;
  try {
    parsed = JSON.parse(await readFile(manifestPath, 'utf8'));
  } catch {
    throw new Error(`Plugin payload manifest missing or unreadable: ${manifestPath}`);
  }
  parsed.version = version;
  const temporaryPath = `${manifestPath}.tmp`;
  await writeFile(temporaryPath, `${JSON.stringify(parsed, null, 2)}\n`, 'utf8');
  try {
    await rename(temporaryPath, manifestPath);
  } catch (error) {
    await rm(temporaryPath, { force: true });
    throw error;
  }
  return manifestPath;
}
