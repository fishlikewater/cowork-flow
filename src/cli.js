import { stdin as input, stdout as output } from 'node:process';
import { emitKeypressEvents } from 'node:readline';
import { createInterface } from 'node:readline/promises';

import { runInit } from './commands/init.js';
import { runSync } from './commands/sync.js';
import { runUpdate } from './commands/update.js';
import { readPackageInfo } from './lib/package-info.js';

const HELP = `cowork-flow

Usage:
  cowork-flow init [target] --platform <codex|opencode|both> [--developer <name>] [--dry-run] [--force]
  cowork-flow update
  cowork-flow sync [target] [--dry-run] [--force]
  cowork-flow --version
  cowork-flow --help
`;

function defaultIo() {
  return {
    writeOut(message) {
      process.stdout.write(message);
    },
    writeErr(message) {
      process.stderr.write(message);
    }
  };
}

async function defaultPrompt(message) {
  if (!input.isTTY || !output.isTTY) {
    return null;
  }
  const readline = createInterface({ input, output });
  try {
    return await readline.question(message);
  } finally {
    readline.close();
  }
}

async function defaultSelectPlatforms({ message, choices, defaultSelected = [] }) {
  if (!input.isTTY || !output.isTTY || typeof input.setRawMode !== 'function') {
    return null;
  }

  const selected = new Set(defaultSelected);
  let activeIndex = 0;
  let search = '';
  let renderedLines = 0;

  const filteredChoices = () => {
    const term = search.toLowerCase();
    return choices.filter((choice) => choice.label.toLowerCase().includes(term));
  };

  const render = () => {
    const visibleChoices = filteredChoices();
    if (activeIndex >= visibleChoices.length) {
      activeIndex = Math.max(0, visibleChoices.length - 1);
    }

    if (renderedLines > 0) {
      output.write(`\x1b[${renderedLines}A\x1b[0J`);
    }

    const selectedLabels = choices
      .filter((choice) => selected.has(choice.value))
      .map((choice) => choice.label);
    const lines = [
      `? ${message} (${choices.length} available)`,
      `Selected: ${selectedLabels.length > 0 ? selectedLabels.join(', ') : '(none)'}`,
      `Search: ${search || '[type to filter]'}`,
      '↑↓ navigate • Space toggle • Backspace remove • Enter confirm'
    ];

    if (visibleChoices.length === 0) {
      lines.push('  (no matches)');
    } else {
      for (let index = 0; index < visibleChoices.length; index += 1) {
        const choice = visibleChoices[index];
        const cursor = index === activeIndex ? '›' : ' ';
        const marker = selected.has(choice.value) ? '◉' : '○';
        const suffix = selected.has(choice.value) ? ' (selected)' : '';
        lines.push(`${cursor} ${marker} ${choice.label}${suffix}`);
      }
    }

    output.write(`${lines.join('\n')}\n`);
    renderedLines = lines.length;
  };

  return await new Promise((resolve, reject) => {
    emitKeypressEvents(input);
    input.setRawMode(true);
    input.resume();

    const cleanup = () => {
      input.off('keypress', onKeypress);
      input.setRawMode(false);
      output.write('\n');
    };

    const onKeypress = (text, key = {}) => {
      const visibleChoices = filteredChoices();
      if (key.ctrl && key.name === 'c') {
        cleanup();
        reject(new Error('Platform selection cancelled'));
        return;
      }
      if (key.name === 'return' || key.name === 'enter') {
        if (selected.size === 0 && visibleChoices[activeIndex]) {
          selected.add(visibleChoices[activeIndex].value);
        }
        cleanup();
        resolve([...selected]);
        return;
      }
      if (key.name === 'up') {
        activeIndex = Math.max(0, activeIndex - 1);
      } else if (key.name === 'down') {
        activeIndex = Math.min(Math.max(visibleChoices.length - 1, 0), activeIndex + 1);
      } else if (key.name === 'space' && visibleChoices[activeIndex]) {
        const value = visibleChoices[activeIndex].value;
        if (selected.has(value)) {
          selected.delete(value);
        } else {
          selected.add(value);
        }
      } else if (key.name === 'backspace') {
        search = search.slice(0, -1);
        activeIndex = 0;
      } else if (text && text.trim() && text.length === 1) {
        search += text;
        activeIndex = 0;
      }
      render();
    };

    input.on('keypress', onKeypress);
    render();
  });
}

export async function main(argv = process.argv.slice(2), options = {}) {
  const io = options.io ?? defaultIo();
  const prompt = Object.hasOwn(options, 'prompt') ? options.prompt : defaultPrompt;
  const selectPlatforms = Object.hasOwn(options, 'selectPlatforms')
    ? options.selectPlatforms
    : defaultSelectPlatforms;
  const [command, ...args] = argv;

  try {
    if (!command || command === '--help' || command === '-h') {
      io.writeOut(HELP);
      return 0;
    }

    if (command === '--version' || command === '-v') {
      const packageInfo = await readPackageInfo();
      io.writeOut(`${packageInfo.version}\n`);
      return 0;
    }

    if (command === 'init') {
      return await runInit(args, { io, prompt, selectPlatforms });
    }

    if (command === 'sync') {
      return await runSync(args, { io });
    }

    if (command === 'update') {
      return await runUpdate(args, { io });
    }

    io.writeErr(`Unknown command: ${command}\n`);
    return 1;
  } catch (error) {
    io.writeErr(`${error instanceof Error ? error.message : String(error)}\n`);
    return 1;
  }
}
