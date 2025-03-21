import axios, { AxiosResponse, AxiosError } from 'axios';
import { League, LeagueInvite } from '../types/league';

// Create an axios instance with appropriate configuration
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
  },
  maxRedirects: 0, // Don't follow redirects automatically
});

// Token management helper functions
const getAuthToken = (): string | null => {
  return localStorage.getItem('token') || sessionStorage.getItem('token') || null;
};

const setAuthToken = (token: string, remember: boolean = false): void => {
  if (remember) {
    localStorage.setItem('token', token);
  } else {
    sessionStorage.setItem('token', token);
  }
};

const clearAuthToken = (): void => {
  localStorage.removeItem('token');
  sessionStorage.removeItem('token');
};

// Add request interceptor for authentication
api.interceptors.request.use(
  config => {
    // Add token to every request if available
    const token = getAuthToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    } else {
      console.error('Request without auth token:', config.url);
    }
    
    return config;
  },
  error => {
    console.error('Request interceptor error:', error);
    return Promise.reject(error);
  }
);

// Add response interceptor to handle common issues
api.interceptors.response.use(
  (response: AxiosResponse) => {
    
    // Check if response includes a new token
    const newToken = response.headers['x-auth-token'];
    if (newToken) {
      setAuthToken(newToken);
    }
    
    return response;
  },
  async (error: AxiosError) => {
    if (!error.response) {
      console.error('Network error:', error.message);
      return Promise.reject(new Error('Network error. Please check your connection.'));
    }
    
    const { status, config } = error.response;
    
    // Handle authentication errors
    if (status === 401 || status === 403) {
      console.error(`Authentication error (${status})`);
      clearAuthToken();
      
      // Redirect to login if not already there
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
      
      return Promise.reject(new Error('Authentication failed. Please log in again.'));
    }
    
    // Handle redirects
    if (status === 302) {
      console.error('Received redirect. Current auth token may be invalid.');
      
      // Only redirect to login from non-login pages
      if (window.location.pathname !== '/login') {
        clearAuthToken();
        window.location.href = '/login';
      }
    }
    
    // Handle other common errors
    switch (status) {
      case 404:
        console.error(`Resource not found: ${config.url}`);
        break;
      case 500:
        console.error('Server error');
        break;
      default:
        console.error(`Error with status ${status}:`, error.response.data);
    }
    
    return Promise.reject(error);
  }
);

/**
 * Authenticate user and get token
 */
export const login = async (username: string, password: string, remember: boolean = false): Promise<boolean> => {
  try {
    const response = await api.post('/auth/login', { username, password });
    const token = response.data.token || response.headers['x-auth-token'];
    
    if (token) {
      setAuthToken(token, remember);
      return true;
    } else {
      console.error('Login successful but no token received');
      return false;
    }
  } catch (error) {
    console.error('Login error:', error);
    throw error;
  }
};

/**
 * Log user out
 */
export const logout = async (): Promise<void> => {
  try {
    // Call logout endpoint if your API has one
    await api.post('/auth/logout');
  } catch (error) {
    console.error('Logout API error:', error);
    // Continue with client-side logout even if API call fails
  } finally {
    clearAuthToken();
    window.location.href = '/login';
  }
};

/**
 * Check if user is authenticated
 */
export const isAuthenticated = (): boolean => {
  return !!getAuthToken();
};

/**
 * Fetch current user's leagues
 */
export const fetchMyLeagues = async (): Promise<League[]> => {
  try {
    const response = await api.get('/leagues/my');
    return response.data;
  } catch (error) {
    if (axios.isAxiosError(error)) {
      console.error('Error fetching leagues:', {
        message: error.message,
        status: error.response?.status,
        data: error.response?.data
      });
    } else {
      console.error('Unknown error fetching leagues:', error);
    }
    throw error;
  }
};

/**
 * Fetch a single league by ID
 */
export const fetchLeagueById = async (leagueId: string): Promise<League> => {
  try {
    const response = await api.get<League>(`/leagues/${leagueId}`);
    return response.data;
  } catch (error) {
    console.error(`Error fetching league ${leagueId}:`, error);
    throw error;
  }
};

/**
 * Join a league
 */
export const joinLeague = async (leagueId: string): Promise<void> => {
  try {
    await api.post(`/leagues/${leagueId}/join`);
  } catch (error) {
    console.error(`Error joining league ${leagueId}:`, error);
    throw error;
  }
};

/**
 * Leave a league
 */
export const leaveLeague = async (leagueId: string): Promise<void> => {
  try {
    await api.post(`/leagues/${leagueId}/leave`);
  } catch (error) {
    console.error(`Error leaving league ${leagueId}:`, error);
    throw error;
  }
};

/**
 * Test authentication status
 */
export const checkAuth = async (): Promise<boolean> => {
  try {
    await api.get('/verify');
    return true;
  } catch (error) {
    console.error('Auth check failed:', error);
    return false;
  }
};

export const fetchMyInvites = async (): Promise<LeagueInvite[]> => {
  try {
    const response = await api.get('/invites/my');
    return response.data;
  } catch (error) {
    console.error('Error fetching invites:', error);
    throw error;
  }
};

/**
 * Accept a league invitation
 */
export const acceptLeagueInvite = async (inviteId: string): Promise<void> => {
  try {
    await api.post(`/invites/${inviteId}/accept`);
  } catch (error) {
    console.error('Error accepting invite:', error);
    throw error;
  }
};

/**
 * Decline a league invitation
 */
export const declineLeagueInvite = async (inviteId: string): Promise<void> => {
  try {
    await api.post(`/invites/${inviteId}/decline`);
  } catch (error) {
    console.error('Error declining invite:', error);
    throw error;
  }
};

/**
 * Create a new league
 */
/**
 * Create a new league
 */
export const createLeague = async (leagueData: {
  name: string;
  owner: string;
  public: boolean;
  calendar: Array<{track: string, date: string}>;
  pointSystem: Record<string, number>;
  max_players: number;
  fastestLapPoint: number;
  participants: string[]; // Initial participants (likely just the creator)
  invites: string[]; // People to invite
  participantsCount: number;
  next_race: {track: string, date: string} | null;
  status: string;
  admins: string[];
}): Promise<League> => {
  try {
    const response = await api.post<League>('/leagues', leagueData);
    return response.data;
  } catch (error) {
    console.error('Error creating league:', error);
    throw error;
  }
};

/**
 * Submit race results for a league
 */
export const submitRaceResult = async (
  leagueId: string, 
  trackName: string, 
  results: Record<string, { position: number; fastestLap?: boolean; points: number }>
): Promise<League> => {
  try {
    const response = await api.post<League>(
      `/leagues/${leagueId}/races/${encodeURIComponent(trackName)}/results`, 
      results 
    );
    return response.data;
  } catch (error) {
    console.error('Error submitting race results:', error);
    throw error;
  }
};

export default api;