import { readFile } from 'node:fs/promises';
import { join } from 'node:path';

import { packageRoot } from './paths.js';

export async function readPackageInfo() {
  const raw = await readFile(join(packageRoot, 'package.json'), 'utf8');
  return JSON.parse(raw);
}
