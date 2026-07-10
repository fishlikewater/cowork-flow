import { existsSync, readFileSync } from 'node:fs';
import { isAbsolute, join } from 'node:path';

import { templateRoot as defaultTemplateRoot } from './paths.js';


const KINDS = new Set(['phase', 'protocol', 'domain', 'mode', 'runtime']);
const VISIBILITIES = new Set(['public', 'internal']);
const ENTRY_STATUSES = new Set(['active', 'deprecated', 'disabled']);
const WORKFLOW_STATUSES = new Set([
  'no_task',
  'planning',
  'in_progress',
  'review',
  'completed',
  'delegated_subtask'
]);
const ENFORCEMENTS = new Set(['advisory', 'mandatory', 'runtime']);
const ID_PATTERN = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const INTENT_PATTERN = /^[a-z][a-z0-9_]*$/;
const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;
const REQUIRED_FIELDS = new Set([
  'id',
  'displayName',
  'aliases',
  'kind',
  'visibility',
  'status',
  'statuses',
  'intents',
  'enforcement',
  'runtimeGate',
  'runtimeCommand',
  'evidenceArtifact',
  'source',
  'managedPaths'
]);
const ALLOWED_FIELDS = new Set([
  ...REQUIRED_FIELDS,
  'readWhen',
  'replacement',
  'removeAfter'
]);


export class SkillRegistryError extends Error {
  constructor(message) {
    super(message);
    this.name = 'SkillRegistryError';
  }
}


export const skillRegistryPath = join(
  defaultTemplateRoot,
  '.cowork-flow',
  'spec',
  'runtime',
  'skill-registry.json'
);


export const skillRegistrySchemaPath = join(
  defaultTemplateRoot,
  '.cowork-flow',
  'spec',
  'schemas',
  'skill-registry.schema.json'
);


export function loadSkillRegistry(
  path = skillRegistryPath,
  options = {}
) {
  let raw;
  try {
    raw = JSON.parse(readFileSync(path, 'utf8'));
  } catch (error) {
    throw new SkillRegistryError(
      `unable to read Skill Registry ${path}: ${error.message}`
    );
  }
  return createSkillRegistry(raw, options);
}


