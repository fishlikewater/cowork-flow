import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { templateRoot } from './paths.js';


export const hostAssetManifestPath = process.env.COWORK_FLOW_HOST_ASSET_MANIFEST
  || join(
    templateRoot,
    '.cowork-flow',
    'spec',
    'runtime',
    'host-assets.json'
  );

const REQUIRED_HOST_NEUTRAL_CAPABILITIES = [
  'task_action',
  'subagent_dispatch',
  'file_write',
  'party_board_action'
];
const REQUIRED_CAPABILITY_MATRIX_HOSTS = [
  'codex',
  'claude-code',
  'opencode',
  'zcode'
];
const CAPABILITY_STATUS_VALUES = [
  'native',
  'shim',
  'plugin',
  'external',
  'experimental',
  'unsupported'
];
const CAPABILITY_DECLARATION_KEYS = ['status', 'fallback'];
const COMMAND_TARGET_KEYS = ['config', 'format', 'target'];
const COMMAND_TARGET_FORMATS = ['json', 'toml', 'yaml'];
const MANIFEST_KEYS = [
  'schemaVersion',
  'capabilityValues',
  'capabilityMatrix',
  'platforms',
  'excludedPrefixes',
  'syncPolicy'
];
const PLATFORM_KEYS = [
  'id',
  'displayName',
  'aliases',
  'detectAny',
  'assetPrefixes',
  'assetFiles',
  'skillTarget',
  'adapterPath',
  'capabilities',
  'commandTargets'
];
const SYNC_POLICY_KEYS = [
  'protectedFiles',
  'protectedPrefixes',
  'safeFiles',
  'safePrefixes',
  'managedBlockFiles',
  'obsoleteFiles'
];


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
  const capabilityMatrix = normalizeCapabilityMatrix(manifest.capabilityMatrix);
  const syncPolicy = {
    protectedFiles: manifest.syncPolicy.protectedFiles.map(normalizePath),
    protectedPrefixes: manifest.syncPolicy.protectedPrefixes.map(normalizePath),
    safeFiles: manifest.syncPolicy.safeFiles.map(normalizePath),
    safePrefixes: manifest.syncPolicy.safePrefixes.map(normalizePath),
    managedBlockFiles: manifest.syncPolicy.managedBlockFiles.map(normalizePath),
    obsoleteFiles: manifest.syncPolicy.obsoleteFiles.map(normalizePath)
  };
  const assetPrefixes = unique(
    platforms.flatMap((platform) => platform.assetPrefixes)
  );
  const skillTargets = unique(
    platforms
      .map((platform) => platform.skillTarget)
      .filter(
        (value) => typeof value === 'string' && value.length > 0
      )
      .map(normalizePath)
  );
  const protectedFiles = new Set(syncPolicy.protectedFiles);
  const safeFiles = new Set(syncPolicy.safeFiles);
  const managedBlockFiles = new Set(syncPolicy.managedBlockFiles);

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
    const owners = assetOwners(normalized);
    if (owners.length === 0) {
      return true;
    }
    return owners.some(
      (platformId) => selectedPlatforms.includes(platformId)
    );
  }

  function assetOwners(relativePath) {
    const normalized = normalizePath(relativePath);
    return platforms
      .filter((platform) => ownsAsset(platform, normalized))
      .map((platform) => platform.id);
  }

  function isKnownPlatformAsset(relativePath) {
    return assetOwners(relativePath).length > 0;
  }

  function isSafeSyncFile(relativePath) {
    const normalized = normalizePath(relativePath);
    return safeFiles.has(normalized)
      || syncPolicy.safePrefixes.some((prefix) => normalized.startsWith(prefix))
      || assetPrefixes.some((prefix) => normalized.startsWith(prefix))
      || skillTargets.some((target) => normalized.startsWith(`${target}/`))
      || normalized.endsWith('/.gitkeep');
  }

  function isProtectedSyncFile(relativePath) {
    const normalized = normalizePath(relativePath);
    if (safeFiles.has(normalized)) {
      return false;
    }
    return protectedFiles.has(normalized)
      || syncPolicy.protectedPrefixes.some((prefix) => normalized.startsWith(prefix));
  }

  function isManagedBlockFile(relativePath) {
    return managedBlockFiles.has(normalizePath(relativePath));
  }

  function obsoleteSyncFiles() {
    return [...syncPolicy.obsoleteFiles].sort((left, right) => {
      if (left.length !== right.length) {
        return left.length - right.length;
      }
      return left.localeCompare(right);
    });
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
    capabilityMatrix,
    syncPolicy,
    assetPrefixes,
    skillTargets,
    parsePlatformSelection,
    shouldInclude,
    assetOwners,
    detectInstalledPlatforms,
    platform(platformId) {
      return byId.get(platformId) ?? null;
    },
    platformLabel(platformId) {
      return byId.get(platformId)?.displayName ?? platformId;
    },
    hostCapability(hostId, capability) {
      return capabilityMatrix.hosts[hostId]?.[capability] ?? null;
    },
    skillDestination(platformId) {
      return byId.get(platformId)?.skillTarget ?? null;
    },
    isKnownPlatformAsset,
    isSafeSyncFile,
    isProtectedSyncFile,
    isManagedBlockFile,
    obsoleteSyncFiles
  };
}


