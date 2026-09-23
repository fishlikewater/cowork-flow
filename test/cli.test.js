import assert from 'node:assert/strict';
import { join } from 'node:path';
import { test } from 'node:test';

import { EXIT_USAGE, main } from '../src/cli.js';
import { ALIASES, COMMANDS, GROUPS, aliasNotice } from '../src/commands/registry.js';
import { readPackageInfo } from '../src/lib/package-info.js';

function aliasNamed(name) {
  const alias = ALIASES.find((entry) => entry.name === name);
  assert.ok(alias, `the registry declares no alias named ${name}`);
  return alias;
}

function createIo() {
  return {
    stdout: '',
    stderr: '',
    writeOut(message) {
      this.stdout += message;
    },
    writeErr(message) {
      this.stderr += message;
    }
  };
}

// Command runners write through the injected io, but the host installers print
// with console.log, so a case that reaches one has to capture both streams.
async function runCli(argv) {
  const io = createIo();
  const printed = [];
  const original = console.log;
  console.log = (...args) => {
    printed.push(args.join(' '));
  };
  let code;
  try {
    code = await main(argv, { io });
  } finally {
    console.log = original;
  }
  return {
    code,
    stdout: printed.length > 0 ? `${io.stdout}${printed.join('\n')}\n` : io.stdout,
    stderr: io.stderr
  };
}

test('root help lists every group and every command', async () => {
  const { code, stdout, stderr } = await runCli([]);

  assert.equal(code, 0);
  assert.equal(stderr, '');
  for (const group of GROUPS) {
    assert.match(stdout, new RegExp(`^  ${group.id}\\s+\\S`, 'm'), `root help is missing group ${group.id}`);
  }
  for (const command of COMMANDS) {
    assert.ok(
      stdout.includes(`  cwf ${command.usage}`),
      `root help is missing the usage of ${command.path.join(' ')}`
    );
    assert.ok(
      stdout.includes(command.summary),
      `root help is missing the summary of ${command.path.join(' ')}`
    );
  }
});

test('prints version with --version', async () => {
  const io = createIo();
  const packageInfo = await readPackageInfo();

  const code = await main(['--version'], { io });

  assert.equal(code, 0);
  assert.equal(io.stdout, `${packageInfo.version}\n`);
  assert.equal(io.stderr, '');
});

test('help is answered at every level without running the command', async () => {
  const levels = [
    { argv: ['--help'], expect: 'Groups:' },
    { argv: ['-h'], expect: 'Groups:' },
    { argv: ['help'], expect: 'Groups:' },
    { argv: ['host'], expect: 'cwf host add <host>' },
    { argv: ['host', '--help'], expect: 'cwf host add <host>' },
    { argv: ['help', 'host'], expect: 'cwf host add <host>' },
    { argv: ['host', 'add', '--help'], expect: 'Options:' },
    { argv: ['help', 'host', 'add'], expect: 'Examples:' }
  ];

  for (const { argv, expect } of levels) {
    const { code, stdout, stderr } = await runCli(argv);
    assert.equal(code, 0, `${argv.join(' ')} should exit 0`);
    assert.equal(stderr, '');
    assert.ok(stdout.includes(expect), `${argv.join(' ')} should print ${JSON.stringify(expect)}`);
  }
});

test('--help outranks the rest of argv and never runs the command', async () => {
  const { code, stdout, stderr } = await runCli(['host', 'list', '--bogus', '--help']);

  assert.equal(code, 0);
  assert.equal(stderr, '');
  assert.match(stdout, /^cwf host list/m);
  assert.doesNotMatch(stdout, /Hosts declared in host-assets\.json/);
});

test('a legacy name documents where it now points', async () => {
  const { code, stdout } = await runCli(['install-codex-plugin', '--help']);

  assert.equal(code, 0);
  assert.match(stdout, /^cwf host add — /m);
});

test('an unknown command is a usage error', async () => {
  const { code, stdout, stderr } = await runCli(['missing']);

  assert.equal(code, EXIT_USAGE);
  assert.equal(stdout, '');
  assert.match(stderr, /Unknown command: missing/);
});

test('an unknown subcommand names the group it was tried in', async () => {
  const { code, stderr } = await runCli(['host', 'missing']);

  assert.equal(code, EXIT_USAGE);
  assert.match(stderr, /Unknown command: host missing/);
});

test('an unknown flag is a usage error rather than being ignored', async () => {
  const { code, stderr } = await runCli(['host', 'list', '--bogus']);

  assert.equal(code, EXIT_USAGE);
  assert.match(stderr, /Unknown option: --bogus/);
});

test('an unknown host or component is a usage error', async () => {
  const unknownHost = await runCli(['host', 'add', 'nonsense']);
  assert.equal(unknownHost.code, EXIT_USAGE);
  assert.match(unknownHost.stderr, /Unknown host: nonsense/);
  assert.match(unknownHost.stderr, /Declared hosts: codex, opencode, claude-code, dsh, zcode, kimi-code, qoder/);

  const noComponent = await runCli(['host', 'add', 'opencode']);
  assert.equal(noComponent.code, EXIT_USAGE);
  assert.match(noComponent.stderr, /Host opencode has no machine-level integration/);

  const wrongComponent = await runCli(['host', 'add', 'codex', '--component', 'hook']);
  assert.equal(wrongComponent.code, EXIT_USAGE);
  assert.match(wrongComponent.stderr, /Host codex has no component hook/);
});

test('a missing positional argument is a usage error', async () => {
  const { code, stderr } = await runCli(['host', 'add']);

  assert.equal(code, EXIT_USAGE);
  assert.match(stderr, /Missing required argument: <host>/);
});

test('a value flag without a value is a usage error', async () => {
  const { code, stderr } = await runCli(['host', 'add', 'dsh', '--component', '--dry-run']);

  assert.equal(code, EXIT_USAGE);
  assert.match(stderr, /Missing value for --component/);
});

// The shims must be pure renames: same stdout, one extra line on stderr.
test('a shim reports the migration on stderr and leaves stdout alone', async () => {
  const shim = await runCli(['install-dsh-hook', '--dry-run']);
  const replacement = await runCli(['host', 'add', 'dsh', '--component', 'hook', '--dry-run']);

  assert.equal(shim.code, 0);
  assert.equal(shim.stdout, replacement.stdout);
  assert.equal(shim.stderr, aliasNotice(aliasNamed('install-dsh-hook')));
  assert.equal(replacement.stderr, '');
});

test('a permanent alias is silent', async () => {
  const target = join(process.cwd(), 'cwf-alias-probe-does-not-exist');
  const argv = [target, '--platform', 'codex', '--developer', 'probe', '--dry-run'];

  const viaAlias = await runCli(['init', ...argv]);
  const viaPath = await runCli(['project', 'init', ...argv]);

  assert.equal(viaAlias.code, 0);
  assert.equal(viaAlias.stderr, '');
  assert.equal(viaAlias.stdout, viaPath.stdout);
});

test('every alias points at a command the registry declares', async () => {
  for (const alias of ALIASES) {
    const target = COMMANDS.find(
      (command) => command.path.join(' ') === alias.command.join(' ')
    );
    assert.ok(target, `alias ${alias.name} points at undeclared command ${alias.command.join(' ')}`);
  }
});
