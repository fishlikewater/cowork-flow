import { homedir } from 'node:os';
import { join } from 'node:path';

export function getDshHome(env = process.env) {
  return env.DSH_HOME || join(homedir(), '.dsh');
}
