const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

function loadModule(filename, dependencies = {}, context = vm.createContext({ Error, console, URL })) {
  const source = ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src', filename), 'utf8'), {
    compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS,
      jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true },
  }).outputText;
  const module = { exports: {} };
  vm.runInContext('(function(exports,require,module){' + source + '\n})', context)(module.exports, name => {
    if (name in dependencies) return dependencies[name];
    throw new Error('Unexpected dependency: ' + name);
  }, module);
  return module.exports;
}
const imports = loadModule('services/race-image-import.ts');
const participants = [
  { email: 'ann@example.test', name: 'Ann', league_user_name: 'Ann' },
  { email: 'anna@example.test', name: 'Anna', league_user_name: 'Anna' },
  { email: 'bob@example.test', name: 'Robert', league_user_name: 'Bob' },
];
const drivers = participants.map((item, i) => ({ driverId: item.email, name: item.league_user_name,
  position: i + 1, fastestLap: i === 1, dnf: i === 2 }));
const row = (driver, position) => ({ driver, position });
const apply = rows => imports.importImageResults({ results: rows }, drivers, participants);
const ids = result => Array.from(result.drivers, driver => driver.driverId);
const file = (name = 'first', size = 10, type = 'image/png') => ({ name, size, type });

test('Ann and Anna match separately; exact aliases normalize case and whitespace', () => {
  const result = apply([row(' anna ', 1), row('ANN', 2), row('Robert', 3)]);
  assert.deepEqual(ids(result), ['anna@example.test', 'ann@example.test', 'bob@example.test']);
  assert.equal(result.matched, 3);
  assert.equal(result.drivers[0].fastestLap, true);
  assert.equal(result.drivers[2].dnf, true);
  assert.equal(result.warnings.length, 0);
});

test('ambiguous display names and substring guesses never select a driver', () => {
  const duplicate = participants.map(item => ({ ...item, league_user_name: 'Driver' }));
  assert.throws(() => imports.importImageResults({ results: [row('Driver', 1)] },
    drivers.map(driver => ({ ...driver, name: 'Driver' })), duplicate), /No unambiguous/);
  assert.throws(() => apply([row('An', 1)]), /No unambiguous/);
});

test('incomplete and invalid rows are skipped and partial ordering stays unique', () => {
  const result = apply([{}, row(null, 2), row('Anna', '2'), row('Bob', 0), row('Unknown', 1), row('Ann', 3)]);
  assert.equal(result.matched, 1);
  assert.deepEqual(ids(result), ['anna@example.test', 'bob@example.test', 'ann@example.test']);
  assert.deepEqual(Array.from(result.drivers, driver => driver.position), [1, 2, 3]);
  assert.ok(result.warnings.some(message => message.includes('5')));
  assert.ok(result.warnings.some(message => message.includes('Anna') && message.includes('Bob')));
  assert.equal(result.drivers[0].fastestLap, true);
  assert.equal(result.drivers[1].dnf, true);
});

test('overlapping screenshots deduplicate identical rows and reject conflicting placements', () => {
  const duplicate = apply([row('Ann', 2), row('Ann', 2), row('Anna', 1)]);
  assert.equal(duplicate.matched, 2);
  const conflict = apply([row('Ann', 1), row('Anna', 1), row('Bob', 3)]);
  assert.equal(conflict.matched, 1);
  assert.equal(conflict.warnings.filter(message => message.includes('conflicting')).length, 1);
  assert.deepEqual(ids(conflict), drivers.map(driver => driver.driverId));
  assert.throws(() => apply([row('Ann', 1), row('Ann', 2), row('Anna', 2)]), /No unambiguous/);
});

test('malformed or empty AI results fail without changing the existing order', () => {
  for (const value of [null, [], 'bad JSON', { results: {} }, { error: 'parse failed' }]) {
    assert.throws(() => imports.importImageResults(value, drivers, participants), /invalid results/);
  }
  assert.throws(() => apply([]), /No unambiguous/);
  assert.deepEqual(drivers.map(driver => driver.position), [1, 2, 3]);
});

test('client validation checks the whole selection without silently dropping files', () => {
  for (const files of [[], [file(), file(), file()], [file('empty', 0)], [file('big', 6 * 1024 * 1024 + 1)],
    [file('gif', 10, 'image/gif')]]) {
    assert.ok(imports.validateScreenshots(files));
  }
  assert.equal(imports.validateScreenshots([file('one', 6 * 1024 * 1024), file('two', 12, '')]), null);
});

