import type { DriverStandings, TeamsWithStats } from '../types/league';

const compareKey = (a: string, b: string) => a < b ? -1 : a > b ? 1 : 0;

export function sortedDrivers(standings: Record<string, DriverStandings>) {
  return Object.entries(standings).sort(([idA, a], [idB, b]) => {
    if (a.position != null && b.position != null) return a.position - b.position;
    return b.points - a.points || b.wins - a.wins || b.podiums - a.podiums || compareKey(idA, idB);
  });
}

export function sortedTeams(teams: TeamsWithStats) {
  return Object.entries(teams).sort(([nameA, a], [nameB, b]) => {
    if (a.position != null && b.position != null) return a.position - b.position;
    return b.total_points - a.total_points || b.total_wins - a.total_wins
      || b.total_podiums - a.total_podiums || compareKey(nameA, nameB);
  });
}
