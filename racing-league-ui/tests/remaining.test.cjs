const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

function load(filename, dependencies = {}, context = vm.createContext({ Error, console, Date })) {
  const source = ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src', filename), 'utf8'), {
    compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS,
      jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true },
  }).outputText;
  const module = { exports: {} };
  vm.runInContext('(function(exports,require,module){' + source + '\n})', context)(module.exports, name => {
    if (!(name in dependencies)) throw new Error('Unexpected dependency: ' + name);
    return dependencies[name];
  }, module);
  return module.exports;
}
const ranking = load('services/standings.ts');
const stats = (points, wins, podiums, position) => ({ points, wins, podiums, position, dnfs: 0, fastestLaps: 0 });
const team = (points, wins, podiums, position) => ({ members: [], member_details: [],
  total_points: points, total_wins: wins, total_podiums: podiums, total_dnfs: 0, total_fastest_laps: 0, position });

test('driver ordering uses authoritative positions and complete tie breakers for older responses', () => {
  assert.deepEqual(Array.from(ranking.sortedDrivers({ owner: stats(25, 0, 1), winner: stats(25, 1, 1) }), item => item[0]), ['winner', 'owner']);
  assert.deepEqual(Array.from(ranking.sortedDrivers({ z: stats(0, 0, 0), a: stats(0, 0, 0) }), item => item[0]), ['a', 'z']);
  assert.deepEqual(Array.from(ranking.sortedDrivers({ a: stats(25, 0, 0, 2), z: stats(25, 0, 0, 1) }), item => item[0]), ['z', 'a']);
});

test('team ordering uses backend ranks, wins, podiums, then stable names', () => {
  assert.deepEqual(Array.from(ranking.sortedTeams({ Earlier: team(25, 0, 1), Winner: team(25, 1, 1) }), item => item[0]), ['Winner', 'Earlier']);
  assert.deepEqual(Array.from(ranking.sortedTeams({ B: team(0, 0, 0), A: team(0, 0, 0) }), item => item[0]), ['A', 'B']);
  assert.deepEqual(Array.from(ranking.sortedTeams({ A: team(25, 0, 0, 2), B: team(25, 0, 0, 1) }), item => item[0]), ['B', 'A']);
});

function harness(filename, api, route = { leagueId: 'league-A' }) {
  const states = [], effects = [], cleanups = [], timers = new Map();
  let cursor = 0, effectCursor = 0, nextTimer = 0;
  const react = {
    useState(initial) {
      const i = cursor++;
      if (!(i in states)) states[i] = typeof initial === 'function' ? initial() : initial;
      return [states[i], value => { states[i] = typeof value === 'function' ? value(states[i]) : value; }];
    },
    useEffect(work, dependencies) {
      const i = effectCursor++;
      if (!effects[i] || dependencies.some((value, index) => value !== effects[i].dependencies[index])) {
        effects[i] = { work, dependencies, pending: true };
      }
    },
  };
  react.default = react; react.__esModule = true;
  const jsx = (type, props) => ({ type, props });
  const mui = new Proxy({}, { get: (_target, key) => key });
  const context = vm.createContext({ Error, console, Date,
    setTimeout: work => { timers.set(++nextTimer, work); return nextTimer; }, clearTimeout: id => timers.delete(id) });
  const component = load('pages/' + filename, {
    react, 'react/jsx-runtime': { jsx, jsxs: jsx, Fragment: 'Fragment' },
    '@mui/material': mui, '@mui/icons-material': mui,
    'react-router-dom': { useNavigate: () => () => {}, useParams: () => route },
    '../hooks/useAuth': { useAuth: () => ({ user: { email: 'owner@example.test' }, isAuthenticated: true }) },
    '../services/api': api, '../services/standings': ranking,
    '../components/submit-race-results': { __esModule: true, default: 'SubmitRaceResultsDialog' },
    '../components/invite-players-dialog': { __esModule: true, default: 'InvitePlayersDialog' },
    '../components/race-detail-dialog': { __esModule: true, default: 'RaceDetailDialog' },
  }, context).default;
  const render = () => { cursor = 0; effectCursor = 0; return component(); };
  function flushEffects() {
    for (let i = 0; i < effects.length; i++) {
      if (!effects[i].pending) continue;
      effects[i].pending = false;
      if (typeof cleanups[i] === 'function') cleanups[i]();
      cleanups[i] = effects[i].work();
    }
  }
  async function runTimers() {
    const work = [...timers.values()]; timers.clear();
    await Promise.all(work.map(callback => callback()));
  }
  return { render, flushEffects, runTimers,
    dispose: () => cleanups.forEach(cleanup => typeof cleanup === 'function' && cleanup()) };
}
function elements(node, predicate) {
  if (Array.isArray(node)) return node.flatMap(item => elements(item, predicate));
  if (!node || !node.props) return [];
  return [...(predicate(node) ? [node] : []), ...elements(node.props.children, predicate)];
}
const text = node => node == null ? '' : ['string', 'number'].includes(typeof node) ? String(node) : Array.isArray(node)
  ? node.map(text).join('') : text(node.props?.children);
