import assert from 'node:assert/strict';
import { test } from 'node:test';

import { isInternalTemplateFile } from '../src/lib/copy-template.js';

test('internal template files are detected with windows separators', () => {
  assert.equal(isInternalTemplateFile('.superpowers\\using-superpowers\\SKILL.md'), true);
  assert.equal(isInternalTemplateFile('.superpowers/using-superpowers/SKILL.md'), true);
  assert.equal(isInternalTemplateFile('.cowork-flow\\scripts\\change.py'), false);
});
