import { constants } from 'node:fs';
import { access, readdir } from 'node:fs/promises';
import { join, relative } from 'node:path';

export async function pathExists(path) {
  try {
    await access(path, constants.F_OK);
    return true;
  } catch (error) {
    if (error && error.code === 'ENOENT') {
      return false;
    }
    throw error;
  }
}

export function toTemplatePath(path) {
  return path.replaceAll('\\', '/');
}

export async function listFiles(root, current = root, options = {}) {
  const { skipPath = () => false } = options;
  const entries = await readdir(current, { withFileTypes: true });
  const files = [];

  for (const entry of entries) {
    const absolute = join(current, entry.name);
    const relativePath = relative(root, absolute);
    if (skipPath(relativePath)) {
      continue;
    }
    if (entry.isDirectory()) {
      files.push(...await listFiles(root, absolute, options));
    } else if (entry.isFile()) {
      files.push(relativePath);
    }
  }

  return files.sort();
}
