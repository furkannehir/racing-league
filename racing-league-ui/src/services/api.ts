import axios from 'axios';
import { League, LeagueDiscoveryPage, LeagueInvite, SentLeagueInvite, TeamsWithStats, TeamStanding, TeamsConfig } from '../types/league';
import api, { fetchAuthUser, passwordChanged } from './auth-client';
import { readSession, updateSessionUser } from './session';
import { AuthUser, AccountEmailResponse } from '../types/auth';
import { UserProfile } from '../types/user';
import { validateScreenshots, ImageExtractionResponse } from './race-image-import';

/**
 * Check if user is authenticated
 */
export const isAuthenticated = (): boolean => {
  return !!readSession();
};

/**
 * Fetch current user's leagues
 */
export const fetchMyLeagues = async (): Promise<League[]> => {
  try {
    const response = await api.get('/v1/leagues/my');
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
    const response = await api.get<League>(`/v1/leagues/${leagueId}`);
    return response.data;
  } catch (error) {
    console.error(`Error fetching league ${leagueId}:`, error);
    throw error;
  }
};

/**
 * Update a league's settings
 */
export const updateLeague = async (leagueId: string, data: Partial<League>): Promise<League> => {
  try {
    const response = await api.put<League>(`/v1/leagues/${leagueId}`, data);
    return response.data;
  } catch (error) {
    console.error(`Error updating league ${leagueId}:`, error);
    throw error;
  }
};

/**
 * Delete a league (owner/admin only)
 */
export const deleteLeague = async (leagueId: string): Promise<void> => {
  try {
    await api.delete(`/v1/leagues/${leagueId}`);
  } catch (error) {
    console.error(`Error deleting league ${leagueId}:`, error);
    throw error;
  }
};

/**
 * Join a league
 */
export const joinLeague = async (leagueId: string): Promise<void> => {
  try {
    await api.post(`/v1/leagues/${leagueId}/join`);
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
    await api.post(`/v1/leagues/${leagueId}/leave`);
  } catch (error) {
    console.error(`Error leaving league ${leagueId}:`, error);
    throw error;
  }
};

/**
 * Test authentication status
 */
export const checkAuth = (): Promise<AuthUser> => fetchAuthUser();

export const fetchMyInvites = async (): Promise<LeagueInvite[]> => {
  try {
    const response = await api.get('/v1/invites/my');
    return response.data;
  } catch (error) {
    console.error('Error fetching invites:', error);
    throw error;
  }
};

/**
 * Accept a league invitation
 */
export const acceptLeagueInvite = async (inviteId: string, leagueUserName?: string): Promise<void> => {
  try {
    await api.post(`/v1/invites/${inviteId}/accept`, { league_user_name: leagueUserName });
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
    await api.post(`/v1/invites/${inviteId}/decline`);
  } catch (error) {
    console.error('Error declining invite:', error);
    throw error;
  }
};

/**
 * Create a new league
 */
