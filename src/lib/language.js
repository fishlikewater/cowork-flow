import { readFile } from 'node:fs/promises';
import { join } from 'node:path';

export const DEFAULT_LANGUAGE = 'zh-CN';
export const SUPPORTED_LANGUAGES = Object.freeze(['zh-CN', 'en-US']);

const LANGUAGE_ALIASES = new Map([
  ['zh', 'zh-CN'],
  ['zh-cn', 'zh-CN'],
  ['zh_cn', 'zh-CN'],
  ['en', 'en-US'],
  ['en-us', 'en-US'],
  ['en_us', 'en-US']
]);

// The config is a flat YAML document; a top-level `language:` scalar is the
// only place the install-time choice is recorded. A `#` starts a comment only
// outside quotes and only after whitespace, matching the Python reader.
const LANGUAGE_KEY_RE = /^language\s*:\s*(.*)$/;

function stripInlineComment(value) {
  let quote = '';
  let escaped = false;
  for (let index = 0; index < value.length; index += 1) {
    const char = value[index];
    if (escaped) {
      escaped = false;
    } else if (quote === '"' && char === '\\') {
      escaped = true;
    } else if (quote) {
      if (char === quote) {
        quote = '';
      }
    } else if (index === 0 && (char === '"' || char === "'")) {
      quote = char;
    } else if (char === '#' && (index === 0 || value[index - 1] === ' ' || value[index - 1] === '\t')) {
      return value.slice(0, index).trimEnd();
    }
  }
  return value;
}

function unquote(value) {
  if (
    value.length >= 2
    && (value[0] === '"' || value[0] === "'")
    && value[value.length - 1] === value[0]
  ) {
    return value.slice(1, -1);
  }
  return value;
}

export function normalizeLanguage(value) {
  if (value === undefined || value === null) {
    return null;
  }
  return LANGUAGE_ALIASES.get(String(value).trim().toLowerCase()) ?? null;
}

// Top-level `language:` lines only. Two keys, an empty value, a glued comment,
// or trailing junk after a quoted value all mean the explicit setting cannot be
// trusted; callers decide whether that is fatal (sync) or falls back (generation).
export function readLanguageSetting(content) {
  const entries = [];
  for (const rawLine of String(content ?? '').split(/\r?\n/)) {
    if (/^\s/.test(rawLine)) {
      continue;
    }
    const match = LANGUAGE_KEY_RE.exec(rawLine);
    if (match) {
      entries.push(match[1]);
    }
  }
  if (entries.length === 0) {
    return { present: false, raw: null, duplicate: false };
  }
  if (entries.length > 1) {
    return { present: true, raw: null, duplicate: true };
  }
  return {
    present: true,
    raw: unquote(stripInlineComment(entries[0].trim())).trim(),
    duplicate: false
  };
}

export function readLanguageValue(content) {
  const setting = readLanguageSetting(content);
  return setting.present ? setting.raw : null;
}

export function parseLanguage(content) {
  return normalizeLanguage(readLanguageValue(content));
}

export async function readProjectLanguage(targetDir) {
  const file = join(targetDir, '.cowork-flow', 'config.yaml');
  let content;
  try {
    content = await readFile(file, 'utf8');
  } catch (error) {
    if (error && error.code === 'ENOENT') {
      return {
        file,
        present: false,
        configured: false,
        valid: true,
        duplicate: false,
        raw: null,
        language: DEFAULT_LANGUAGE
      };
    }
    throw error;
  }

  const setting = readLanguageSetting(content);
  const language = setting.duplicate ? null : normalizeLanguage(setting.raw);
  return {
    file,
    present: true,
    configured: setting.present,
    valid: !setting.present || language !== null,
    duplicate: setting.duplicate,
    raw: setting.raw,
    language: language ?? DEFAULT_LANGUAGE
  };
}

// Planning commands must not silently fall back on a typo: the caller is about
// to distribute assets for a language the project explicitly asked for.
export async function readProjectLanguageStrict(targetDir) {
  const info = await readProjectLanguage(targetDir);
  if (info.configured && !info.valid) {
    const detail = info.duplicate
      ? 'duplicate language keys'
      : `unsupported language ${JSON.stringify(info.raw)}`;
    throw new Error(
      `${detail} in ${info.file}; expected ${SUPPORTED_LANGUAGES.join(' or ')}`
    );
  }
  return info;
}

// Write the chosen language into the config content that is about to be
// installed. The template already declares the key; the fallback keeps a
// hand-edited template from losing the choice.
export function withLanguage(content, language) {
  const canonical = normalizeLanguage(language);
  if (!canonical) {
    throw new Error(`Unsupported language: ${language}`);
  }
  const setting = readLanguageSetting(content);
  if (setting.duplicate) {
    throw new Error('Cannot rewrite a config with duplicate language keys');
  }
  const line = `language: "${canonical}"`;
  if (setting.present) {
    return content.replace(/^language\s*:.*$/m, line);
  }
  return `${content.replace(/\s*$/, '')}\n\n${line}\n`;
}
