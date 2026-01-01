export interface RaceDetails {
    _id: string;
    date: string;
    track: string;
    status?: "Upcoming" | "Completed" | "Cancelled";
  }
  
  export interface DriverResult {
    position: number;
    points: number;
    fastestLap?: boolean;
  }
  
  export interface RaceResults {
    [driverId: string]: DriverResult;
  }
  
  export interface DriverStandings {
    points: number;
    wins: number;
    podiums: number;
    fastestLaps: number;
    dnfs: number;
    name?: string;
  }
  
  export interface League {
    _id: string;
    admins: string[];
    calendar: RaceDetails[] | string[];
    created_at: Date;
    deleted_at: Date | null;
    fastestLapPoint: number;
    max_players: number;
    name: string;
    owner: string;
    participants: string[];
    pointSystem: {};
    public: boolean;
    standings: {
      overall: Record<string, DriverStandings>;
      races: Record<string, RaceResults>;
    };
    updated_at: Date | null;
    participantsCount: number;
    position?: number;
    next_race: RaceDetails;
    status: string;
  }
  

export interface LeagueInvite {
    _id: string;
    league: {
        _id: string;
        name: string;
        participantsCount: number;
        status: string;
    };
    inviter?: {
      _id: string;
      name: string;
      email?: string;
    };
    createdAt: string;
    status: 'pending' | 'accepted' | 'declined';
  }

export interface TeamMemberDetails {
  email: string;
  name: string;
  points: number;
  wins: number;
  podiums: number;
  dnfs: number;
  fastestLaps: number;
}

export interface TeamStats {
  members: string[];
  total_points: number;
  total_wins: number;
  total_podiums: number;
  total_dnfs: number;
  total_fastest_laps: number;
  member_details: TeamMemberDetails[];
}

export interface TeamsWithStats {
  [teamName: string]: TeamStats;
}

export interface TeamStanding {
  name: string;
  position: number;
  members: string[];
  total_points: number;
  total_wins: number;
  total_podiums: number;
  total_dnfs: number;
  total_fastest_laps: number;
  member_details: TeamMemberDetails[];
}

export interface TeamsConfig {
  [teamName: string]: string[];
}