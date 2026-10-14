const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const crypto = require('node:crypto');
const ts = require('typescript');
const axios = require('axios');

function storage() {
  const values = new Map();
  return { getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, String(value)),
    removeItem: key => values.delete(key) };
}

function deferred() {
  let resolve;
  const promise = new Promise(done => { resolve = done; });
  return { promise, resolve };
}

function payload(id = 'A', token = 'token-' + id) {
  return { token, refreshToken: 'refresh-' + token, expiresIn: 3600,
    user: { id, mongoId: 'mongo-' + id, email: id + '@example.test', name: id } };
}

function harness(handler, shared = storage()) {
  const requests = [];
  const sessionStorage = storage();
  const events = [];
  const loggedErrors = [];
  const location = { pathname: '/profile', href: '', reload() {} };
  const fakeAxios = { ...axios, create: options => axios.create({ ...options, adapter: async config => {
    requests.push(config);
    const result = await handler(config);
    const response = { status: result.status ?? 200, data: result.data, statusText: '', headers: {}, config };
    if (response.status >= 400) throw new axios.AxiosError('Request failed', 'ERR_BAD_REQUEST', config, null, response);
    return response;
  } }) };
  const context = vm.createContext({ console: { ...console, error: (...args) => loggedErrors.push(args) }, crypto: crypto.webcrypto, Date, Promise, Map,
    Event: class Event { constructor(type) { this.type = type; } },
    navigator: {}, localStorage: shared, sessionStorage,
    window: { location, dispatchEvent: event => events.push(event.type) } });
  const cache = new Map();
  function load(file) {
    file = path.resolve(__dirname, '..', file);
    if (cache.has(file)) return cache.get(file).exports;
    const module = { exports: {} };
    cache.set(file, module);
    const source = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
      compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS, esModuleInterop: true },
    }).outputText;
    const requireModule = name => {
      if (name === 'axios') return fakeAxios;
      if (name === '../config/config') return { __esModule: true, default: { api: { baseUrl: 'https://api.test/api' } } };
      return load(path.relative(path.resolve(__dirname, '..'), path.resolve(path.dirname(file), name + '.ts')));
    };
    vm.runInContext('(function(exports,require,module){' + source + '\n})', context, { filename: file })(
      module.exports, requireModule, module);
    return module.exports;
  }
  const sessions = load('src/services/session.ts');
  const client = load('src/services/auth-client.ts');
  function signIn(id = 'A', remember = false, expiresAt) {
    const session = sessions.sessionFromResponse(payload(id));
    if (expiresAt !== undefined) session.expiresAt = expiresAt;
    sessions.saveNewSession(session, remember);
    return session;
  }
  return { client, sessions, signIn, requests, sessionStorage, localStorage: shared, location, context, events, load, loggedErrors };
}

test('screenshot API keeps multipart files, uses the image timeout, and rejects invalid batches before sending', async () => {
  const h = harness(request => {
    assert.ok(request.data instanceof FormData);
    assert.equal(request.data.getAll('images').length, 2);
    assert.equal(request.headers.get('Authorization'), 'Bearer token-A');
    assert.equal(request.timeout, 60000);
    assert.notEqual(request.headers.get('Content-Type'), 'application/json');
    return { data: { results: [{ driver: 'Ann', position: 1 }] } };
  });
  h.context.FormData = FormData;
  h.signIn();
  const api = h.load('src/services/api.ts');
  const image = new File(['fake-image-bytes'], 'race.png', { type: 'image/png' });
  const result = await api.processMultipleRaceScreenshots([image, image], 'league', 'race');
  assert.equal(result.results[0].driver, 'Ann');
  assert.equal(h.requests[0].url, '/v1/leagues/league/races/race/extract-results');
  for (const files of [[], [image, image, image], [new File([], 'empty.png', { type: 'image/png' })],
    [new File(['gif'], 'image.gif', { type: 'image/gif' })]]) {
    await assert.rejects(api.processMultipleRaceScreenshots(files, 'league', 'race'));
  }
  assert.equal(h.requests.length, 1);
});

test('paged discovery is anonymous and sends only the requested page and trimmed search', async () => {
  const h = harness(request => {
    assert.equal(request.url, '/v1/leagues/discovery');
    assert.equal(request.headers.get('Authorization'), undefined);
    assert.deepEqual({ ...request.params }, { page: 2, page_size: 9, q: 'Spa' });
    return { data: { leagues: [], total: 0, total_pages: 0, page: 2, page_size: 9 } };
  });
  h.signIn();
  await h.load('src/services/api.ts').fetchPublicLeagues(2, 9, ' Spa ');
  assert.equal(h.requests.length, 1);
});

