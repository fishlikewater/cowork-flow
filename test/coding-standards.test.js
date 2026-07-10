import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { promisify } from 'node:util';
import { test } from 'node:test';

import { packageRoot } from '../src/lib/paths.js';

const execFileAsync = promisify(execFile);

test('coding standards fixtures document implicit encoding cases', async () => {
  const fixtures = [
    ['implicit-open.py', /open\("data\.txt"\)\.read/],
    ['implicit-read-file.js', /readFile\('data\.txt'\)/],
    ['implicit-get-content.ps1', /Get-Content \.\\data\.txt/]
  ];

  for (const [name, pattern] of fixtures) {
    const content = await readFile(
      join(packageRoot, 'tests', 'fixtures', 'coding-standards', name),
      'utf8'
    );
    assert.match(content, pattern);
  }
});

test('template coding standards validator reports implicit Python encoding', async (t) => {
  const repo = await mkdtemp(join(tmpdir(), 'cowork-flow-coding-'));
  t.after(async () => {
    await rm(repo, { recursive: true, force: true });
  });

  const taskDir = join(repo, '.cowork-flow', 'tasks', 'demo');
  await mkdir(taskDir, { recursive: true });
  await mkdir(join(repo, 'src'), { recursive: true });
  await writeFile(
    join(repo, 'src', 'bad.py'),
    'DATA = open("data.txt").read()\n',
    'utf8'
  );

  await execFileAsync('git', ['init'], { cwd: repo, encoding: 'utf8' });
  const scriptsDir = join(packageRoot, 'template', '.cowork-flow', 'scripts');
  const runner = join(
    packageRoot,
    'template',
    '.cowork-flow',
    process.platform === 'win32' ? 'run.cmd' : 'run'
  );

  let failure = null;
  try {
    await execFileAsync(
      runner,
      [
        'python',
        '-m',
        'common.gates.validate_coding_standards',
        '--validate',
        '--repo-root',
        repo,
        '--task-dir',
        taskDir
      ],
      {
        cwd: scriptsDir,
        encoding: 'utf8',
        shell: process.platform === 'win32',
        env: {
          ...process.env,
          PYTHONPATH: scriptsDir
        }
      }
    );
  } catch (error) {
    failure = error;
  }

  assert.ok(failure, 'validator should fail on implicit Python encoding');
  assert.match(failure.stdout, /CS-UTF8-PY-001/);
  assert.match(failure.stdout, /src\/bad\.py/);
});

test('template coding standards validator allows binary Python open modes', async (t) => {
  const repo = await mkdtemp(join(tmpdir(), 'cowork-flow-coding-'));
  t.after(async () => {
    await rm(repo, { recursive: true, force: true });
  });

  const taskDir = join(repo, '.cowork-flow', 'tasks', 'demo');
  await mkdir(taskDir, { recursive: true });
  await mkdir(join(repo, 'src'), { recursive: true });
  await writeFile(
    join(repo, 'src', 'binary.py'),
    'from pathlib import Path\n\nhandle = Path("lock").open("a+b")\nhandle.write(b"0")\n',
    'utf8'
  );

  await execFileAsync('git', ['init'], { cwd: repo, encoding: 'utf8' });
  const scriptsDir = join(packageRoot, 'template', '.cowork-flow', 'scripts');
  const runner = join(
    packageRoot,
    'template',
    '.cowork-flow',
    process.platform === 'win32' ? 'run.cmd' : 'run'
  );

  const result = await execFileAsync(
    runner,
    [
      'python',
      '-m',
      'common.gates.validate_coding_standards',
      '--validate',
      '--repo-root',
      repo,
      '--task-dir',
      taskDir
    ],
    {
      cwd: scriptsDir,
      encoding: 'utf8',
      shell: process.platform === 'win32',
      env: {
        ...process.env,
        PYTHONPATH: scriptsDir
      }
    }
  );

  assert.equal(result.stderr, '');
});

test('template coding standards validator accepts multiline Node utf8 options', async (t) => {
  const repo = await mkdtemp(join(tmpdir(), 'cowork-flow-coding-'));
  t.after(async () => {
    await rm(repo, { recursive: true, force: true });
  });

  const taskDir = join(repo, '.cowork-flow', 'tasks', 'demo');
  await mkdir(taskDir, { recursive: true });
  await mkdir(join(repo, 'src'), { recursive: true });
  const source = [
    "import { writeFile } from 'node:fs/promises';",
    "import { join } from 'node:path';",
    '',
    'await write' + 'File(',
    '  join(',
    "    'nested',",
    "    'output.txt'",
    '  ),',
    '  [',
    "    'first line',",
    "    'second line'",
    "  ].join('\\n'),",
    "  'utf8'",
    ');',
    ''
  ].join('\n');
  await writeFile(join(repo, 'src', 'multiline.js'), source, 'utf8');

  await execFileAsync('git', ['init'], { cwd: repo, encoding: 'utf8' });
  const scriptsDir = join(packageRoot, 'template', '.cowork-flow', 'scripts');
  const runner = join(
    packageRoot,
    'template',
    '.cowork-flow',
    process.platform === 'win32' ? 'run.cmd' : 'run'
  );

  const result = await execFileAsync(
    runner,
    [
      'python',
      '-m',
      'common.gates.validate_coding_standards',
      '--validate',
      '--repo-root',
      repo,
      '--task-dir',
      taskDir
    ],
    {
      cwd: scriptsDir,
      encoding: 'utf8',
      shell: process.platform === 'win32',
      env: {
        ...process.env,
        PYTHONPATH: scriptsDir
      }
    }
  );

  assert.equal(result.stderr, '');
});