export const createLeague = async (leagueData: {
  name: string;
  public: boolean;
  calendar: Array<{track: string, date: string}>;
  pointSystem: Record<string, number>;
  max_players: number;
  fastestLapPoint: number;
  creatorParticipates: boolean;
  invites: string[];
}): Promise<League> => {
  try {
    const response = await api.post<League>('/v1/leagues', leagueData);
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
  raceId: string,
  results: Record<string, { position: number; fastestLap?: boolean; points: number; dnf?: boolean }>
): Promise<League> => {
  try {
    const response = await api.post<League>(
      `/v1/leagues/${leagueId}/races/${encodeURIComponent(raceId)}/results`,
      results 
    );
    return response.data;
  } catch (error) {
    console.error('Error submitting race results:', error);
    throw error;
  }
};

/**
 * Fetch current user's profile data
 */
export const fetchUserProfile = async (): Promise<UserProfile> => {
  try {
    const response = await api.get<UserProfile>('/v1/users/profile');
    return response.data;
  } catch (error) {
    console.error('Error fetching user profile:', error);
    throw error;
  }
};

/**
 * Update user profile information
 */
export const updateUserProfile = async (userData: {
  name?: string;
  bio?: string;
}): Promise<UserProfile> => {
  const snapshot = readSession();
  try {
    const response = await api.put<UserProfile>('/v1/users/update', userData);
    const current = readSession();
    if (snapshot && current?.id === snapshot.id && current.user.mongoId === response.data._id) {
      updateSessionUser({ ...current.user, name: response.data.name, email: response.data.email }, snapshot.id);
    }
    return response.data;
  } catch (error) {
    console.error('Error updating user profile:', error);
    throw error;
  }
};

/**
 * Update user password
 */
export const updateUserPassword = async (passwordData: {
  currentPassword: string;
  newPassword: string;
  confirmPassword: string;
}) => {
  const sessionId = readSession()?.id;
  try {
    const response = await api.put('/v1/users/update/password', passwordData);
    if (sessionId && response.data.code === 'password_updated') passwordChanged(sessionId);
    return response.data;
  } catch (error) {
    if (sessionId && error instanceof Error && 'response' in error) {
      const failure = error as Error & { response?: { data?: { code?: string } } };
      if (failure.response?.data?.code === 'password_changed_revocation_failed') {
        passwordChanged(sessionId, true);
      }
    }
    console.error('Error updating password:', error);
    throw error;
  }
};

/**
 * Fetch public leagues
 */
export const fetchPublicLeagues = async (page = 1, pageSize = 9, query = ''): Promise<LeagueDiscoveryPage> => {
  try {
    const response = await api.get<LeagueDiscoveryPage>('/v1/leagues/discovery', {
      params: { page, page_size: pageSize, q: query.trim() },
    });
    return response.data;
  } catch (error) {
    console.error('Error fetching public leagues:', error);
    throw error;
  }
};

/**
 * Invite players to join a league
 */
export const invitePlayersToLeague = async (league_id: string, emails: string[]): Promise<SentLeagueInvite[]> => {
  try {
    const response = await api.post<SentLeagueInvite[]>(`/v1/invites`, { league_id, emails });
    return response.data;
  } catch (error) {
    console.error('Error inviting players to league:', error);
    throw error;
  }
};

export const fetchSentLeagueInvites = async (leagueId: string): Promise<SentLeagueInvite[]> => {
  const response = await api.get<SentLeagueInvite[]>('/v1/invites/sent', { params: { league_id: leagueId } });
  return response.data;
};

export const retryInvitationEmail = async (inviteId: string): Promise<void> => {
  await api.post(`/v1/invites/${encodeURIComponent(inviteId)}/retry-email`);
};

/**
 * Process race screenshot with AI to extract race results using existing API
 */
export const processRaceScreenshot = async (
  image: File, 
  leagueId: string, 
  raceId: string
): Promise<ImageExtractionResponse> => processMultipleRaceScreenshots([image], leagueId, raceId);

/**
 * Process multiple race screenshots with AI to extract race results (max 2 images)
 */
export const processMultipleRaceScreenshots = async (
  images: File[], 
  leagueId: string, 
  raceId: string
): Promise<ImageExtractionResponse> => {
  const validation = validateScreenshots(images);
  if (validation) throw new Error(validation);
  const formData = new FormData();
  images.forEach(image => formData.append('images', image));
  const response = await api.post<ImageExtractionResponse>(
    `/v1/leagues/${encodeURIComponent(leagueId)}/races/${encodeURIComponent(raceId)}/extract-results`, formData,
    { headers: { 'Content-Type': undefined }, timeout: 60000 },
  );
  return response.data;
};

export const reset_password = async (email: string): Promise<AccountEmailResponse> => {
  try {
    const response = await api.post<AccountEmailResponse>('/v1/auth/reset-password', { email });
    return response.data;
  } catch (error) {
    console.error('Error requesting password reset:', error);
    throw error;
  }
};

export const verification_email = async (email: string): Promise<AccountEmailResponse> => {
  try {
    const response = await api.post<AccountEmailResponse>('/v1/auth/verification-email', { email });
    return response.data;
  } catch (error) {
    console.error('Error requesting email verification:', error);
    throw error;
  }
};

/**
 * Get teams with calculated statistics for a league
 */
export const fetchLeagueTeams = async (leagueId: string): Promise<TeamsWithStats> => {
  try {
    const response = await api.get<TeamsWithStats>(`/v1/leagues/${leagueId}/teams`);
    return response.data;
  } catch (error) {
    console.error(`Error fetching teams for league ${leagueId}:`, error);
    throw error;
  }
};

/**
 * Get team standings (sorted by points) for a league
 */
export const fetchTeamStandings = async (leagueId: string): Promise<TeamStanding[]> => {
  try {
    const response = await api.get<TeamStanding[]>(`/v1/leagues/${leagueId}/teams/standings`);
    return response.data;
  } catch (error) {
    console.error(`Error fetching team standings for league ${leagueId}:`, error);
    throw error;
  }
};

/**
 * Create or update teams for a league
 */
export const setLeagueTeams = async (leagueId: string, teamsConfig: TeamsConfig): Promise<TeamsWithStats> => {
  try {
    const response = await api.post<TeamsWithStats>(`/v1/leagues/${leagueId}/teams`, teamsConfig);
    return response.data;
  } catch (error) {
    console.error(`Error setting teams for league ${leagueId}:`, error);
    throw error;
  }
};

/**
 * Remove a team from a league
 */
export const removeLeagueTeam = async (leagueId: string, teamName: string): Promise<void> => {
  try {
    await api.delete(`/v1/leagues/${leagueId}/teams/${encodeURIComponent(teamName)}`);
  } catch (error) {
    console.error(`Error removing team ${teamName} from league ${leagueId}:`, error);
    throw error;
  }
};
/**
 * Get point system presets
 */
export const getPointSystemPresets = async (): Promise<Array<{
  _id: string;
  name: string;
  description: string;
  points: Record<string, number>;
  fastest_lap_point: number;
  active: boolean;
}>> => {
  try {
    const response = await api.get('/v1/point-systems');
    return response.data;
  } catch (error) {
    console.error('Error fetching point system presets:', error);
    throw error;
  }
};

export default api;
