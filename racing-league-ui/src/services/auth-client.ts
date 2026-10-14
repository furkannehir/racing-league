import axios, { InternalAxiosRequestConfig } from 'axios';
import config from '../config/config';
import { AuthUser, LoginResponse, RegistrationResponse } from '../types/auth';
import {
  AuthSession, readSession, saveNewSession, replaceSession, sessionFromResponse,
  clearSession, updateSessionUser,
} from './session';

interface ErrorBody { message?: string; code?: string; }
interface SessionRequest extends InternalAxiosRequestConfig {
  sessionId?: string;
  authRetried?: boolean;
}

export class ApiError extends Error {
  readonly response?: { status: number; data: ErrorBody };
  constructor(message: string, status?: number, code?: string) {
    super(message);
    this.name = 'ApiError';
    if (status) this.response = { status, data: { message, code } };
  }
}

function safeError(error: unknown): ApiError {
  if (error instanceof ApiError) return error;
  if (axios.isAxiosError<ErrorBody>(error)) {
    return new ApiError(error.response?.data?.message ||
      (error.response ? 'The request failed. Please try again.' : 'Network error. Please try again.'),
      error.response?.status, error.response?.data?.code);
  }
  return new ApiError(error instanceof Error ? error.message : 'The request failed. Please try again.');
}

const options = { baseURL: config.api.baseUrl, timeout: 15000,
  headers: { Accept: 'application/json', 'Content-Type': 'application/json' } };
const credentialsApi = axios.create(options);
credentialsApi.interceptors.response.use(response => response, error => Promise.reject(safeError(error)));
const api = axios.create(options);
const refreshes = new Map<string, Promise<AuthSession>>();
let loginAttempt = 0;

function endSession(sessionId: string): void {
  if (clearSession(sessionId) && window.location.pathname !== '/login') {
    window.location.href = '/login';
  }
}

function sessionChanged(): ApiError {
  return new ApiError('Your session changed. Please try again.', 409, 'session_changed');
}

async function exchangeRefresh(snapshot: AuthSession): Promise<AuthSession> {
  const current = readSession();
  if (!current || current.id !== snapshot.id) throw sessionChanged();
  if (current.token !== snapshot.token || current.refreshToken !== snapshot.refreshToken) return current;
  try {
    const response = await credentialsApi.post<LoginResponse>('/v1/auth/refresh', {
      refreshToken: current.refreshToken,
    });
    const next = sessionFromResponse(response.data, current.id);
    if (next.user.id !== current.user.id) {
      throw new ApiError('Your session is invalid. Please sign in again.', 401, 'invalid_session');
    }
    const stored = replaceSession(next, current);
    if (!stored) throw sessionChanged();
    return stored;
  } catch (error) {
    const failure = safeError(error);
    const latest = readSession();
    if (latest?.id === current.id &&
        (latest.token !== current.token || latest.refreshToken !== current.refreshToken)) return latest;
    if (failure.response?.status === 401) endSession(current.id);
    throw failure;
  }
}

export async function refreshSession(snapshot: AuthSession): Promise<AuthSession> {
  const pending = refreshes.get(snapshot.id);
  if (pending) return pending;
  const operation = (async () => {
    if (typeof navigator !== 'undefined' && navigator.locks) {
      return navigator.locks.request('racing-league-refresh:' + snapshot.id, () => exchangeRefresh(snapshot));
    }
    return exchangeRefresh(snapshot);
  })();
  refreshes.set(snapshot.id, operation);
  try { return await operation; }
  finally { if (refreshes.get(snapshot.id) === operation) refreshes.delete(snapshot.id); }
}

function anonymousRequest(url = ''): boolean {
  const path = url.split('?')[0].replace(/^\//, '');
  return (path.startsWith('v1/auth/') && !['v1/auth/verify', 'v1/auth/logout'].includes(path)) ||
    ['v1/leagues/all', 'v1/leagues/public', 'v1/leagues/discovery', 'v1/point-systems'].includes(path);
}

api.interceptors.request.use(async (request: SessionRequest) => {
  if (anonymousRequest(request.url)) {
    request.headers.delete('Authorization');
    return request;
  }
  const snapshot = readSession();
  if (request.sessionId && request.sessionId !== snapshot?.id) throw sessionChanged();
  if (snapshot) {
    const session = snapshot.expiresAt <= Date.now() + 60000 ? await refreshSession(snapshot) : snapshot;
    if (readSession()?.id !== session.id) throw sessionChanged();
    request.headers.set('Authorization', `Bearer ${session.token}`);
    request.sessionId = session.id;
  } else {
    request.headers.delete('Authorization');
  }
  return request;
});

api.interceptors.response.use(response => {
  const request = response.config as SessionRequest;
  if (request.sessionId && request.sessionId !== readSession()?.id) throw sessionChanged();
  return response;
}, async (error: unknown) => {
  const failure = safeError(error);
  const request = axios.isAxiosError(error) ? error.config as SessionRequest | undefined : undefined;
  if (failure.response?.status !== 401 || !request || anonymousRequest(request.url)) throw failure;
  const current = readSession();
  // A late failure from an old account must not clear or retry a new account's session.
  if (!current || current.id !== request.sessionId) throw failure;
  if (failure.response.data.code === 'token_expired' && !request.authRetried) {
    request.authRetried = true;
    const token = request.headers.get('Authorization');
    if (token === `Bearer ${current.token}`) await refreshSession(current);
    return api.request(request);
  }
  endSession(current.id);
  throw failure;
});

export async function authenticate(email: string, password: string, remember = false): Promise<AuthUser> {
  const attempt = ++loginAttempt;
  const response = await credentialsApi.post<LoginResponse>('/v1/auth/login', { email, password });
  if (attempt !== loginAttempt) throw sessionChanged();
  const session = sessionFromResponse(response.data);
  saveNewSession(session, remember);
  return session.user;
}

export async function register(name: string, email: string, password: string): Promise<RegistrationResponse> {
  const response = await credentialsApi.post<RegistrationResponse>('/v1/auth/register', { name, email, password });
  return response.data;
}

export async function fetchAuthUser(): Promise<AuthUser> {
  const snapshot = readSession();
  if (!snapshot) throw new ApiError('Please sign in again.', 401, 'missing_token');
  const response = await api.get<{ user: AuthUser }>('/v1/auth/verify');
  if (readSession()?.id !== snapshot.id) throw sessionChanged();
  if (response.data.user.id !== snapshot.user.id) {
    endSession(snapshot.id);
    throw new ApiError('Your session is invalid. Please sign in again.', 401, 'invalid_session');
  }
  updateSessionUser(response.data.user, snapshot.id);
  return response.data.user;
}

export async function logoutSession(allDevices = false): Promise<void> {
  ++loginAttempt;
  const snapshot = readSession();
  try {
    if (allDevices && snapshot) {
      const session = snapshot.expiresAt <= Date.now() + 60000 ? await refreshSession(snapshot) : snapshot;
      await credentialsApi.post('/v1/auth/logout', { allDevices: true }, {
        headers: { Authorization: `Bearer ${session.token}` },
      });
    }
  } finally {
    if (snapshot) clearSession(snapshot.id);
  }
}

export function passwordChanged(expectedId: string, revocationFailed = false): void {
  const current = readSession();
  if (current?.id === expectedId && clearSession(expectedId)) {
    ++loginAttempt;
    window.location.href = '/login?reason=' +
      (revocationFailed ? 'password-changed-revocation-failed' : 'password-changed');
  }
}

export default api;
