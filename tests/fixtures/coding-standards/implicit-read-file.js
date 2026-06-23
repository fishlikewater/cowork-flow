import { readFile } from 'node:fs/promises';

export async function loadText() {
  return readFile('data.txt');
}