export function createSkillRegistry(raw, options = {}) {
  const templateRoot = options.templateRoot ?? defaultTemplateRoot;
  validateRoot(raw);
  const entries = raw.entries
    .map((entry) => normalizeEntry(entry, templateRoot))
    .sort((left, right) => left.id.localeCompare(right.id));

  const byId = new Map();
  const aliases = new Map();
  const tokens = new Set();
  for (const entry of entries) {
    for (const token of [entry.id, ...entry.aliases]) {
      if (tokens.has(token)) {
        throw new SkillRegistryError(
          `duplicate skill id or alias: ${token}`
        );
      }
      tokens.add(token);
      if (token === entry.id) {
        byId.set(token, entry);
      } else {
        aliases.set(token, entry.id);
      }
    }
  }

  const publicIntents = new Set();
  for (const entry of entries) {
    if (entry.enforcement === 'mandatory' && !entry.runtimeGate) {
      throw new SkillRegistryError(
        `mandatory entry ${entry.id} requires runtimeGate`
      );
    }
    if (entry.runtimeGate) {
      const gate = byId.get(entry.runtimeGate);
      if (!gate || gate.kind !== 'runtime') {
        throw new SkillRegistryError(
          `runtimeGate ${entry.runtimeGate} must reference a runtime entry`
        );
      }
    }
    if (entry.kind === 'runtime') {
      if (
        entry.visibility !== 'internal'
        || entry.enforcement !== 'runtime'
      ) {
        throw new SkillRegistryError(
          `runtime entry ${entry.id} must be internal with runtime enforcement`
        );
      }
    } else if (entry.enforcement === 'runtime') {
      throw new SkillRegistryError(
        `non-runtime entry ${entry.id} cannot use runtime enforcement`
      );
    }
    if (entry.status === 'deprecated') {
      if (!entry.replacement || !entry.removeAfter) {
        throw new SkillRegistryError(
          `deprecated entry ${entry.id} requires replacement and removeAfter`
        );
      }
      if (!byId.has(entry.replacement) || entry.replacement === entry.id) {
        throw new SkillRegistryError(
          `deprecated entry ${entry.id} has invalid replacement: ${entry.replacement}`
        );
      }
    }
    if (entry.visibility === 'public' && entry.status === 'active') {
      for (const intent of entry.intents) {
        if (publicIntents.has(intent)) {
          throw new SkillRegistryError(
            `duplicate public intent: ${intent}`
          );
        }
        publicIntents.add(intent);
      }
    }
  }

  validateManagedPaths(entries);
  const normalized = {
    schemaVersion: 1,
    entries: entries.map((entry) => ({ ...entry }))
  };
  const publicEntries = entries.filter(
    (entry) => entry.visibility === 'public' && entry.status === 'active'
  );

  return {
    schemaVersion: 1,
    entries,
    normalized,
    publicEntries,
    publicSkillIds: publicEntries.map((entry) => entry.id),
    domainEntriesFor({ devType = null, paths = [] } = {}) {
      const normalizedDevType = typeof devType === 'string'
        ? devType.trim()
        : '';
      const normalizedPaths = paths.map(
        (path) => String(path).replaceAll('\\', '/').replace(/^\.\//, '')
      );
      return entries.filter((entry) => (
        entry.kind === 'domain'
        && entry.status === 'active'
        && (
          entry.readWhen.devTypes.includes(normalizedDevType)
          || normalizedPaths.some((path) => (
            entry.readWhen.pathPatterns.some(
              (pattern) => globMatches(path, pattern)
            )
          ))
        )
      ));
    },
    entry(idOrAlias) {
      if (typeof idOrAlias !== 'string') {
        return null;
      }
      const id = byId.has(idOrAlias)
        ? idOrAlias
        : aliases.get(idOrAlias);
      return id ? byId.get(id) ?? null : null;
    }
  };
}


function validateRoot(raw) {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    throw new SkillRegistryError('Skill Registry must be an object');
  }
  const rootKeys = Object.keys(raw);
  for (const key of rootKeys) {
    if (!['schemaVersion', 'entries'].includes(key)) {
      throw new SkillRegistryError(
        `unexpected Skill Registry field: ${key}`
      );
    }
  }
  if (raw.schemaVersion !== 1) {
    throw new SkillRegistryError(
      `unsupported Skill Registry schemaVersion: ${raw.schemaVersion}`
    );
  }
  if (!Array.isArray(raw.entries) || raw.entries.length === 0) {
    throw new SkillRegistryError(
      'Skill Registry entries must be a non-empty array'
    );
  }
}


