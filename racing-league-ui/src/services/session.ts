import { AuthUser, LoginResponse } from '../types/auth';

export const SESSION_KEY = 'racing-league.session';
export const SESSION_EVENT = 'racing-league:session';

export interface AuthSession {
  id: string;
  token: string;
  refreshToken: string;
  expiresAt: number;
  user: AuthUser;
}

function validUser(user: unknown): user is AuthUser {
  if (!user || typeof user !== 'object') return false;
  const value = user as Partial<AuthUser>;
  return typeof value.id === 'string' && !!value.id &&
    typeof value.mongoId === 'string' && !!value.mongoId &&
    typeof value.email === 'string' && !!value.email && typeof value.name === 'string';
}

function parseSession(value: string | null): AuthSession | null {
  if (!value) return null;
  try {
    const session = JSON.parse(value) as Partial<AuthSession>;
    return typeof session.id === 'string' && !!session.id &&
      typeof session.token === 'string' && !!session.token &&
      typeof session.refreshToken === 'string' && !!session.refreshToken &&
      typeof session.expiresAt === 'number' && Number.isFinite(session.expiresAt) &&
      validUser(session.user) ? session as AuthSession : null;
  } catch {
    return null;
  }
}

export function readSession(): AuthSession | null {
  const tabSession = sessionStorage.getItem(SESSION_KEY);
  // An explicit sign-out (or invalid tab record) must not activate another account.
  return tabSession !== null ? parseSession(tabSession) : parseSession(localStorage.getItem(SESSION_KEY));
}

function notifySession(): void {
  window.dispatchEvent(new Event(SESSION_EVENT));
}

export function clearLegacySession(): void {
  for (const storage of [sessionStorage, localStorage]) {
    storage.removeItem('token');
    storage.removeItem('user');
  }
}

export function sessionFromResponse(payload: LoginResponse, id: string = crypto.randomUUID()): AuthSession {
  if (typeof payload.token !== 'string' || !payload.token ||
      typeof payload.refreshToken !== 'string' || !payload.refreshToken ||
      !Number.isFinite(payload.expiresIn) || payload.expiresIn <= 0 || !validUser(payload.user)) {
    throw new Error('The authentication response was incomplete. Please try again.');
  }
  return { id, token: payload.token, refreshToken: payload.refreshToken,
    expiresAt: Date.now() + payload.expiresIn * 1000, user: payload.user };
}

export function saveNewSession(session: AuthSession, remember: boolean): void {
  clearLegacySession();
  const storage = remember ? localStorage : sessionStorage;
  const other = remember ? sessionStorage : localStorage;
  // Write the complete identity and credentials together.
  storage.setItem(SESSION_KEY, JSON.stringify(session));
  other.removeItem(SESSION_KEY);
  notifySession();
}

export function replaceSession(session: AuthSession, expected: AuthSession): AuthSession | null {
  const current = readSession();
  if (!current || current.id !== expected.id) return null;
  if (current.token !== expected.token || current.refreshToken !== expected.refreshToken) return current;
  const storage = parseSession(sessionStorage.getItem(SESSION_KEY))?.id === current.id
    ? sessionStorage : localStorage;
  storage.setItem(SESSION_KEY, JSON.stringify(session));
  notifySession();
  return session;
}

export function updateSessionUser(user: AuthUser, expectedId: string): void {
  const current = readSession();
  if (!current || current.id !== expectedId || current.user.id !== user.id || !validUser(user)) return;
  replaceSession({ ...current, user }, current);
}

export function clearSession(expectedId?: string): boolean {
  if (expectedId && readSession()?.id !== expectedId) return false;
  for (const storage of [sessionStorage, localStorage]) {
    const stored = parseSession(storage.getItem(SESSION_KEY));
    if (!expectedId || stored?.id === expectedId) storage.removeItem(SESSION_KEY);
  }
  sessionStorage.setItem(SESSION_KEY, 'null');
  clearLegacySession();
  notifySession();
  return true;
}
