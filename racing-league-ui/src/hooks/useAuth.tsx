import { useState, useEffect, useRef, createContext, useContext } from 'react';
import { checkAuth } from '../services/api';
import { ApiError, authenticate, register, logoutSession } from '../services/auth-client';
import { SESSION_EVENT, SESSION_KEY, readSession, clearLegacySession } from '../services/session';
import { AuthUser, RegistrationResponse } from '../types/auth';

export type User = AuthUser;

interface AuthContextType {
  isAuthenticated: boolean;
  user: User | null;
  login: (email: string, password: string, remember?: boolean) => Promise<void>;
  signup: (name: string, email: string, password: string) => Promise<RegistrationResponse>;
  googleLogin: () => Promise<void>;
  logout: () => Promise<void>;
  loading: boolean;
  error: string | null;
}

const AuthContext = createContext<AuthContextType | null>(null);

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

export const AuthProvider = ({ children }: { children: React.ReactNode }) => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const active = useRef(readSession());

  const login = async (email: string, password: string, remember = false): Promise<void> => {
    setLoading(true);
    setError(null);
    try {
      await authenticate(email, password, remember);
      const current = readSession();
      setUser(current?.user || null);
      setIsAuthenticated(!!current);
    } catch (failure) {
      setError(errorMessage(failure, 'Sign-in failed. Please try again.'));
      throw failure;
    } finally {
      setLoading(false);
    }
  };

  const signup = async (name: string, email: string, password: string): Promise<RegistrationResponse> => {
    setLoading(true);
    setError(null);
    try {
      return await register(name, email, password);
    } catch (failure) {
      setError(errorMessage(failure, 'Registration failed. Please try again.'));
      throw failure;
    } finally {
      setLoading(false);
    }
  };

  const googleLogin = async (): Promise<void> => {
    const failure = new Error('Google sign-in is not available yet.');
    setError(failure.message);
    throw failure;
  };

  const logout = async (): Promise<void> => {
    setLoading(true);
    try {
      await logoutSession();
    } finally {
      const current = readSession();
      setUser(current?.user || null);
      setIsAuthenticated(!!current);
      setLoading(false);
    }
  };

  useEffect(() => {
    let cancelled = false;
    clearLegacySession();
    const synchronize = (event: Event) => {
      if (event instanceof StorageEvent && event.key !== SESSION_KEY && event.key !== null) return;
      const next = readSession();
      if (event.type === 'storage' && active.current && next &&
          active.current.user.id !== next.user.id) {
        // Discard page data belonging to the previous shared account.
        window.location.reload();
        return;
      }
      active.current = next;
      setUser(next?.user || null);
      setIsAuthenticated(!!next);
    };
    window.addEventListener(SESSION_EVENT, synchronize);
    window.addEventListener('storage', synchronize);

    const verifyUser = async () => {
      const snapshot = readSession();
      if (!snapshot) {
        setLoading(false);
        return;
      }
      try {
        const verifiedUser = await checkAuth();
        if (!cancelled && readSession()?.id === snapshot.id) {
          setUser(verifiedUser);
          setIsAuthenticated(true);
        }
      } catch (failure) {
        if (!cancelled && readSession()?.id === snapshot.id &&
            (!(failure instanceof ApiError) || failure.response?.status !== 401)) {
          // Keep previously verified credentials during a temporary outage.
          setUser(readSession()?.user || snapshot.user);
          setIsAuthenticated(true);
          setError(errorMessage(failure, 'Session verification is temporarily unavailable.'));
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    void verifyUser();
    return () => {
      cancelled = true;
      window.removeEventListener(SESSION_EVENT, synchronize);
      window.removeEventListener('storage', synchronize);
    };
  }, []);

  return (
    <AuthContext.Provider value={{ isAuthenticated, user, login, signup, googleLogin, logout, loading, error }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within an AuthProvider');
  return context;
};
