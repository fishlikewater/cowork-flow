import { readdir, readFile, stat } from 'node:fs/promises';
import { join, relative } from 'node:path';

import { packageRoot as defaultPackageRoot } from './paths.js';

const MIRROR_ENTRIES = [
  '.cowork-flow/scripts',
  '.cowork-flow/spec/contracts',
  '.cowork-flow/spec/core',
  '.cowork-flow/spec/reference',
  '.cowork-flow/spec/runtime',
  '.cowork-flow/spec/schemas',
  '.cowork-flow/spec/registry.json',
  '.agents/skills',
  '.codex',
  '.claude',
  '.opencode'
];

const GENERATED_SUFFIXES = [
  '.pyc'
];

const GENERATED_SEGMENTS = [
  '/__pycache__/',
  '/node_modules/'
];

export const TEMPLATE_SYNC_ALLOWED_DIFFERENCES = [
  {
    pattern: '.cowork-flow/.runtime/**',
    reason: 'runtime local state is generated per workspace and must not ship as template state'
  },
  {
    pattern: '.cowork-flow/tasks/**',
    reason: 'task state is project execution history, not a root/template runtime contract'
  },
  {
    pattern: '.cowork-flow/changes/**',
    reason: 'change artifacts are project planning history and intentionally differ from template seed files'
  },
  {
    pattern: '.cowork-flow/plans/**',
    reason: 'plan artifacts are project planning history and intentionally differ from template seed files'
  },
  {
    pattern: '.cowork-flow/workspace/**',
    reason: 'workspace journals and indexes are developer-local state'
  },
  {
    pattern: '**/__pycache__/**',
    reason: 'Python bytecode caches are generated files'
  },
  {
    pattern: '**/*.pyc',
    reason: 'Python bytecode caches are generated files'
  },
  {
    pattern: '.claude/settings.local.json',
    reason: 'Claude local settings are host-local and intentionally absent from the distributed template'
  },
  {
    pattern: '.claude/hooks/_debug_hook.py',
    reason: 'Claude debug hook is a template-only troubleshooting helper, not a root runtime contract'
  },
  {
    pattern: '.opencode/.gitignore',
    reason: 'OpenCode local development metadata is not part of the distributed host asset template'
  },
  {
    pattern: '.opencode/bun.lock',
    reason: 'OpenCode local development lockfiles are not part of the distributed host asset template'
  },
  {
    pattern: '.opencode/package.json',
    reason: 'OpenCode local development package metadata is not part of the distributed host asset template'
  },
  {
    pattern: '.cowork-flow/spec/contracts/capabilities.md',
    reason: 'legacy flattened spec path is retained in root history; template uses reference/adapters/capabilities.md'
  },
  {
    pattern: '.cowork-flow/spec/contracts/party-mode-v2-board.md',
    reason: 'legacy flattened spec path is retained in root history; template uses reference/party-mode-v2-board.md'
  },
  {
    pattern: '.cowork-flow/spec/contracts/subagent-dispatch.md',
    reason: 'legacy flattened spec path is retained in root history; template uses core/dispatch.md'
  },
  {
    pattern: '.cowork-flow/spec/contracts/workflow-state-templates.md',
    reason: 'legacy flattened spec path is retained in root history; template uses core/state-templates.md'
  },
  {
    pattern: '.cowork-flow/spec/runtime/contract-registry.json',
    reason: 'legacy flattened registry path is retained in root history; template uses spec/registry.json'
  },
  {
    pattern: '.cowork-flow/spec/schemas/adapter.schema.json',
    reason: 'legacy flattened schema path is retained in root history; template uses reference/adapters/adapter.schema.json'
  },
  {
    pattern: '.cowork-flow/spec/schemas/party-mode-v2-actions.schema.json',
    reason: 'legacy flattened schema path is retained in root history; template uses reference/party-mode-v2-actions.schema.json'
  }
];

function toTemplatePath(path) {
  return path.replaceAll('\\', '/');
}

function hasGeneratedSegment(path) {
  const normalized = `/${toTemplatePath(path)}/`;
  return GENERATED_SEGMENTS.some((segment) => normalized.includes(segment));
}

function isGeneratedPath(path) {
  const normalized = toTemplatePath(path);
  return hasGeneratedSegment(normalized)
    || GENERATED_SUFFIXES.some((suffix) => normalized.endsWith(suffix));
}

