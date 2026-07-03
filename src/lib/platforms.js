export const SUPPORTED_PLATFORMS = ['codex', 'opencode', 'claude-code'];

const PLATFORM_ALIASES = new Map([
  ['all', SUPPORTED_PLATFORMS],
  ['codex', ['codex']],
  ['opencode', ['opencode']],
  ['claude', ['claude-code']],
  ['claude-code', ['claude-code']],
  ['claudecode', ['claude-code']]
]);

export function supportedPlatformMessage() {
  return SUPPORTED_PLATFORMS.join(', ');
}

export function parsePlatformSelection(values) {
  const rawValues = Array.isArray(values) ? values : [values];
  const selected = new Set();

  for (const rawValue of rawValues) {
    const tokens = String(rawValue ?? '')
      .toLowerCase()
      .split(/[\s,;|+/]+/)
      .map((token) => token.trim())
      .filter(Boolean);

    for (const token of tokens) {
      const platforms = PLATFORM_ALIASES.get(token);
      if (!platforms) {
        throw new Error(`Unsupported platform: ${token}. Supported platforms: ${supportedPlatformMessage()}`);
      }
      for (const platform of platforms) {
        selected.add(platform);
      }
    }
  }

  if (selected.size === 0) {
    throw new Error(
      'Platform selection required. Run: cowork-flow init <target> --platform codex|opencode|claude-code'
    );
  }

  return SUPPORTED_PLATFORMS.filter((platform) => selected.has(platform));
}

export function formatPlatformList(platforms) {
  return platforms.join(', ');
}

export function shouldIncludeForPlatforms(relativePath, platforms) {
  const normalized = relativePath.replaceAll('\\', '/');

  // Canonical skills directory at template root — never copied directly;
  // init logic injects per-platform copies separately.
  if (normalized.startsWith('skills/')) {
    return false;
  }

  // ZCode plugin bundle (.zcode/) is installed via a dedicated
  // command, not by init/sync; keep it out of project directories.
  if (normalized.startsWith(".zcode")) {
    return false;
  }

  if (normalized.startsWith('.codex/') || normalized.startsWith('.cowork-flow/adapters/codex/')) {
    return platforms.includes('codex');
  }
  if (normalized.startsWith('.opencode/') || normalized.startsWith('.cowork-flow/adapters/opencode/')) {
    return platforms.includes('opencode');
  }
  if (
    normalized === 'CLAUDE.md'
    || normalized.startsWith('.claude/')
    || normalized.startsWith('.cowork-flow/adapters/claude-code/')
  ) {
    return platforms.includes('claude-code');
  }
  return true;
}

// Destination directory for copied skills, per host platform.
// ZCode is absent because it ships the plugin bundle via install-zcode-plugin,
// not by stashing files next to the project.
export function skillDestinationForPlatform(platform) {
  switch (platform) {
    case 'codex':
    case 'opencode':
      return '.agents/skills';
    case 'claude-code':
      return '.claude/skills';
    default:
      return null;
  }
}