function normalizeEntry(raw, templateRoot) {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    throw new SkillRegistryError('Skill Registry entry must be an object');
  }
  const id = typeof raw.id === 'string' ? raw.id : '<unknown>';
  for (const field of REQUIRED_FIELDS) {
    if (!Object.hasOwn(raw, field)) {
      throw new SkillRegistryError(
        `entry ${id} missing required field: ${field}`
      );
    }
  }
  for (const field of Object.keys(raw)) {
    if (!ALLOWED_FIELDS.has(field)) {
      throw new SkillRegistryError(
        `unexpected field for ${id}: ${field}`
      );
    }
  }
  if (!ID_PATTERN.test(raw.id)) {
    throw new SkillRegistryError(`invalid id: ${raw.id}`);
  }
  if (typeof raw.displayName !== 'string' || raw.displayName.trim() === '') {
    throw new SkillRegistryError(
      `displayName for ${raw.id} must be a non-empty string`
    );
  }

  const aliases = normalizeStringArray(raw.aliases, raw.id, 'aliases');
  for (const alias of aliases) {
    if (!ID_PATTERN.test(alias)) {
      throw new SkillRegistryError(
        `invalid alias for ${raw.id}: ${alias}`
      );
    }
  }
  const kind = validateEnum(raw.kind, KINDS, raw.id, 'kind');
  const visibility = validateEnum(
    raw.visibility,
    VISIBILITIES,
    raw.id,
    'visibility'
  );
  const status = validateEnum(
    raw.status,
    ENTRY_STATUSES,
    raw.id,
    'status'
  );
  const statuses = normalizeStringArray(raw.statuses, raw.id, 'statuses');
  for (const workflowStatus of statuses) {
    if (!WORKFLOW_STATUSES.has(workflowStatus)) {
      throw new SkillRegistryError(
        `invalid workflow status for ${raw.id}: ${workflowStatus}`
      );
    }
  }
  const intents = normalizeStringArray(raw.intents, raw.id, 'intents');
  for (const intent of intents) {
    if (!INTENT_PATTERN.test(intent)) {
      throw new SkillRegistryError(
        `invalid intent for ${raw.id}: ${intent}`
      );
    }
  }
  const enforcement = validateEnum(
    raw.enforcement,
    ENFORCEMENTS,
    raw.id,
    'enforcement'
  );
  const runtimeGate = nullableString(
    raw.runtimeGate,
    raw.id,
    'runtimeGate'
  );
  if (runtimeGate && !ID_PATTERN.test(runtimeGate)) {
    throw new SkillRegistryError(
      `invalid runtimeGate for ${raw.id}: ${runtimeGate}`
    );
  }
  const runtimeCommand = nullableString(
    raw.runtimeCommand,
    raw.id,
    'runtimeCommand'
  );
  const evidenceArtifact = nullableString(
    raw.evidenceArtifact,
    raw.id,
    'evidenceArtifact'
  );
  const source = normalizeRelativePath(raw.source, raw.id, 'source');
  if (!existsSync(join(templateRoot, source))) {
    throw new SkillRegistryError(
      `source does not exist for ${raw.id}: ${source}`
    );
  }
  const managedPaths = normalizeStringArray(
    raw.managedPaths,
    raw.id,
    'managedPaths'
  ).map((path) => normalizeManagedPath(path, raw.id));
  const readWhen = normalizeReadWhen(raw.readWhen ?? null, raw.id, kind);
  const replacement = nullableString(
    raw.replacement ?? null,
    raw.id,
    'replacement'
  );
  if (replacement && !ID_PATTERN.test(replacement)) {
    throw new SkillRegistryError(
      `invalid replacement for ${raw.id}: ${replacement}`
    );
  }
  const removeAfter = nullableString(
    raw.removeAfter ?? null,
    raw.id,
    'removeAfter'
  );
  if (removeAfter && !DATE_PATTERN.test(removeAfter)) {
    throw new SkillRegistryError(
      `invalid removeAfter for ${raw.id}: ${removeAfter}`
    );
  }

  return {
    id: raw.id,
    displayName: raw.displayName.trim(),
    aliases: uniqueSorted(aliases),
    kind,
    visibility,
    status,
    statuses: uniqueSorted(statuses),
    intents: uniqueSorted(intents),
    enforcement,
    runtimeGate,
    runtimeCommand,
    evidenceArtifact,
    source,
    managedPaths: uniqueSorted(managedPaths),
    readWhen,
    replacement,
    removeAfter
  };
}


function validateEnum(value, allowed, id, field) {
  if (!allowed.has(value)) {
    throw new SkillRegistryError(
      `invalid ${field} for ${id}: ${value}`
    );
  }
  return value;
}