test('different accounts in separate tabs retain paired credentials and identity', () => {
  const shared = storage();
  const a = harness(() => ({}), shared);
  const b = harness(() => ({}), shared);
  a.signIn('A'); b.signIn('B');
  assert.equal(a.sessions.readSession().user.id, 'A');
  assert.equal(a.sessions.readSession().token, 'token-A');
  assert.equal(b.sessions.readSession().user.id, 'B');
});

test('new login clears legacy storage and writes one complete credential record', () => {
  const h = harness(() => ({}));
  h.localStorage.setItem('token', 'legacy-token');
  h.localStorage.setItem('user', '{"id":"wrong"}');
  h.signIn('A', true);
  assert.equal(h.sessionStorage.getItem(h.sessions.SESSION_KEY), null);
  assert.equal(h.localStorage.getItem('token'), null);
  assert.equal(h.localStorage.getItem('user'), null);
  h.signIn('B', false);
  assert.equal(h.localStorage.getItem(h.sessions.SESSION_KEY), null);
  assert.equal(h.sessions.readSession().user.id, 'B');
});

test('near-expiry concurrent requests share one renewal and use the new token', async () => {
  const ready = deferred(); const release = deferred();
  const h = harness(async request => {
    if (request.url === '/v1/auth/refresh') {
      ready.resolve(); await release.promise;
      assert.equal(JSON.parse(request.data).refreshToken, 'refresh-token-A');
      assert.equal(request.headers.get('Authorization'), undefined);
      return { data: payload('A', 'fresh-token') };
    }
    assert.equal(request.headers.get('Authorization'), 'Bearer fresh-token');
    return { data: { ok: true } };
  });
  const original = h.signIn('A', false, Date.now() - 1000);
  const calls = Promise.all([1, 2, 3].map(i => h.client.default.get('/v1/private/' + i)));
  await ready.promise; release.resolve(); await calls;
  assert.equal(h.requests.filter(r => r.url === '/v1/auth/refresh').length, 1);
  assert.equal(h.sessions.readSession().id, original.id);
  assert.equal(h.sessions.readSession().refreshToken, 'refresh-fresh-token');
});

test('remembered sessions coordinate renewal across tabs using Web Locks', async () => {
  const shared = storage();
  const queues = new Map();
  const locks = { request: (name, work) => {
    const operation = (queues.get(name) || Promise.resolve()).then(work);
    queues.set(name, operation.catch(() => {}));
    return operation;
  } };
  let exchanges = 0;
  const handler = request => {
    if (request.url === '/v1/auth/refresh') {
      exchanges++;
      return { data: payload('A', 'fresh-shared-token') };
    }
    assert.equal(request.headers.get('Authorization'), 'Bearer fresh-shared-token');
    return { data: { ok: true } };
  };
  const a = harness(handler, shared);
  const b = harness(handler, shared);
  a.context.navigator.locks = locks;
  b.context.navigator.locks = locks;
  a.signIn('A', true, Date.now() - 1000);
  await Promise.all([a.client.default.get('/v1/private'), b.client.default.get('/v1/private')]);
  assert.equal(exchanges, 1);
  assert.equal(a.sessions.readSession().token, b.sessions.readSession().token);
});

test('a refresh network failure keeps the session without exposing credentials', async () => {
  const h = harness(request => {
    throw new axios.AxiosError('Network Error', 'ERR_NETWORK', request);
  });
  const original = h.signIn('A', false, Date.now() - 1000);
  await assert.rejects(h.client.default.get('/v1/private'), error => {
    assert.equal('config' in error, false);
    assert.equal(JSON.stringify(error).includes(original.refreshToken), false);
    return true;
  });
  assert.equal(h.sessions.readSession().id, original.id);
  assert.equal(h.location.href, '');
});

test('an expired-token response renews and retries exactly once', async () => {
  const h = harness(request => {
    if (request.url === '/v1/auth/refresh') return { data: payload('A', 'fresh') };
    if (request.headers.get('Authorization') === 'Bearer token-A') {
      return { status: 401, data: { message: 'Expired', code: 'token_expired' } };
    }
    return { data: { ok: true } };
  });
  h.signIn();
  assert.equal((await h.client.default.get('/v1/private')).data.ok, true);
  assert.equal(h.requests.length, 3);
});

test('a second expired response stops retrying and signs out', async () => {
  const h = harness(request => request.url === '/v1/auth/refresh' ? { data: payload('A', 'fresh') } :
    { status: 401, data: { message: 'Expired', code: 'token_expired' } });
  h.signIn();
  await assert.rejects(h.client.default.get('/v1/private'));
  assert.equal(h.requests.length, 3);
  assert.equal(h.sessions.readSession(), null);
});

