import { readFile } from 'node:fs/promises';
import { join } from 'node:path';

import { packageRoot } from './paths.js';

const METADATA_PATH = join(packageRoot, 'presets', 'plugin-meta.json');

// One source for the identity every host shows: the
// shipped manifests are projections of this file and
// test/plugin-metadata.test.js compares their bytes, so a
// field cannot be right in one host and stale in another.
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

// ZCode renders a marketplace icon only when the value is
// an absolute https URL (its client keeps the string only
// if it starts with `https://`), so the icon is fetched
// from somewhere public rather than read out of the
// payload.
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

function codexManifest(metadata, base) {
  const author = metadata.author;
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
      // codex resolves these against the plugin root; the
      // payload is copied into $CODEX_HOME alone, so the
      // mark ships inside it. brandColor is the value the
      // raster is baked from.
      logo: './assets/logo.svg',
      brandColor: metadata.brandColor
    }
  };
}

// zcode maps author/authorUrl/homepage/version from the
// manifest; its display name comes from the marketplace
// listing, so none is declared here, and keywords is not
// part of the schema either.
function zcodeManifest(metadata, base) {
  const author = metadata.author;
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

function qoderManifest(metadata, base) {
  const author = metadata.author;
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

// A skills-directory plugin. Only skills ship: the
// project's own settings hook and `.claude/agents/` stay
// the delivery for injection and subagents, because a
// plugin hook would fire next to the project hook (Claude
// Code stacks hook sources) and plugin agents would
// duplicate the project ones under a second name.
function claudeCodeManifest(metadata, base) {
  const author = metadata.author;
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

// A local-directory plugin, verified against the host
// bundle (Kimi Code 1.0.3 manifest.ts): `name` is the only
// required field, a `skills` entry must start with "./" or
// the host records the plugin as errored with zero skills,
// the display name lives under `interface`, and unread
// keys are dropped without a diagnostic.
// `sessionStart.skill` is what loads that Skill at session
// start. Only skills ship: injection stays on the
// config.toml hook route, because the host runs a plugin
// hook with `cwd` pinned to the plugin root (the hook
// schema is strict, so a plugin cannot override it) and
// the shipped shim cannot walk up to a project, exiting 0.
// The three fixed subagents stay project-level: plugin
// agents have the lowest priority and would be shadowed.
// The schema has no icon key.
function kimiCodeManifest(metadata, base) {
  const author = metadata.author;
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

const HOST_MANIFESTS = {
  codex: codexManifest,
  zcode: zcodeManifest,
  qoder: qoderManifest,
  'claude-code': claudeCodeManifest,
  'kimi-code': kimiCodeManifest
};

export function pluginManifest(metadata, host, version) {
  // Resolve the description first so an unknown host fails
  // on the missing label, not on the missing projection.
  const description = hostDescription(metadata, host);
  const projection = HOST_MANIFESTS[host];
  if (!projection) {
    throw new Error(`plugin metadata projection has no rule for host: ${host}`);
  }
  return projection(metadata, { name: metadata.name, version, description });
}