const search = tree => elements(tree, node => node.type === 'TextField')[0];
const pagination = tree => elements(tree, node => node.type === 'Pagination')[0];
const cards = tree => elements(tree, node => !!node.props.league && typeof node.props.onJoin === 'function');
const summary = name => ({ _id: name, name, public: true, status: 'active', max_players: 20, participantsCount: 2, next_race: null });
const page = (name, total = 23) => ({ leagues: [summary(name)], total, total_pages: Math.ceil(total / 9), page: 1, page_size: 9 });
function deferred() { let resolve; const promise = new Promise(done => { resolve = done; }); return { promise, resolve }; }
async function start(h) { h.render(); h.flushEffects(); await h.runTimers(); await Promise.resolve(); return h.render(); }

test('discovery requests only the selected server page and shows the server total', async () => {
  const requests = [];
  const h = harness('filnd-leagues.tsx', { fetchPublicLeagues: async (...args) => { requests.push(args); return page('First'); } });
  let tree = await start(h);
  assert.deepEqual(requests, [[1, 9, '']]);
  assert.ok(text(tree).includes('Found 23 leagues'));
  assert.equal(pagination(tree).props.count, 3);
  pagination(tree).props.onChange({}, 2); h.render(); h.flushEffects();
  assert.ok(search(h.render()), 'The search field stays mounted while refreshing');
  await h.runTimers(); tree = h.render();
  assert.deepEqual(requests[1], [2, 9, '']);
  assert.equal(cards(tree).length, 1);
  assert.equal(pagination(tree).props.page, 2);
  h.dispose();
});

test('search is debounced on the server, resets pagination, and works after an empty response', async () => {
  const requests = [];
  const h = harness('filnd-leagues.tsx', { fetchPublicLeagues: async (...args) => {
    requests.push(args); return requests.length === 1 ? page('First') : { ...page('unused', 0), leagues: [] };
  } });
  let tree = await start(h);
  pagination(tree).props.onChange({}, 2); h.render(); h.flushEffects();
  search(h.render()).props.onChange({ target: { value: 's' } }); h.render(); h.flushEffects();
  search(h.render()).props.onChange({ target: { value: 'Spa' } }); h.render(); h.flushEffects();
  assert.equal(requests.length, 1);
  await h.runTimers(); tree = h.render();
  assert.deepEqual(requests[1], [1, 9, 'Spa']);
  assert.ok(text(tree).includes('Found 0 leagues'));
  assert.ok(search(tree));
  search(tree).props.onChange({ target: { value: 'Monza' } }); h.render(); h.flushEffects();
  assert.ok(search(h.render()));
  await h.runTimers();
  assert.deepEqual(requests[2], [1, 9, 'Monza']);
  h.dispose();
});

test('a late discovery response cannot replace a newer query', async () => {
  const old = deferred(); let calls = 0;
  const h = harness('filnd-leagues.tsx', { fetchPublicLeagues: () => ++calls === 1 ? Promise.resolve(page('Initial'))
    : calls === 2 ? old.promise : Promise.resolve(page('Newest')) });
  let tree = await start(h);
  search(tree).props.onChange({ target: { value: 'Old' } }); h.render(); h.flushEffects();
  const previous = h.runTimers();
  search(h.render()).props.onChange({ target: { value: 'New' } }); h.render(); h.flushEffects();
  await h.runTimers(); old.resolve(page('Stale')); await previous;
  tree = h.render();
  assert.equal(cards(tree)[0].props.league.name, 'Newest');
  assert.equal(search(tree).props.value, 'New');
  h.dispose();
});

