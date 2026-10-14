const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

// Execute the actual page handlers and hooks without a DOM or external services.
function pageHarness(filename, api, auth = {}) {
  const states = []; const effects = []; const cleanups = [];
  let cursor = 0; let effectCursor = 0;
  const navigate = () => {};
  const react = {
    useState(initial) {
      const index = cursor++;
      if (!(index in states)) states[index] = typeof initial === 'function' ? initial() : initial;
      return [states[index], value => { states[index] = typeof value === 'function' ? value(states[index]) : value; }];
    },
    useEffect(work, dependencies) {
      const index = effectCursor++;
      const old = effects[index];
      if (!old || dependencies.some((value, i) => value !== old.dependencies[i])) {
        effects[index] = { work, dependencies, pending: true };
      }
    },
  };
  react.default = react; react.__esModule = true;
  const jsx = (type, props) => ({ type, props });
  const mui = new Proxy({
    useTheme: () => ({ breakpoints: { down: () => 'md' } }), useMediaQuery: () => false,
  }, { get: (target, key) => target[key] || key });
  const requireModule = name => {
    if (name === 'react') return react;
    if (name === 'react/jsx-runtime') return { jsx, jsxs: jsx, Fragment: 'Fragment' };
    if (name.startsWith('@mui/')) return mui;
    if (name === 'react-router-dom') return { useNavigate: () => navigate, Link: 'Link', Navigate: 'Navigate' };
    if (name === '../services/api') return api;
    if (name === '../hooks/useAuth') return { useAuth: () => ({ isAuthenticated: false, loading: false, ...auth }) };
    if (name === '../components/public-header') return { __esModule: true, default: 'PublicHeader' };
    throw new Error('Unexpected page dependency: ' + name);
  };
  const source = ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/pages', filename), 'utf8'), {
    compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS,
      jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true },
  }).outputText;
  const module = { exports: {} };
  const context = vm.createContext({ Error, console, URLSearchParams,
    window: { location: { search: '', href: '', reload() {} } } });
  vm.runInContext('(function(exports,require,module){' + source + '\n})', context)(module.exports, requireModule, module);
  function render() { cursor = 0; effectCursor = 0; return module.exports.default(); }
  async function flushEffects() {
    for (const effect of effects.filter(value => value.pending)) {
      effect.pending = false;
      cleanups.push(effect.work());
    }
    await new Promise(done => setImmediate(done));
  }
  return { render, flushEffects };
}

function elements(node, predicate) {
  if (Array.isArray(node)) return node.flatMap(value => elements(value, predicate));
  if (!node || typeof node !== 'object' || !node.props) return [];
  return [...(predicate(node) ? [node] : []), ...elements(node.props.children, predicate)];
}
function field(tree, name) { return elements(tree, node => node.type === 'TextField' && node.props.name === name)[0]; }
function form(tree) { return elements(tree, node => typeof node.props.onSubmit === 'function')[0]; }
const profile = { _id: 'mongo-A', name: 'Old name', email: 'driver@example.com', bio: 'Old bio',
  created_at: '2026-10-13', updated_at: null };

test('profile form keeps email read-only and displays the profile actually saved by the server', async () => {
  let submitted;
  const h = pageHarness('profile.tsx', { isAuthenticated: () => true,
    fetchUserProfile: async () => profile,
    updateUserProfile: async data => { submitted = data; return { ...profile, name: 'Saved name', bio: 'Saved bio' }; },
  });
  h.render(); await h.flushEffects();
  let tree = h.render();
  assert.equal(field(tree, 'email').props.InputProps.readOnly, true);
  field(tree, 'name').props.onChange({ target: { name: 'name', value: 'Entered name' } });
  field(tree, 'bio').props.onChange({ target: { name: 'bio', value: 'Entered bio' } });
  tree = h.render();
  await form(tree).props.onSubmit({ preventDefault() {} });
  tree = h.render();
  assert.equal(submitted.name, 'Entered name');
  assert.equal(submitted.bio, 'Entered bio');
  assert.equal('email' in submitted, false);
  assert.equal(field(tree, 'name').props.value, 'Saved name');
  assert.equal(field(tree, 'bio').props.value, 'Saved bio');
});

test('failed profile loading does not present an empty form that could overwrite saved data', async () => {
  const h = pageHarness('profile.tsx', { isAuthenticated: () => true,
    fetchUserProfile: async () => { throw new Error('Profile temporarily unavailable'); },
  });
  h.render(); await h.flushEffects(); const tree = h.render();
  assert.equal(elements(tree, node => node.type === 'form').length, 0);
  assert.equal(elements(tree, node => node.type === 'Alert')[0].props.children, 'Profile temporarily unavailable');
});

test('failed profile saving shows the server error without claiming success or discarding edits', async () => {
  const h = pageHarness('profile.tsx', { isAuthenticated: () => true,
    fetchUserProfile: async () => profile,
    updateUserProfile: async () => { throw new Error('Profile writes are unavailable'); },
  });
  h.render(); await h.flushEffects();
  field(h.render(), 'name').props.onChange({ target: { name: 'name', value: 'Unsaved edit' } });
  await form(h.render()).props.onSubmit({ preventDefault() {} });
  const tree = h.render();
  const alerts = elements(tree, node => node.type === 'Alert');
  assert.equal(alerts.length, 1);
  assert.equal(alerts[0].props.severity, 'error');
  assert.equal(field(tree, 'name').props.value, 'Unsaved edit');
});

test('password-reset failure is shown as an error and retains the entered address for retry', async () => {
  const h = pageHarness('reset-password.tsx', {
    reset_password: async () => { throw new Error('Email requests are unavailable'); },
  });
  let tree = h.render();
  field(tree, 'email').props.onChange({ target: { value: 'driver@example.com' } });
  await form(h.render()).props.onSubmit({ preventDefault() {} });
  tree = h.render();
  const alerts = elements(tree, node => node.type === 'Alert');
  assert.equal(alerts.length, 1);
  assert.equal(alerts[0].props.severity, 'error');
  assert.equal(field(tree, 'email').props.value, 'driver@example.com');
});

test('registration shows queued status and a failed verification resend stays retryable', async () => {
  const h = pageHarness('login.tsx', {
    verification_email: async () => { throw new Error('Could not queue verification email'); },
  }, { signup: async () => ({ message: 'Account created. Email queued.', emailStatus: 'queued' }) });
  let tree = h.render();
  elements(tree, node => node.type === 'Tabs')[0].props.onChange({}, 'signup');
  tree = h.render();
  for (const [name, value] of Object.entries({ name: 'Driver', email: 'driver@example.com',
    password: 'valid-password', confirmPassword: 'valid-password' })) {
    field(tree, name).props.onChange({ target: { value } });
  }
  await form(h.render()).props.onSubmit({ preventDefault() {} });
  tree = h.render();
  assert.equal(elements(tree, node => node.type === 'Alert')[0].props.children, 'Account created. Email queued.');
  const resend = elements(tree, node => node.type === 'Button' && String(node.props.children).includes('Resend'))[0];
  await resend.props.onClick();
  tree = h.render();
  const alert = elements(tree, node => node.type === 'Alert')[0];
  assert.equal(alert.props.severity, 'error');
  assert.equal(alert.props.children, 'Could not queue verification email');
  assert.ok(elements(tree, node => node.type === 'Button' && String(node.props.children).includes('Resend')).length);
});
