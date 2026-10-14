const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const root = path.resolve(__dirname, '..');

async function configure(command, apiUrl, mode = command === 'build' ? 'production' : 'development') {
  const previous = process.env.VITE_API_URL;
  // Existing developer env files must not determine isolated test outcomes.
  process.env.VITE_API_URL = apiUrl;
  try {
    const { resolveConfig } = await import('vite');
    return await resolveConfig({ root, configFile: path.join(root, 'vite.config.ts'),
      logLevel: 'silent' }, command, mode);
  } finally {
    if (previous === undefined) delete process.env.VITE_API_URL;
    else process.env.VITE_API_URL = previous;
  }
}

function selectedUrl(config) {
  return JSON.parse(config.define['import.meta.env.VITE_API_URL']);
}

test('development without an override uses the local backend and API prefix', async () => {
  assert.equal(selectedUrl(await configure('serve', '')), 'http://localhost:5000/api');
});

test('missing build configuration fails before bundling in every mode', async () => {
  for (const mode of ['production', 'development', 'staging']) {
    await assert.rejects(configure('build', '', mode), /VITE_API_URL is required for builds/);
  }
});

test('malformed or credential-bearing API URLs fail with sanitized errors', async () => {
  for (const value of ['/api', 'not-a-url', 'ftp://api.example.test/api',
    'https://api.example.test', 'https://user:private-password@api.example.test/api',
    'https://api.example.test/api?key=private-key', 'https://api.example.test/api#fragment',
    'https://api.example.test/api?', 'https://api.example.test/api#']) {
    await assert.rejects(configure('build', value), error => {
      assert.match(error.message, /VITE_API_URL must be an absolute HTTP\(S\) URL/);
      for (const detail of ['api.example.test', 'private-password', 'private-key']) {
        assert.equal(error.message.includes(detail), false);
      }
      return true;
    });
  }
  await assert.rejects(configure('serve', '/api'), /VITE_API_URL must be/);
});

test('an explicit build URL retains the API path and removes trailing slashes', async () => {
  assert.equal(selectedUrl(await configure('build', ' https://api.example.test/api/// ')),
    'https://api.example.test/api');
  assert.equal(selectedUrl(await configure('build', 'https://api.example.test/gateway/api/')),
    'https://api.example.test/gateway/api');
});

test('the build environment overrides local frontend configuration', async () => {
  for (const command of ['serve', 'build']) {
    assert.equal(selectedUrl(await configure(command, 'https://chosen.example.test/api')),
      'https://chosen.example.test/api');
  }
});
