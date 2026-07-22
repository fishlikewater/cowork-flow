import * as fileSystem from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

export async function createTempDir(t) {
  const dir = await fileSystem.mkdtemp(join(tmpdir(), 'cowork-flow-'));
  t.after(async () => {
    await fileSystem.rm(dir, { recursive: true, force: true });
  });
  return dir;
}

export async function exists(path) {
  try {
    await fileSystem.stat(path);
    return true;
  } catch (error) {
    if (error && error.code === 'ENOENT') {
      return false;
    }
    throw error;
  }
}

export async function readText(path) {
  return fileSystem.readFile(path, 'utf8');
}

export function fileSystemWithRenameFailure(predicate) {
  return new Proxy(fileSystem, {
    get(target, property) {
      if (property !== 'rename') {
        return target[property];
      }
      return async (source, destination) => {
        if (predicate(source, destination)) {
          const error = new Error('injected commit failure');
          error.code = 'EIO';
          throw error;
        }
        return target.rename(source, destination);
      };
    }
  });
}
