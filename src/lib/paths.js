import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

export const srcRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
export const packageRoot = resolve(srcRoot, '..');
export const templateRoot = resolve(packageRoot, 'template');
