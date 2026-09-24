import { readFile } from 'node:fs/promises';
import { join } from 'node:path';

import { packageRoot } from './paths.js';

const METADATA_PATH = join(packageRoot, 'presets', 'plugin-meta.json');

// One source for the identity every host shows. The host manifests are
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

// ZCode only renders a marketplace icon when the value is an absolute https URL
// (its client keeps the string only if `icon.startsWith('https://')`, and drops
// anything else without a warning), so the icon has to be fetched from somewhere
// public rather than read out of the payload. Deriving the URL keeps the repo
// and the branch stated once instead of hardcoded a fourth time.
export function marketplaceIconUrl(metadata) {
  const { repository, defaultBranch, icon } = metadata;
  const prefix = 'https://github.com/';
  if (typeof repository !== 'string' || !repository.startsWith(prefix)) {
    throw new Error(`plugin metadata repository is not a GitHub URL: ${repository}`);
  }
  if (typeof defaultBranch !== 'string' || defaultBranch.length === 0) {
    throw new Error('plugin metadata declares no defaultBranch to pin the icon URL to');
  }
  if (typeof icon?.raster !== 'string' || icon.raster.length === 0) {
    throw new Error('plugin metadata declares no icon.raster to publish');
  }
  const raw = 'https://raw.githubusercontent.com/' + repository.slice(prefix.length);
  return `${raw}/${defaultBranch}/${icon.raster}`;
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
        websiteURL: metadata.homepage,
        // codex resolves these against the plugin root, and the payload is
        // copied into $CODEX_HOME on its own, so the mark ships inside it.
        // brandColor is the same value the raster is baked from, so the mark
        // and the surrounding UI cannot disagree.
        logo: './assets/logo.svg',
        brandColor: metadata.brandColor
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

  if (host === 'claude-code') {
    // A skills-directory plugin: Claude Code loads any folder under a skills
    // directory that carries this manifest as `<name>@skills-dir`, with no
    // marketplace and no install record. Only skills ship here — the project's
    // own `.claude/settings.json` hook and `.claude/agents/` stay the delivery
    // for injection and subagents, because a plugin hook would fire alongside
    // the project hook (Claude Code stacks hook sources) and plugin agents
    // would duplicate the project ones under a second name. The manifest has no
    // icon key at all, so none is written.
    return {
      ...base,
      displayName: metadata.displayName,
      author: { name: author.name, email: author.email, url: author.url },
      homepage: metadata.homepage,
      repository: metadata.repository,
      license: metadata.license,
      keywords: metadata.keywords,
      skills: './skills/'
    };
  }

  if (host === 'kimi-code') {
    // A local-directory plugin. Verified against the host bundle (Kimi Code
    // 1.0.3, `packages/agent-core-v2/src/app/plugin/manifest.ts`): `name` is the
    // only required field; a `skills` entry must start with "./" or the host
    // records the plugin as errored with zero skills; the display name lives
    // under `interface`; every other key the parser does not read is dropped
    // without a diagnostic, so none is written here.
    //
    // `sessionStart.skill` is what makes the plugin useful in a repository
    // without a runtime: Kimi Code loads that Skill when a session starts. Only
    // skills ship. Injection stays with the config.toml hook route — the host
    // runs a plugin hook with `cwd` pinned to the plugin root (and the hook
    // schema is strict, so a plugin cannot override it), where the shipped shim
    // cannot walk up to a project and exits 0. The three fixed subagents stay
    // project-level because plugin agents have the lowest priority and would
    // always be shadowed. The schema has no icon key.
    return {
      ...base,
      author: { name: author.name, email: author.email },
      homepage: metadata.homepage,
      license: metadata.license,
      keywords: metadata.keywords,
      skills: './skills/',
      sessionStart: { skill: 'cowork-flow-bootstrap' },
      interface: {
        displayName: metadata.displayName,
        shortDescription: metadata.description,
        longDescription: metadata.longDescription,
        developerName: author.name,
        websiteURL: metadata.homepage
      }
    };
  }

  throw new Error(`plugin metadata projection has no rule for host: ${host}`);
}