function dialogHarness(api) {
  const states = [], effects = [], cleanups = [], created = [], revoked = [];
  let cursor = 0, effectCursor = 0, nextUrl = 0;
  const react = {
    useState(initial) {
      const i = cursor++;
      if (!(i in states)) states[i] = typeof initial === 'function' ? initial() : initial;
      return [states[i], value => { states[i] = typeof value === 'function' ? value(states[i]) : value; }];
    },
    useRef(initial) {
      const i = cursor++;
      if (!(i in states)) states[i] = { current: initial };
      return states[i];
    },
    useEffect(work, dependencies) {
      const i = effectCursor++;
      if (!effects[i] || dependencies.some((value, index) => value !== effects[i].dependencies[index])) {
        effects[i] = { work, dependencies, pending: true };
      }
    },
  };
  react.useLayoutEffect = react.useEffect;
  react.default = react; react.__esModule = true;
  const jsx = (type, props) => ({ type, props });
  const mui = new Proxy({}, { get: (_target, key) => key });
  const context = vm.createContext({ Error, console, URL: {
    createObjectURL: input => { const url = `blob:${input.name}:${++nextUrl}`; created.push(url); return url; },
    revokeObjectURL: url => revoked.push(url),
  } });
  const component = loadModule('components/submit-race-results.tsx', {
    react, 'react/jsx-runtime': { jsx, jsxs: jsx, Fragment: 'Fragment' },
    '@mui/material': mui, '@mui/icons-material': mui,
    '@dnd-kit/core': { DndContext: 'DndContext', useSensor: () => ({}), useSensors: () => [] },
    '@dnd-kit/sortable': { SortableContext: 'SortableContext', arrayMove: (list, from, to) => {
      const copy = [...list]; copy.splice(to, 0, copy.splice(from, 1)[0]); return copy;
    } }, '@dnd-kit/utilities': {}, '../services/api': api, '../services/race-image-import': imports,
  }, context).default;
  let closed = 0, submitted = 0;
  let props = { open: true, onClose: () => { closed++; }, onResultsSubmitted: () => { submitted++; },
    league: { _id: 'league-A', participants, pointSystem: { 1: 25, 2: 18 }, fastestLapPoint: 1 },
    selectedRace: { _id: 'race-A', track: 'Monza' } };
  const render = () => { cursor = 0; effectCursor = 0; return component(props); };
  function flush() {
    for (let i = 0; i < effects.length; i++) {
      if (!effects[i].pending) continue;
      effects[i].pending = false;
      if (typeof cleanups[i] === 'function') cleanups[i]();
      cleanups[i] = effects[i].work();
    }
  }
  const settle = () => { render(); flush(); render(); flush(); return render(); };
  return { render, settle, created, revoked,
    change: values => { props = { ...props, ...values }; return settle(); },
    dispose: () => cleanups.forEach(cleanup => typeof cleanup === 'function' && cleanup()),
    counts: () => ({ closed, submitted }) };
}
function elements(node, predicate) {
  if (Array.isArray(node)) return node.flatMap(item => elements(item, predicate));
  if (!node || !node.props) return [];
  return [...(predicate(node) ? [node] : []), ...elements(node.props.children, predicate)];
}
const text = node => !node ? '' : typeof node === 'string' ? node : Array.isArray(node)
  ? node.map(text).join('') : text(node.props?.children);
const button = (tree, label) => elements(tree, node => node.type === 'Button' && text(node).includes(label))[0];
const rows = tree => elements(tree, node => !!node.props.driver);
const uploader = tree => elements(tree, node => node.type === 'input')[0];
const checkbox = tree => elements(tree, node => node.type === 'FormControlLabel' && node.props.control?.type === 'Checkbox')[0]?.props.control;
function upload(h, files = [file()]) {
  const target = { files, value: 'selected' };
  uploader(h.render()).props.onChange({ target });
  assert.equal(target.value, '');
  return h.settle();
}
function deferred() { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b; }); return { promise, resolve, reject }; }

