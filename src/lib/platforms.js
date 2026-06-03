export const SUPPORTED_PLATFORMS = ['codex', 'opencode', 'claude-code'];

const LEGACY_BOTH_PLATFORMS = ['codex', 'opencode'];

const PLATFORM_ALIASES = new Map([
  ['all', SUPPORTED_PLATFORMS],
  ['both', LEGACY_BOTH_PLATFORMS],
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