function patternToRegExp(pattern) {
  let source = '';
  for (let index = 0; index < pattern.length; index += 1) {
    const char = pattern[index];
    const next = pattern[index + 1];
    if (char === '*' && next === '*') {
      source += '.*';
      index += 1;
    } else if (char === '*') {
      source += '[^/]*';
    } else {
      source += char.replace(/[.+?^${}()|[\]\\]/g, '\\$&');
    }
  }
  return new RegExp(`^${source}$`);
}

function allowedDifferenceFor(path) {
  const normalized = toTemplatePath(path);
  return TEMPLATE_SYNC_ALLOWED_DIFFERENCES.find((entry) =>
    patternToRegExp(entry.pattern).test(normalized)
  );
}

export function explainAllowedDifference(path) {
  return allowedDifferenceFor(path)?.reason ?? '';
}

function shouldSkipMirrorPath(path) {
  return isGeneratedPath(path) || Boolean(allowedDifferenceFor(path));
}

async function listFiles(root, current = root) {
  let entries;
  try {
    entries = await readdir(current, { withFileTypes: true });
  } catch (error) {
    if (error && error.code === 'ENOENT') {
      return [];
    }
    throw error;
  }

  const files = [];
  for (const entry of entries) {
    const absolute = join(current, entry.name);
    const relativePath = toTemplatePath(relative(root, absolute));
    if (shouldSkipMirrorPath(relativePath)) {
      continue;
    }
    if (entry.isDirectory()) {
      files.push(...await listFiles(root, absolute));
    } else if (entry.isFile()) {
      files.push(relativePath);
    }
  }
  return files.sort();
}

async function listMirrorEntry(root, entry) {
  const absolute = join(root, entry);
  let info;
  try {
    info = await stat(absolute);
  } catch (error) {
    if (error && error.code === 'ENOENT') {
      return [];
    }
    throw error;
  }

  if (info.isFile()) {
    return [toTemplatePath(entry)];
  }
  if (info.isDirectory()) {
    const files = await listFiles(absolute);
    return files.map((file) => toTemplatePath(join(entry, file)));
  }
  return [];
}

async function readOptional(path) {
  try {
    return await readFile(path);
  } catch (error) {
    if (error && error.code === 'ENOENT') {
      return null;
    }
    throw error;
  }
}

async function collectMirrorFiles(root) {
  const files = new Set();
  for (const mirrorEntry of MIRROR_ENTRIES) {
    for (const rel of await listMirrorEntry(root, mirrorEntry)) {
      files.add(toTemplatePath(rel));
    }
    for (const rel of await listMirrorEntry(join(root, 'template'), mirrorEntry)) {
      files.add(toTemplatePath(rel));
    }
  }
  return [...files].sort();
}

function isTextPath(path) {
  return /\.(cmd|css|html|ini|js|json|jsonl|md|py|sh|toml|txt|yaml|yml)$/i.test(path)
    || path.endsWith('.gitignore');
}

function normalizeText(buffer) {
  return buffer.toString('utf8').replaceAll('\r\n', '\n');
}

function compareContents(path, left, right) {
  if (left === null || right === null) {
    return left === right;
  }
  if (isTextPath(path)) {
    return normalizeText(left) === normalizeText(right);
  }
  return left.equals(right);
}

export async function checkTemplateSync(options = {}) {
  const root = options.packageRoot ?? defaultPackageRoot;
  const files = await collectMirrorFiles(root);
  const drifts = [];

  for (const path of files) {
    if (shouldSkipMirrorPath(path)) {
      continue;
    }
    const rootFile = join(root, path);
    const templatePath = toTemplatePath(join('template', path));
    const templateFile = join(root, templatePath);
    const [rootContent, templateContent] = await Promise.all([
      readOptional(rootFile),
      readOptional(templateFile)
    ]);

    if (!compareContents(path, rootContent, templateContent)) {
      drifts.push({
        path,
        templatePath,
        reason: rootContent === null
          ? 'root file missing'
          : templateContent === null
            ? 'template file missing'
            : 'content differs'
      });
    }
  }

  return {
    ok: drifts.length === 0,
    checked: files.length,
    drifts
  };
}