function normalizeStringArray(value, id, field) {
  if (!Array.isArray(value)) {
    throw new SkillRegistryError(`${field} for ${id} must be an array`);
  }
  return value.map((item) => {
    if (typeof item !== 'string' || item.trim() === '') {
      throw new SkillRegistryError(
        `${field} for ${id} must contain non-empty strings`
      );
    }
    return item.trim();
  });
}


function nullableString(value, id, field) {
  if (value === null) {
    return null;
  }
  if (typeof value !== 'string' || value.trim() === '') {
    throw new SkillRegistryError(
      `${field} for ${id} must be null or a non-empty string`
    );
  }
  return value.trim();
}


function normalizeReadWhen(value, id, kind) {
  if (value === null) {
    return { devTypes: [], pathPatterns: [] };
  }
  if (kind !== 'domain' || typeof value !== 'object' || Array.isArray(value)) {
    throw new SkillRegistryError(
      `readWhen for ${id} is only valid for domain entries`
    );
  }
  for (const field of Object.keys(value)) {
    if (!['devTypes', 'pathPatterns'].includes(field)) {
      throw new SkillRegistryError(
        `unexpected readWhen field for ${id}: ${field}`
      );
    }
  }
  const devTypes = uniqueSorted(
    normalizeStringArray(value.devTypes ?? [], id, 'readWhen.devTypes')
  );
  const pathPatterns = uniqueSorted(
    normalizeStringArray(
      value.pathPatterns ?? [],
      id,
      'readWhen.pathPatterns'
    )
  );
  if (devTypes.length === 0 && pathPatterns.length === 0) {
    throw new SkillRegistryError(
      `readWhen for ${id} requires devTypes or pathPatterns`
    );
  }
  for (const pattern of pathPatterns) {
    const normalized = pattern.replaceAll('\\', '/');
    if (
      normalized.startsWith('/')
      || normalized.startsWith('../')
      || normalized.includes('/../')
    ) {
      throw new SkillRegistryError(
        `invalid readWhen.pathPatterns for ${id}: ${pattern}`
      );
    }
  }
  return { devTypes, pathPatterns };
}


function globMatches(path, pattern) {
  const escaped = pattern
    .replace(/[.+^${}()|[\]\\]/g, '\\$&')
    .replaceAll('**', '\u0000')
    .replaceAll('*', '[^/]*')
    .replaceAll('\u0000', '.*')
    .replaceAll('?', '.');
  return new RegExp(`^${escaped}$`).test(path);
}


function normalizeRelativePath(value, id, field) {
  if (typeof value !== 'string' || value.trim() === '') {
    throw new SkillRegistryError(
      `${field} for ${id} must be a non-empty relative path`
    );
  }
  const normalized = value.trim().replaceAll('\\', '/').replace(/^\.\//, '');
  if (
    isAbsolute(normalized)
    || normalized.startsWith('//')
    || /^[A-Za-z]:/.test(normalized)
    || normalized.split('/').includes('..')
    || /[*?[\]]/.test(normalized)
  ) {
    throw new SkillRegistryError(
      `invalid ${field} for ${id}: ${value}`
    );
  }
  return normalized;
}


function normalizeManagedPath(value, id) {
  const normalized = normalizeRelativePath(value, id, 'managedPaths');
  if (!normalized.endsWith('/')) {
    throw new SkillRegistryError(
      `managedPaths for ${id} must end with /: ${value}`
    );
  }
  return normalized;
}


function validateManagedPaths(entries) {
  const owners = [];
  for (const entry of entries) {
    for (const path of entry.managedPaths) {
      for (const existing of owners) {
        if (
          path === existing.path
          || path.startsWith(existing.path)
          || existing.path.startsWith(path)
        ) {
          throw new SkillRegistryError(
            `managed path overlap: ${existing.entry}:${existing.path} and ${entry.id}:${path}`
          );
        }
      }
      owners.push({ entry: entry.id, path });
    }
  }
}


function uniqueSorted(values) {
  return [...new Set(values)].sort();
}


export const skillRegistry = loadSkillRegistry();