test('failed discovery offers retry, and disappearing last pages refetch the new last page', async () => {
  let calls = 0;
  const h = harness('filnd-leagues.tsx', { fetchPublicLeagues: async () => {
    if (++calls === 1) throw new Error('offline');
    return page('Recovered');
  } });
  let tree = await start(h);
  const alert = elements(tree, node => node.type === 'Alert' && node.props.severity === 'error')[0];
  assert.ok(!text(tree).includes('Found '));
  alert.props.action.props.onClick(); h.render(); h.flushEffects(); await h.runTimers(); tree = h.render();
  assert.equal(cards(tree)[0].props.league.name, 'Recovered');
  h.dispose();
  const requested = [];
  const shrink = harness('filnd-leagues.tsx', { fetchPublicLeagues: async number => {
    requested.push(number);
    return number === 3 ? { ...page('unused', 10), leagues: [] } : page('Valid page', number === 2 ? 10 : 23);
  } });
  tree = await start(shrink);
  pagination(tree).props.onChange({}, 3); shrink.render(); shrink.flushEffects(); await shrink.runTimers();
  shrink.render(); shrink.flushEffects(); await shrink.runTimers();
  assert.deepEqual(requested, [1, 3, 2]);
  assert.equal(pagination(shrink.render()).props.page, 2);
  shrink.dispose();
});

const league = { _id: 'league-A', name: 'League', owner: 'owner@example.test', admins: [],
  participants: [{ email: 'owner@example.test', name: 'Owner' }, { email: 'driver@example.test', name: 'Driver' }],
  created_at: new Date(), calendar: [], pointSystem: { 1: 25 }, fastestLapPoint: 0, status: 'active',
  max_players: 20, participantsCount: 2, standings: { overall: {}, races: {} },
  teams: { Team: team(0, 0, 0, 1) } };
const teamPoints = tree => elements(tree, node => node.type === 'Typography' && node.props.variant === 'h5'
  && node.props.color === 'primary')[0]?.props.children;

test('actual result callback updates team totals from the same response and clears removed teams', async () => {
  const h = harness('league-details.tsx', { fetchLeagueById: async () => league });
  let tree = await start(h);
  assert.equal(teamPoints(tree), 0);
  elements(tree, node => node.type === 'SubmitRaceResultsDialog')[0].props.onResultsSubmitted({
    ...league, teams: { Team: team(25, 1, 1, 1) },
  });
  tree = h.render(); assert.equal(teamPoints(tree), 25);
  elements(tree, node => node.type === 'SubmitRaceResultsDialog')[0].props.onResultsSubmitted({ ...league, teams: {} });
  assert.equal(teamPoints(h.render()), undefined);
  assert.ok(text(h.render()).includes('No Teams Created'));
  h.dispose();
});

test('league details use the same driver and team order in every standings view', async () => {
  const fixture = { ...league, standings: { overall: {
    'owner@example.test': stats(25, 0, 1, 2), 'driver@example.test': stats(25, 1, 1, 1),
  }, races: {} }, teams: { Earlier: team(25, 0, 1, 2), Winner: team(25, 1, 1, 1) } };
  const h = harness('league-details.tsx', { fetchLeagueById: async () => fixture });
  const tree = await start(h);
  const names = elements(tree, node => node.type === 'TableRow').map(text).filter(value => value.includes('Driver') || value.includes('Owner'));
  assert.ok(names.findIndex(value => value.includes('Driver')) < names.findIndex(value => value.includes('Owner')));
  const teams = elements(tree, node => node.type === 'Typography' && node.props.variant === 'h6').map(text);
  assert.ok(teams.indexOf('Winner') < teams.indexOf('Earlier'));
  h.dispose();
});

test('creation starts with zero fastest-lap bonus, applies current presets, and retains custom bonus editing', async () => {
  const h = harness('create-league.tsx', { getPointSystemPresets: async () => [
    { _id: 'custom', name: 'Custom bonus', points: { 1: 25 }, fastest_lap_point: 5 },
    { _id: 'current', name: 'F1 Current', points: { 1: 25 }, fastest_lap_point: 0 },
  ] });
  let tree = await start(h);
  elements(tree, node => node.type === 'TextField' && node.props.name === 'name')[0].props.onChange({
    target: { name: 'name', value: 'New league' },
  });
  const next = () => elements(h.render(), node => node.type === 'Button' && text(node) === 'Next')[0].props.onClick();
  next(); next(); tree = h.render();
  const bonus = () => elements(h.render(), node => node.type === 'TextField' && node.props.name === 'fastestLapPoint')[0];
  assert.equal(bonus().props.value, 0);
  const preset = () => elements(h.render(), node => node.type === 'Select' && node.props.labelId === 'scoring-preset-label')[0];
  preset().props.onChange({ target: { value: 'custom' } });
  assert.equal(bonus().props.value, 5);
  preset().props.onChange({ target: { value: 'current' } });
  assert.equal(bonus().props.value, 0);
  bonus().props.onChange({ target: { name: 'fastestLapPoint', value: '1' } });
  assert.equal(bonus().props.value, 1);
  h.dispose();
});