function ownsAsset(platform, normalizedPath) {
  return platform.assetFiles.includes(normalizedPath)
    || platform.assetPrefixes.some(
      (prefix) => normalizedPath.startsWith(prefix)
    );
}


function validateManifest(manifest) {
  if (!manifest || typeof manifest !== 'object' || Array.isArray(manifest)) {
    throw new Error('Host Asset Manifest must be an object');
  }
  assertKnownKeys(manifest, MANIFEST_KEYS, 'Host Asset Manifest');
  if (manifest.schemaVersion !== 1) {
    throw new Error(
      `Unsupported Host Asset Manifest schemaVersion: ${manifest.schemaVersion}`
    );
  }
  const allowed = validateCapabilityValues(manifest.capabilityValues);
  if (!Array.isArray(manifest.platforms) || manifest.platforms.length === 0) {
    throw new Error(
      'Host Asset Manifest platforms must be a non-empty array'
    );
  }
  const platformIds = [];
  const seenPlatformIds = new Set();
  const aliases = new Map();
  for (const platform of manifest.platforms) {
    validatePlatform(platform, allowed, seenPlatformIds, aliases);
    platformIds.push(platform.id);
  }
  validateStringArray(
    manifest.excludedPrefixes,
    'Host Asset Manifest excludedPrefixes'
  );
  validateCapabilityMatrix(manifest.capabilityMatrix, allowed, platformIds);
  validateSyncPolicy(manifest.syncPolicy);
}

function validateCapabilityValues(values) {
  validateStringArray(
    values,
    'Host Asset Manifest capabilityValues',
    { unique: true }
  );
  if (!arraysEqual(values, CAPABILITY_STATUS_VALUES)) {
    throw new Error(
      `Host Asset Manifest capabilityValues must be ${CAPABILITY_STATUS_VALUES.join(', ')}`
    );
  }
  return new Set(CAPABILITY_STATUS_VALUES);
}

