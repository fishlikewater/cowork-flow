import { stdin as input, stdout as output } from 'node:process';
import { emitKeypressEvents } from 'node:readline';
import { createInterface } from 'node:readline/promises';

import { UsageError } from './lib/cli-flags.js';
import { readPackageInfo } from './lib/package-info.js';
import {
  aliasNotice,
  groupFor,
  helpPath,
  renderHelp,
  resolve
} from './commands/registry.js';

// A usage error is the caller's mistake and gets its own
// exit code; a failed operation stays 1. Success is 0.
export const EXIT_USAGE = 2;

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


function matchingChoices(choices, search) {
  const term = search.toLowerCase();
  return choices.filter((choice) => choice.label.toLowerCase().includes(term));
}


function pickerLines(state, { message, choices }) {
  const visibleChoices = matchingChoices(choices, state.search);
  if (state.activeIndex >= visibleChoices.length) {
    state.activeIndex = Math.max(0, visibleChoices.length - 1);
  }

  const selectedLabels = choices
    .filter((choice) => state.selected.has(choice.value))
    .map((choice) => choice.label);
  const lines = [
    `? ${message} (${choices.length} available)`,
    `Selected: ${selectedLabels.length > 0 ? selectedLabels.join(', ') : '(none)'}`,
    `Search: ${state.search || '[type to filter]'}`,
    '↑↓ navigate • Space toggle • Backspace remove • Enter confirm'
  ];

  if (visibleChoices.length === 0) {
    lines.push('  (no matches)');
  } else {
    for (let index = 0; index < visibleChoices.length; index += 1) {
      const choice = visibleChoices[index];
      const cursor = index === state.activeIndex ? '›' : ' ';
      const marker = state.selected.has(choice.value) ? '◉' : '○';
      const suffix = state.selected.has(choice.value) ? ' (selected)' : '';
      lines.push(`${cursor} ${marker} ${choice.label}${suffix}`);
    }
  }
  return lines;
}


function drawPicker(state, { message, choices }) {
  const lines = pickerLines(state, { message, choices });
  if (state.renderedLines > 0) {
    output.write(`\x1b[${state.renderedLines}A\x1b[0J`);
  }
  output.write(`${lines.join('\n')}\n`);
  state.renderedLines = lines.length;
}


// Returns a cancel/confirm outcome, or null for "mutated,
// redraw".
function applyPickerKey(state, text, key, choices) {
  const visibleChoices = matchingChoices(choices, state.search);
  if (key.ctrl && key.name === 'c') {
    return { outcome: 'cancel' };
  }
  if (key.name === 'return' || key.name === 'enter') {
    if (state.selected.size === 0 && visibleChoices[state.activeIndex]) {
      state.selected.add(visibleChoices[state.activeIndex].value);
    }
    return { outcome: 'confirm', value: [...state.selected] };
  }
  if (key.name === 'up') {
    state.activeIndex = Math.max(0, state.activeIndex - 1);
  } else if (key.name === 'down') {
    state.activeIndex = Math.min(Math.max(visibleChoices.length - 1, 0), state.activeIndex + 1);
  } else if (key.name === 'space' && visibleChoices[state.activeIndex]) {
    const value = visibleChoices[state.activeIndex].value;
    if (state.selected.has(value)) {
      state.selected.delete(value);
    } else {
      state.selected.add(value);
    }
  } else if (key.name === 'backspace') {
    state.search = state.search.slice(0, -1);
    state.activeIndex = 0;
  } else if (text && text.trim() && text.length === 1) {
    state.search += text;
    state.activeIndex = 0;
  }
  return null;
}


async function defaultSelectPlatforms({ message, choices, defaultSelected = [] }) {
  if (!input.isTTY || !output.isTTY || typeof input.setRawMode !== 'function') {
    return null;
  }

  const state = {
    selected: new Set(defaultSelected),
    activeIndex: 0,
    search: '',
    renderedLines: 0
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
      const action = applyPickerKey(state, text, key, choices);
      if (action?.outcome === 'cancel') {
        cleanup();
        reject(new Error('Platform selection cancelled'));
        return;
      }
      if (action?.outcome === 'confirm') {
        cleanup();
        resolve(action.value);
        return;
      }
      drawPicker(state, { message, choices });
    };

    input.on('keypress', onKeypress);
    drawPicker(state, { message, choices });
  });
}


export async function main(argv = process.argv.slice(2), options = {}) {
  const io = options.io ?? defaultIo();
  const prompt = Object.hasOwn(options, 'prompt') ? options.prompt : defaultPrompt;
  const selectPlatforms = Object.hasOwn(options, 'selectPlatforms')
    ? options.selectPlatforms
    : defaultSelectPlatforms;

  try {
    // Asking for help is an explicit intent that outranks
    // everything else in argv, so it is answered before
    // any command is resolved.
    if (argv.includes('--help') || argv.includes('-h')) {
      io.writeOut(renderHelp(helpPath(argv)));
      return 0;
    }

    if (argv.length === 0) {
      io.writeOut(renderHelp([]));
      return 0;
    }

    if (argv[0] === '--version' || argv[0] === '-v') {
      const packageInfo = await readPackageInfo();
      io.writeOut(`${packageInfo.version}\n`);
      return 0;
    }

    if (argv[0] === 'help') {
      io.writeOut(renderHelp(helpPath(argv)));
      return 0;
    }

    // A bare group names no action: answer with that
    // group's commands instead of an error, which is what
    // the caller wants anyway.
    if (argv.length === 1 && groupFor(argv[0])) {
      io.writeOut(renderHelp([argv[0]]));
      return 0;
    }

    const { command, args, alias } = resolve(argv);
    if (alias !== null && !alias.permanent) {
      io.writeErr(aliasNotice(alias));
    }
    // Installers that finish quietly return nothing;
    // `main` always answers with an exit code.
    return (await command.run(args, { io, prompt, selectPlatforms })) ?? 0;
  } catch (error) {
    io.writeErr(`${error instanceof Error ? error.message : String(error)}\n`);
    return error instanceof UsageError ? EXIT_USAGE : 1;
  }
}
