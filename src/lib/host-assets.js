import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { templateRoot } from './paths.js';


export const hostAssetManifestPath = join(
  templateRoot,
  '.cowork-flow',
  'spec',
  'runtime',
  'host-assets.json'
);


export function loadHostAssetManifest(path = hostAssetManifestPath) {
  const manifest = JSON.parse(readFileSync(path, 'utf8'));
  validateManifest(manifest);
  return manifest;
}


export function createHostRegistry(manifest) {
  validateManifest(manifest);
  const platforms = manifest.platforms.map((platform) => ({
    ...platform,
    aliases: [...platform.aliases],
    detectAny: [...platform.detectAny],
    assetPrefixes: platform.assetPrefixes.map(normalizePath),
    assetFiles: platform.assetFiles.map(normalizePath)
  }));
  const byId = new Map(platforms.map((platform) => [platform.id, platform]));
  const aliases = new Map();
  for (const platform of platforms) {
    for (const alias of platform.aliases) {
      const normalized = alias.toLowerCase();
      if (aliases.has(normalized)) {
        throw new Error(`Duplicate platform alias: ${alias}`);
      }
      aliases.set(normalized, platform.id);
    }
  }
  const platformIds = platforms.map((platform) => platform.id);
  const syncPolicy = {
    protectedFiles: manifest.syncPolicy.protectedFiles.map(normalizePath),
    protectedPrefixes: manifest.syncPolicy.protectedPrefixes.map(normalizePath),
    safeFiles: manifest.syncPolicy.safeFiles.map(normalizePath),
    safePrefixes: manifest.syncPolicy.safePrefixes.map(normalizePath),
    managedBlockFiles: manifest.syncPolicy.managedBlockFiles.map(normalizePath),
    obsoleteFiles: manifest.syncPolicy.obsoleteFiles.map(normalizePath)
  };

  function parsePlatformSelection(values) {
    const rawValues = Array.isArray(values) ? values : [values];
    const selected = new Set();
    for (const rawValue of rawValues) {
      const tokens = String(rawValue ?? '')
        .toLowerCase()
        .split(/[\s,;|+/]+/)
        .map((token) => token.trim())
        .filter(Boolean);
      for (const token of tokens) {
        if (token === 'all') {
          for (const platformId of platformIds) {
            selected.add(platformId);
          }
          continue;
        }
        const platformId = aliases.get(token);
        if (!platformId) {
          throw new Error(
            `Unsupported platform: ${token}. Supported platforms: ${platformIds.join(', ')}`
          );
        }
        selected.add(platformId);
      }
    }
    if (selected.size === 0) {
      throw new Error(
        `Platform selection required. Run: cowork-flow init <target> --platform ${platformIds.join('|')}`
      );
    }
    return platformIds.filter((platformId) => selected.has(platformId));
  }

  function shouldInclude(relativePath, selectedPlatforms) {
    const normalized = normalizePath(relativePath);
    if (
      manifest.excludedPrefixes.some(
        (prefix) => normalized.startsWith(normalizePath(prefix))
      )
    ) {
      return false;
    }
    const owners = platforms.filter((platform) => (
      platform.assetFiles.includes(normalized)
      || platform.assetPrefixes.some(
        (prefix) => normalized.startsWith(prefix)
      )
    ));
    if (owners.length === 0) {
      return true;
    }
    return owners.some(
      (platform) => selectedPlatforms.includes(platform.id)
    );
  }

  async function detectInstalledPlatforms(targetDir, pathExists) {
    const installed = [];
    for (const platform of platforms) {
      for (const marker of platform.detectAny) {
        if (await pathExists(join(targetDir, marker))) {
          installed.push(platform.id);
          break;
        }
      }
    }
    return installed;
  }

  return {
    manifest,
    platforms,
    platformIds,
    syncPolicy,
    assetPrefixes: unique(
      platforms.flatMap((platform) => platform.assetPrefixes)
    ),
    skillTargets: unique(
      platforms
        .map((platform) => platform.skillTarget)
        .filter(
          (value) => typeof value === 'string' && value.length > 0
        )
        .map(normalizePath)
    ),
    parsePlatformSelection,
    shouldInclude,
    detectInstalledPlatforms,
    platform(platformId) {
      return byId.get(platformId) ?? null;
    },
    platformLabel(platformId) {
      return byId.get(platformId)?.displayName ?? platformId;
    },
    skillDestination(platformId) {
      return byId.get(platformId)?.skillTarget ?? null;
    },
    isKnownPlatformAsset(relativePath) {
      const normalized = normalizePath(relativePath);
      return platforms.some((platform) => (
        platform.assetFiles.includes(normalized)
        || platform.assetPrefixes.some(
          (prefix) => normalized.startsWith(prefix)
        )
      ));
    }
  };
}


function validateManifest(manifest) {
  if (!manifest || typeof manifest !== 'object' || Array.isArray(manifest)) {
    throw new Error('Host Asset Manifest must be an object');
  }
  if (manifest.schemaVersion !== 1) {
    throw new Error(
      `Unsupported Host Asset Manifest schemaVersion: ${manifest.schemaVersion}`
    );
  }
  if (!Array.isArray(manifest.platforms) || manifest.platforms.length === 0) {
    throw new Error(
      'Host Asset Manifest platforms must be a non-empty array'
    );
  }
  if (!Array.isArray(manifest.excludedPrefixes)) {
    throw new Error(
      'Host Asset Manifest excludedPrefixes must be an array'
    );
  }
  if (!manifest.syncPolicy || typeof manifest.syncPolicy !== 'object') {
    throw new Error('Host Asset Manifest syncPolicy must be an object');
  }
  for (const platform of manifest.platforms) {
    if (!platform || typeof platform !== 'object' || !platform.id) {
      throw new Error('Every host platform must define an id');
    }
    for (const key of [
      'aliases',
      'detectAny',
      'assetPrefixes',
      'assetFiles',
      'commandTargets'
    ]) {
      if (!Array.isArray(platform[key])) {
        throw new Error(
          `Host platform ${platform.id} ${key} must be an array`
        );
      }
    }
  }
  for (const key of [
    'protectedFiles',
    'protectedPrefixes',
    'safeFiles',
    'safePrefixes',
    'managedBlockFiles',
    'obsoleteFiles'
  ]) {
    if (!Array.isArray(manifest.syncPolicy[key])) {
      throw new Error(
        `Host Asset Manifest syncPolicy.${key} must be an array`
      );
    }
  }
}


function normalizePath(value) {
  return String(value).replaceAll('\\', '/');
}


function unique(values) {
  return [...new Set(values)];
}


export const hostAssetManifest = loadHostAssetManifest();
export const hostRegistry = createHostRegistry(hostAssetManifest);