function validatePlatform(platform, allowed, seenPlatformIds, aliases) {
  if (!platform || typeof platform !== 'object' || Array.isArray(platform)) {
    throw new Error('Every host platform must be an object');
  }
  assertKnownKeys(platform, PLATFORM_KEYS, `Host platform ${platform.id ?? '<unknown>'}`);
  validateRequiredString(platform.id, 'Host platform id');
  if (seenPlatformIds.has(platform.id)) {
    throw new Error(`Duplicate host platform id: ${platform.id}`);
  }
  seenPlatformIds.add(platform.id);
  validateRequiredString(platform.displayName, `Host platform ${platform.id} displayName`);
  validateStringArray(platform.aliases, `Host platform ${platform.id} aliases`);
  for (const alias of platform.aliases) {
    const normalized = alias.toLowerCase();
    const owner = aliases.get(normalized);
    if (owner !== undefined) {
      throw new Error(`Duplicate platform alias: ${alias}`);
    }
    aliases.set(normalized, platform.id);
  }
  validateStringArray(platform.detectAny, `Host platform ${platform.id} detectAny`);
  validateStringArray(platform.assetPrefixes, `Host platform ${platform.id} assetPrefixes`);
  validateStringArray(platform.assetFiles, `Host platform ${platform.id} assetFiles`);
  if (platform.skillTarget !== null && typeof platform.skillTarget !== 'string') {
    throw new Error(`Host platform ${platform.id} skillTarget must be a string or null`);
  }
  if (typeof platform.skillTarget === 'string' && platform.skillTarget.length === 0) {
    throw new Error(`Host platform ${platform.id} skillTarget must be a non-empty string or null`);
  }
  validateRequiredString(platform.adapterPath, `Host platform ${platform.id} adapterPath`);
  validatePlatformCapabilities(platform, allowed);
  if (!Array.isArray(platform.commandTargets)) {
    throw new Error(`Host platform ${platform.id} commandTargets must be an array`);
  }
  for (const target of platform.commandTargets) {
    validateCommandTarget(target, platform.id);
  }
}

function validatePlatformCapabilities(platform, allowed) {
  if (!platform.capabilities || typeof platform.capabilities !== 'object' || Array.isArray(platform.capabilities)) {
    throw new Error(`Host platform ${platform.id} capabilities must be an object`);
  }
  if (Object.keys(platform.capabilities).length === 0) {
    throw new Error(`Host platform ${platform.id} capabilities must be a non-empty object`);
  }
  for (const [name, value] of Object.entries(platform.capabilities)) {
    validateRequiredString(name, `Host platform ${platform.id} capability name`);
    if (typeof value !== 'string' || !allowed.has(value)) {
      throw new Error(`Host platform ${platform.id} illegal capability status ${name}=${value}`);
    }
  }
}

function validateCommandTarget(target, platformId) {
  if (!target || typeof target !== 'object' || Array.isArray(target)) {
    throw new Error(`Host platform ${platformId} commandTargets must be objects`);
  }
  assertKnownKeys(target, COMMAND_TARGET_KEYS, `Host platform ${platformId} commandTarget`);
  validateRequiredString(target.config, `Host platform ${platformId} commandTarget.config`);
  validateRequiredString(target.target, `Host platform ${platformId} commandTarget.target`);
  if (!COMMAND_TARGET_FORMATS.includes(target.format)) {
    throw new Error(`Host platform ${platformId} commandTarget.format must be json, toml, or yaml`);
  }
}

function validateSyncPolicy(syncPolicy) {
  if (!syncPolicy || typeof syncPolicy !== 'object' || Array.isArray(syncPolicy)) {
    throw new Error('Host Asset Manifest syncPolicy must be an object');
  }
  assertKnownKeys(syncPolicy, SYNC_POLICY_KEYS, 'Host Asset Manifest syncPolicy');
  for (const key of SYNC_POLICY_KEYS) {
    validateStringArray(
      syncPolicy[key],
      `Host Asset Manifest syncPolicy.${key}`
    );
  }
}