test('AI results require review, preserve flags, and prevent submission while extraction is pending', async () => {
  const pending = deferred(); let saves = 0, requests = 0;
  const h = dialogHarness({ processMultipleRaceScreenshots: () => { requests++; return pending.promise; },
    submitRaceResult: async (_league, _race, results) => { saves++; assert.equal(results['bob@example.test'].dnf, true); return {}; } });
  let tree = h.settle();
  rows(tree)[1].props.onFastestLapChange('anna@example.test');
  rows(tree)[2].props.onDNFChange('bob@example.test', true);
  tree = upload(h);
  const process = button(tree, 'Extract Results').props.onClick();
  tree = h.render();
  assert.equal(button(tree, 'Submit Results').props.disabled, true);
  assert.equal(uploader(tree).props.disabled, true);
  assert.ok(rows(tree).every(node => node.props.disabled));
  await button(tree, 'Submit Results').props.onClick();
  await button(tree, 'Analyzing').props.onClick();
  assert.equal(saves, 0); assert.equal(requests, 1);
  pending.resolve({ results: [row('Anna', 1), row('Ann', 2), row('Bob', 3)] });
  await process;
  tree = h.settle();
  assert.equal(rows(tree)[0].props.driver.fastestLap, true);
  assert.equal(rows(tree)[2].props.driver.dnf, true);
  assert.equal(button(tree, 'Submit Results').props.disabled, true);
  await button(tree, 'Submit Results').props.onClick();
  assert.equal(saves, 0);
  checkbox(tree).props.onChange({ target: { checked: true } });
  tree = h.render();
  assert.equal(button(tree, 'Submit Results').props.disabled, false);
  await button(tree, 'Submit Results').props.onClick();
  assert.equal(saves, 1);
  assert.deepEqual(h.counts(), { closed: 1, submitted: 1 });
  h.dispose();
});

test('responses from a previous race, closed dialog, or unmounted dialog cannot replace the current draft', async () => {
  for (const change of ['race', 'close', 'unmount']) {
    const pending = deferred();
    const h = dialogHarness({ processMultipleRaceScreenshots: () => pending.promise });
    h.settle(); const tree = upload(h);
    const request = button(tree, 'Extract Results').props.onClick();
    if (change === 'race') h.change({ selectedRace: { _id: 'race-B', track: 'Spa' } });
    if (change === 'close') { button(h.render(), 'Cancel').props.onClick(); h.change({ open: false }); h.change({ open: true }); }
    if (change === 'unmount') h.dispose();
    pending.resolve({ results: [row('Anna', 1), row('Ann', 2)] });
    await request;
    assert.equal(rows(h.render())[0].props.driver.name, 'Ann');
    assert.equal(checkbox(h.render()), undefined);
    if (change !== 'unmount') h.dispose();
  }
});

test('upload previews retain file order and release object URLs after removal, close, and unmount', () => {
  const h = dialogHarness({}); h.settle();
  let tree = upload(h, [file('first'), file('second')]);
  const images = elements(tree, node => node.type === 'img');
  assert.ok(images[0].props.src.includes('first'));
  assert.ok(images[1].props.src.includes('second'));
  elements(tree, node => node.props['aria-label'] === 'Remove screenshot 1')[0].props.onClick();
  tree = h.settle();
  assert.equal(elements(tree, node => node.type === 'img').length, 1);
  assert.ok(elements(tree, node => node.type === 'img')[0].props.src.includes('second'));
  h.change({ open: false }); h.dispose();
  assert.equal(h.created.length, h.revoked.length);
  assert.deepEqual(new Set(h.created), new Set(h.revoked));
});

test('invalid upload selection reports a failure and retains previous files for retry', () => {
  const h = dialogHarness({}); h.settle(); upload(h, [file('first')]);
  const tree = upload(h, [file('big', 6 * 1024 * 1024 + 1)]);
  assert.equal(elements(tree, node => node.type === 'img').length, 1);
  assert.ok(text(elements(tree, node => node.type === 'Alert')[0]).includes('6 MiB'));
  h.dispose();
});

test('failed extraction retains manual edits and images without claiming a successful import', async () => {
  const h = dialogHarness({ processMultipleRaceScreenshots: async () => { throw new Error('Image extraction timed out'); } });
  let tree = h.settle();
  rows(tree)[1].props.onFastestLapChange('anna@example.test');
  tree = upload(h);
  await button(tree, 'Extract Results').props.onClick();
  tree = h.render();
  assert.equal(rows(tree)[1].props.driver.fastestLap, true);
  assert.equal(elements(tree, node => node.type === 'img').length, 1);
  assert.ok(text(elements(tree, node => node.type === 'Alert')[0]).includes('timed out'));
  assert.equal(checkbox(tree), undefined);
  h.dispose();
});

test('late submission callbacks do not close a different race dialog; dropping outside the list does not reorder', async () => {
  const pending = deferred();
  const h = dialogHarness({ submitRaceResult: () => pending.promise });
  let tree = h.settle();
  elements(tree, node => node.type === 'DndContext')[0].props.onDragEnd({ active: { id: 'ann@example.test' }, over: null });
  assert.equal(rows(h.render())[0].props.driver.name, 'Ann');
  const request = button(tree, 'Submit Results').props.onClick();
  tree = h.change({ selectedRace: { _id: 'race-B', track: 'Spa' } });
  pending.resolve({}); await request;
  assert.deepEqual(h.counts(), { closed: 0, submitted: 0 });
  assert.equal(button(tree, 'Submit Results').props.disabled, false);
  h.dispose();
});
