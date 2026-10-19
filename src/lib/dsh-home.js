import { homedir } from 'node:os';
import { join } from 'node:path';

export function getDshHome() {
  return process.env.DSH_HOME || join(homedir(), '.dsh');
}
