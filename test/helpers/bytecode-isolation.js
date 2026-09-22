import { join } from 'node:path';

import { packageRoot } from '../../src/lib/paths.js';

// Shipped runtimes live under `template/`; a python child that imports them
// would otherwise drop `__pycache__` next to shipped sources. Python reads
// PYTHONPYCACHEPREFIX when the interpreter starts, so exporting it here — at
// module load, before any test spawns a child — covers every `python` process
// descended from this test run, including ones spawned by the host hooks the
// tests drive. `tests/__init__.py` is the pytest/unittest-side half of the
// same guard.
//
// Truthiness, not `??=`: an empty value is "unset" to Python, so letting one
// through would silently restore the pollution.
if (!process.env.PYTHONPYCACHEPREFIX) {
  process.env.PYTHONPYCACHEPREFIX = join(packageRoot, '.tmp', 'pycache');
}