function validateCapabilityMatrix(matrix, allowed, platformIds) {
  if (!matrix || typeof matrix !== 'object' || Array.isArray(matrix)) {
    throw new Error('Host Asset Manifest capabilityMatrix must be an object');
  }
  assertKnownKeys(matrix, ['required', 'hosts'], 'Host Asset Manifest capabilityMatrix');
  validateStringArray(
    matrix.required,
    'Host Asset Manifest capabilityMatrix.required'
  );
  if (!arraysEqual(matrix.required, REQUIRED_HOST_NEUTRAL_CAPABILITIES)) {
    throw new Error(
      `Host Asset Manifest capabilityMatrix.required must be ${REQUIRED_HOST_NEUTRAL_CAPABILITIES.join(', ')}`
    );
  }
  if (!matrix.hosts || typeof matrix.hosts !== 'object' || Array.isArray(matrix.hosts)) {
    throw new Error('Host Asset Manifest capabilityMatrix.hosts must be an object');
  }
  const requiredHosts = new Set([
    ...REQUIRED_CAPABILITY_MATRIX_HOSTS,
    ...platformIds
  ]);
  for (const hostId of [...requiredHosts].sort()) {
    if (!matrix.hosts[hostId]) {
      throw new Error(`Host Asset Manifest capability matrix missing host: ${hostId}`);
    }
  }
  for (const [hostId, capabilities] of Object.entries(matrix.hosts)) {
    validateRequiredString(hostId, 'Host Asset Manifest capabilityMatrix host id');
    if (!capabilities || typeof capabilities !== 'object' || Array.isArray(capabilities)) {
      throw new Error(`Host Asset Manifest capabilityMatrix host ${hostId} must be an object`);
    }
    for (const key of Object.keys(capabilities)) {
      if (!REQUIRED_HOST_NEUTRAL_CAPABILITIES.includes(key)) {
        throw new Error(`Host Asset Manifest unknown host-neutral capability ${hostId}:${key}`);
      }
    }
    for (const capability of REQUIRED_HOST_NEUTRAL_CAPABILITIES) {
      validateCapabilityDeclaration(
        capabilities[capability],
        allowed,
        hostId,
        capability
      );
    }
  }
}

function validateCapabilityDeclaration(declaration, allowed, hostId, capability) {
  if (!declaration || typeof declaration !== 'object' || Array.isArray(declaration)) {
    throw new Error(`Host Asset Manifest missing host-neutral capability ${hostId}:${capability}`);
  }
  assertKnownKeys(
    declaration,
    CAPABILITY_DECLARATION_KEYS,
    `Host Asset Manifest capabilityMatrix.hosts.${hostId}.${capability}`
  );
  if (!allowed.has(declaration.status)) {
    throw new Error(
      `Host Asset Manifest illegal host-neutral capability ${hostId}:${capability}=${declaration.status}`
    );
  }
  if (declaration.fallback !== undefined && (
    typeof declaration.fallback !== 'string' || declaration.fallback.length === 0
  )) {
    throw new Error(
      `Host Asset Manifest capability fallback must be a non-empty string: ${hostId}:${capability}`
    );
  }
  if (declaration.status === 'unsupported' && !declaration.fallback) {
    throw new Error(
      `Host Asset Manifest unsupported capability requires fallback: ${hostId}:${capability}`
    );
  }
}

function validateRequiredString(value, label) {
  if (typeof value !== 'string' || value.length === 0) {
    throw new Error(`${label} must be a non-empty string`);
  }
}

function validateStringArray(value, label, { unique = false } = {}) {
  if (!Array.isArray(value)) {
    throw new Error(`${label} must be an array`);
  }
  const seen = new Set();
  for (const item of value) {
    if (typeof item !== 'string' || item.length === 0) {
      throw new Error(`${label} entries must be non-empty strings`);
    }
    if (unique && seen.has(item)) {
      throw new Error(`${label} entries must be unique: ${item}`);
    }
    seen.add(item);
  }
}

function assertKnownKeys(value, allowedKeys, label) {
  const allowed = new Set(allowedKeys);
  for (const key of Object.keys(value)) {
    if (!allowed.has(key)) {
      throw new Error(`${label} unknown field: ${key}`);
    }
  }
}

function normalizeCapabilityMatrix(matrix) {
  return {
    required: [...matrix.required],
    hosts: Object.fromEntries(
      Object.entries(matrix.hosts).map(([hostId, capabilities]) => [
        hostId,
        Object.fromEntries(
          Object.entries(capabilities).map(([capability, declaration]) => [
            capability,
            { ...declaration }
          ])
        )
      ])
    )
  };
}


function normalizePath(value) {
  return String(value).replaceAll('\\', '/');
}


function unique(values) {
  return [...new Set(values)];
}


function arraysEqual(left, right) {
  return Array.isArray(left)
    && left.length === right.length
    && left.every((value, index) => value === right[index]);
}


export const hostAssetManifest = loadHostAssetManifest();
export const hostRegistry = createHostRegistry(hostAssetManifest);
