import { readFile } from 'node:fs/promises';
import { join } from 'node:path';

import { packageRoot } from './paths.js';

const METADATA_PATH = join(packageRoot, 'presets', 'plugin-meta.json');

// One source for the identity every host shows. The three native manifests are
// projections of this file (test/plugin-metadata.test.js asserts the shipped
// bytes match), so a field can never be right in one host and stale in another.
export async function readPluginMetadata() {
  return JSON.parse(await readFile(METADATA_PATH, 'utf8'));
}

function hostLabel(metadata, host) {
  const label = metadata.hosts?.[host]?.label;
  if (!label) {
    throw new Error(`plugin metadata declares no label for host: ${host}`);
  }
  return label;
}

export function hostDescription(metadata, host) {
  return `${metadata.description}将 cowork-flow 的完整工作流带入 ${hostLabel(metadata, host)}。`;
}

export function pluginManifest(metadata, host, version) {
  const base = {
    name: metadata.name,
    version,
    description: hostDescription(metadata, host)
  };
  const author = metadata.author;

  if (host === 'codex') {
    return {
      ...base,
      author: { name: author.name, email: author.email, url: author.url },
      homepage: metadata.homepage,
      repository: metadata.repository,
      license: metadata.license,
      keywords: metadata.keywords,
      skills: './skills/',
      interface: {
        displayName: metadata.displayName,
        shortDescription: metadata.description,
        longDescription: metadata.longDescription,
        developerName: author.name,
        category: metadata.category,
        websiteURL: metadata.homepage
      }
    };
  }

  if (host === 'zcode') {
    // zcode's manifest display metadata maps author/authorUrl/homepage/version;
    // its display name comes from the marketplace listing, so none is declared
    // here. keywords is not part of the manifest schema either.
    return {
      ...base,
      author: { name: author.name, url: author.url },
      homepage: metadata.homepage,
      license: metadata.license,
      hooks: 'hooks/hooks.json',
      agents: 'agents',
      skills: 'skills'
    };
  }

  if (host === 'qoder') {
    return {
      ...base,
      displayName: metadata.displayName,
      author: { name: author.name, email: author.email, url: author.url },
      homepage: metadata.homepage,
      repository: metadata.repository,
      license: metadata.license,
      keywords: metadata.keywords,
      hooks: 'hooks/hooks.json',
      agents: 'agents',
      skills: 'skills'
    };
  }

  throw new Error(`plugin metadata projection has no rule for host: ${host}`);
}