test('permission denial preserves a valid session and exposes no request credentials', async () => {
  const h = harness(() => ({ status: 403, data: { message: 'Forbidden' } }));
  h.signIn();
  await assert.rejects(h.client.default.get('/v1/private'), error => {
    assert.equal(error.response.status, 403);
    assert.equal('config' in error, false);
    assert.equal(JSON.stringify(error).includes('token-A'), false);
    return true;
  });
  assert.equal(h.sessions.readSession().user.id, 'A');
  assert.equal(h.location.href, '');
});

test('revoked sessions are cleared without attempting renewal', async () => {
  const h = harness(() => ({ status: 401, data: { message: 'Revoked', code: 'token_revoked' } }));
  h.signIn();
  await assert.rejects(h.client.default.get('/v1/private'));
  assert.equal(h.requests.length, 1);
  assert.equal(h.sessions.readSession(), null);
  assert.equal(h.location.href, '/login');
});

test('temporary refresh failure preserves credentials and does not send a stale request', async () => {
  const h = harness(() => ({ status: 503, data: { message: 'Try again', code: 'auth_unavailable' } }));
  const original = h.signIn('A', false, Date.now() - 1000);
  await assert.rejects(h.client.default.get('/v1/private'));
  assert.equal(h.sessions.readSession().token, original.token);
  assert.equal(h.sessions.readSession().refreshToken, original.refreshToken);
  assert.equal(h.requests.length, 1);
  assert.equal(h.location.href, '');
});

test('invalid refresh credentials and mismatched refreshed identity end the session', async () => {
  for (const response of [
    { status: 401, data: { message: 'Expired', code: 'invalid_refresh_token' } }, { data: payload('B') },
  ]) {
    const h = harness(() => response);
    h.signIn('A', false, Date.now() - 1000);
    await assert.rejects(h.client.default.get('/v1/private'));
    assert.equal(h.sessions.readSession(), null);
  }
});

test('logout while renewal is pending cannot resurrect credentials', async () => {
  const ready = deferred(); const release = deferred();
  const h = harness(async () => { ready.resolve(); await release.promise; return { data: payload('A', 'fresh') }; });
  h.signIn('A', false, Date.now() - 1000);
  const call = h.client.default.get('/v1/private');
  const failed = assert.rejects(call);
  await ready.promise;
  await h.client.logoutSession(); release.resolve(); await failed;
  assert.equal(h.sessions.readSession(), null);
});

test('late success or rejection from account A cannot affect account B', async () => {
  for (const status of [200, 401]) {
    const ready = deferred(); const release = deferred();
    const h = harness(async () => {
      ready.resolve(); await release.promise;
      return { status, data: { message: 'Revoked', code: 'token_revoked', privateAccount: 'A' } };
    });
    h.signIn('A');
    const failed = assert.rejects(h.client.default.get('/v1/private'));
    await ready.promise; h.signIn('B'); release.resolve(); await failed;
    assert.equal(h.sessions.readSession().user.id, 'B');
    assert.equal(h.location.href, '');
  }
});

test('late renewal cannot overwrite a new login', async () => {
  const ready = deferred(); const release = deferred();
  const h = harness(async () => { ready.resolve(); await release.promise; return { data: payload('A', 'fresh') }; });
  const original = h.signIn('A');
  const failed = assert.rejects(h.client.refreshSession(original));
  await ready.promise; h.signIn('B'); release.resolve(); await failed;
  assert.equal(h.sessions.readSession().user.id, 'B');
});

test('logout invalidates a pending login response', async () => {
  const ready = deferred(); const release = deferred();
  const h = harness(async () => { ready.resolve(); await release.promise; return { data: payload('A') }; });
  const failed = assert.rejects(h.client.authenticate('A@example.test', 'secret'));
  await ready.promise; await h.client.logoutSession(); release.resolve(); await failed;
  assert.equal(h.sessions.readSession(), null);
});

test('verification replaces cached profile with the server identity', async () => {
  const h = harness(() => ({ data: { user: { ...payload().user, name: 'Fresh profile' } } }));
  h.signIn();
  const user = await h.client.fetchAuthUser();
  assert.equal(user.name, 'Fresh profile');
  assert.equal(h.sessions.readSession().user.name, 'Fresh profile');
});

test('public requests and rejected login do not attach or clear existing credentials', async () => {
  const h = harness(request => {
    assert.equal(request.headers.get('Authorization'), undefined);
    return { status: 401, data: { message: 'Invalid credentials' } };
  });
  h.signIn();
  await assert.rejects(h.client.default.get('/v1/leagues/all'));
  await assert.rejects(h.client.authenticate('B@example.test', 'secret'));
  assert.equal(h.sessions.readSession().user.id, 'A');
  assert.equal(h.location.href, '');
});

