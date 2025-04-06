import { useState, useEffect, createContext, useContext } from 'react';
import api, { checkAuth } from '../services/api';

// User interface
export interface User {
  id: string;
  username: string;
  email: string;
  name: string;
  profilePicture?: string;
}

// Auth context interface
interface AuthContextType {
  isAuthenticated: boolean;
  user: User | null;
  login: (email: string, password: string, remember?: boolean) => Promise<void>;
  signup: (name: string, email: string, password: string) => Promise<void>;
  googleLogin: () => Promise<void>;
  logout: () => void;
  loading: boolean;
  error: string | null;
}

// Create auth context
const AuthContext = createContext<AuthContextType | null>(null);

export const AuthProvider = ({ children }: { children: React.ReactNode }) => {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Login with username/password
  const login = async (email: string, password: string, remember: boolean = false): Promise<void> => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await api.post('/v1/auth/login', {
        email,
        password
      });

      const { token, user } = response.data;
      
      // Store token based on remember preference
      if (remember) {
        localStorage.setItem('token', token);
      } else {
        sessionStorage.setItem('token', token);
      }
      
      localStorage.setItem('user', JSON.stringify(user));
      setUser(user);
      setIsAuthenticated(true);
    } catch (err: any) {
      const errorMessage = err.response?.data?.message || 
                          err.response?.data?.error || 
                          err.message || 
                          'Authentication failed. Please try again.';
      setError(errorMessage);
      throw new Error(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  // Register new user
  const signup = async (name: string, email: string, password: string): Promise<void> => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await api.post('/register', {
        name,
        email,
        password
      });

      const { token, user } = response.data;
      
      // Store in session storage by default for new users
      sessionStorage.setItem('token', token);
      localStorage.setItem('user', JSON.stringify(user));
      
      setUser(user);
      setIsAuthenticated(true);
    } catch (err: any) {
      const errorMessage = err.response?.data?.message || 
                          err.response?.data?.error || 
                          err.message || 
                          'Registration failed. Please try again.';
      setError(errorMessage);
      throw new Error(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  // Login with Google OAuth
  const googleLogin = async (): Promise<void> => {
    try {
      setLoading(true);
      setError(null);
      
      // Open Google OAuth window
      const googleAuthUrl = `${import.meta.env.VITE_API_URL}/auth/google`;
      
      // Open a popup window for Google login
      const width = 500;
      const height = 600;
      const left = window.screenX + (window.outerWidth - width) / 2;
      const top = window.screenY + (window.outerHeight - height) / 2;
      
      const popup = window.open(
        googleAuthUrl,
        'googleAuth',
        `width=${width},height=${height},left=${left},top=${top}`
      );
      
      // Poll the popup to check for completion
      const pollTimer = setInterval(() => {
        if (!popup || popup.closed) {
          clearInterval(pollTimer);
          setLoading(false);
          
          // Check if token was stored during redirect
          const token = localStorage.getItem('token') || sessionStorage.getItem('token');
          if (token) {
            setIsAuthenticated(true);
          } else {
            setError('Google login failed or was cancelled');
          }
        }
      }, 500);
      
    } catch (err: any) {
      setError('Failed to initialize Google login');
      setLoading(false);
      throw new Error('Google login initialization failed');
    }
  };

  // Logout
  const logout = async (): Promise<void> => {
    try {
      // Call logout API if available
      await api.get('/v1/auth/logout').catch(() => {
        // Ignore errors from logout endpoint
      });
    } finally {
      // Always clear local storage regardless of API response
      localStorage.removeItem('token');
      sessionStorage.removeItem('token');
      localStorage.removeItem('user');
      setUser(null);
      setIsAuthenticated(false);
    }
  };

  // Check authentication status on mount
  useEffect(() => {
    const verifyUser = async () => {
      setLoading(true);
      
      try {
        const token = localStorage.getItem('token') || sessionStorage.getItem('token');
        const storedUser = localStorage.getItem('user');
        
        if (!token) {
          setLoading(false);
          return;
        }
        
        // Set initial state from stored data
        if (storedUser) {
          setUser(JSON.parse(storedUser));
          setIsAuthenticated(true);
        }
        
        // Validate token with server using checkAuth
        const isValid = await checkAuth();
        
        if (isValid) {
          setIsAuthenticated(true);
        } else {
          // Token is invalid, clear auth state
          localStorage.removeItem('token');
          sessionStorage.removeItem('token');
          localStorage.removeItem('user');
          setUser(null);
          setIsAuthenticated(false);
        }
      } catch (err) {
        // Handle unexpected errors
        console.error('Error verifying authentication:', err);
        
        // Clear auth state for safety
        localStorage.removeItem('token');
        sessionStorage.removeItem('token');
        localStorage.removeItem('user');
        setUser(null);
        setIsAuthenticated(false);
      } finally {
        setLoading(false);
      }
    };
    
    verifyUser();
  }, []);

  return (
    <AuthContext.Provider 
      value={{ 
        isAuthenticated, 
        user, 
        login, 
        signup,
        googleLogin,
        logout,
        loading,
        error 
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};