test('a stale refresh rejection preserves a token already renewed by another tab', async () => {
  const ready = deferred(); const release = deferred(); const shared = storage();
  const h = harness(async () => { ready.resolve(); await release.promise;
    return { status: 401, data: { code: 'invalid_refresh_token' } }; }, shared);
  const other = harness(() => ({}), shared);
  const original = h.signIn('A', true);
  const refreshing = h.client.refreshSession(original);
  await ready.promise;
  other.sessions.replaceSession(other.sessions.sessionFromResponse(payload('A', 'fresh'), original.id), original);
  release.resolve();
  assert.equal((await refreshing).token, 'fresh');
  assert.equal(h.sessions.readSession().token, 'fresh');
});

test('signing out a tab does not silently activate a different remembered account', async () => {
  const shared = storage(); const a = harness(() => ({}), shared); const b = harness(() => ({}), shared);
  a.signIn('A'); b.signIn('B', true);
  await a.client.logoutSession();
  assert.equal(a.sessions.readSession(), null);
  assert.equal(b.sessions.readSession().user.id, 'B');
});

test('password-change completion cannot clear a newer account session', () => {
  const h = harness(() => ({})); const original = h.signIn('A'); h.signIn('B');
  h.client.passwordChanged(original.id);
  assert.equal(h.sessions.readSession().user.id, 'B');
  assert.equal(h.location.href, '');
});

test('saved profile updates canonical cached identity while preserving credentials', async () => {
  const h = harness(() => ({ data: { _id: 'mongo-A', name: 'Saved name', email: 'A@example.test', bio: 'Saved bio' } }));
  const original = h.signIn('A');
  const api = h.load('src/services/api.ts');
  const saved = await api.updateUserProfile({ name: 'Entered name', bio: 'Entered bio' });
  assert.equal(saved.bio, 'Saved bio');
  assert.equal(h.sessions.readSession().user.name, 'Saved name');
  assert.equal(h.sessions.readSession().id, original.id);
  assert.equal(h.sessions.readSession().token, original.token);
  assert.equal(h.sessions.readSession().refreshToken, original.refreshToken);
});

test('profile rejection leaves cached identity and credentials intact', async () => {
  const h = harness(() => ({ status: 400, data: { message: 'Name is required', code: 'invalid_profile' } }));
  const original = h.signIn('A');
  const api = h.load('src/services/api.ts');
  await assert.rejects(api.updateUserProfile({ name: '' }), /Name is required/);
  assert.equal(h.sessions.readSession().user.name, original.user.name);
  assert.equal(h.sessions.readSession().token, original.token);
});

test('late profile response cannot update a newer account', async () => {
  const ready = deferred(); const release = deferred();
  const h = harness(async () => { ready.resolve(); await release.promise;
    return { data: { _id: 'mongo-A', name: 'Saved for A', email: 'A@example.test', bio: '' } }; });
  h.signIn('A');
  const api = h.load('src/services/api.ts');
  const pending = api.updateUserProfile({ name: 'Saved for A' });
  await ready.promise; h.signIn('B'); release.resolve();
  await assert.rejects(pending, /session changed/);
  assert.equal(h.sessions.readSession().user.id, 'B');
  assert.equal(h.sessions.readSession().user.name, 'B');
});

test('registration returns queued-email status without signing in or sending an existing token', async () => {
  const h = harness(request => {
    assert.equal(request.url, '/v1/auth/register');
    assert.equal(request.headers.get('Authorization'), undefined);
    return { status: 201, data: { uid: 'new-user', emailStatus: 'queued', message: 'Account created. Email queued.' } };
  });
  const existing = h.signIn('A');
  const result = await h.client.register('Name', 'new@example.test', 'new-password');
  assert.equal(result.emailStatus, 'queued');
  assert.equal(result.message, 'Account created. Email queued.');
  assert.equal(h.sessions.readSession().id, existing.id);
});

test('account email requests return queued status and surface outages without ending a session', async () => {
  const h = harness(request => {
    assert.equal(request.headers.get('Authorization'), undefined);
    return request.url.includes('reset-password')
      ? { status: 202, data: { message: 'If eligible, an email is queued.', code: 'email_queued' } }
      : { status: 503, data: { message: 'Email requests are temporarily unavailable.', code: 'email_unavailable' } };
  });
  const original = h.signIn('A');
  const api = h.load('src/services/api.ts');
  const reset = await api.reset_password('new@example.test');
  assert.equal(reset.code, 'email_queued');
  await assert.rejects(api.verification_email('new@example.test'), /temporarily unavailable/);
  assert.equal(h.sessions.readSession().id, original.id);
});
