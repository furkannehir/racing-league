import type { LeagueParticipant } from '../types/league';

export const MAX_SCREENSHOTS = 2;
export const MAX_SCREENSHOT_BYTES = 6 * 1024 * 1024;

export interface ExtractedRaceResult {
  driver: string | null;
  position: number | null;
}

export interface ImageExtractionResponse {
  results: ExtractedRaceResult[];
}

export interface ImageDriverResult {
  position: number;
  fastestLap: boolean;
  dnf: boolean;
  driverId: string;
  name: string;
}

export function validateScreenshots(files: Pick<File, 'size' | 'type'>[]): string | null {
  if (files.length < 1 || files.length > MAX_SCREENSHOTS) return 'Upload one or two screenshots.';
  if (files.some(file => !['image/jpeg', 'image/jpg', 'image/png', '', 'application/octet-stream'].includes(file.type))) {
    return 'Only JPEG and PNG images are supported.';
  }
  if (files.some(file => file.size === 0)) return 'The image is empty.';
  if (files.some(file => file.size > MAX_SCREENSHOT_BYTES)) return 'Each image must be 6 MiB or smaller.';
  return null;
}

const normalize = (value: string) => value.normalize('NFKC').trim().replace(/\s+/g, ' ').toLowerCase();

/** Apply only unique exact aliases. Partial imports retain the other drivers' relative order. */
export function importImageResults(
  response: unknown, drivers: ImageDriverResult[], participants: LeagueParticipant[],
): { drivers: ImageDriverResult[]; matched: number; warnings: string[] } {
  if (!response || typeof response !== 'object' || !('results' in response)
    || !Array.isArray(response.results) || response.results.length > 200) {
    throw new Error('AI returned invalid results. Please enter results manually or try again.');
  }
  const aliases = new Map<string, Set<string>>();
  for (const driver of drivers) {
    const participant = participants.find(item => item.email === driver.driverId);
    for (const alias of [driver.name, driver.driverId, participant?.league_user_name, participant?.name]) {
      if (!alias?.trim()) continue;
      const key = normalize(alias);
      const owners = aliases.get(key) ?? new Set<string>();
      owners.add(driver.driverId);
      aliases.set(key, owners);
    }
  }
  const candidates = new Map<string, Set<number>>();
  let ignored = 0;
  for (const row of response.results) {
    if (!row || typeof row !== 'object' || typeof row.driver !== 'string'
      || !row.driver.trim() || !Number.isInteger(row.position) || row.position < 1 || row.position > drivers.length) {
      ignored++;
      continue;
    }
    const owners = aliases.get(normalize(row.driver));
    if (!owners || owners.size !== 1) { ignored++; continue; }
    const id = [...owners][0];
    const positions = candidates.get(id) ?? new Set<number>();
    positions.add(row.position);
    candidates.set(id, positions);
  }
  // Mark every driver involved in a position conflict, including conflicting duplicate rows.
  const positionOwners = new Map<number, Set<string>>();
  for (const [id, positions] of candidates) {
    for (const position of positions) {
      const owners = positionOwners.get(position) ?? new Set<string>();
      owners.add(id);
      positionOwners.set(position, owners);
    }
  }
  const placements = new Map<string, number>();
  let conflicts = 0;
  for (const [id, positions] of candidates) {
    const position = [...positions][0];
    if (positions.size !== 1 || positionOwners.get(position)!.size !== 1) { conflicts++; continue; }
    placements.set(id, position);
  }
  if (placements.size === 0) {
    throw new Error('No unambiguous driver matches were found. Enter results manually or use a clearer screenshot.');
  }
  const ordered: ImageDriverResult[] = new Array(drivers.length);
  const remaining = drivers.filter(driver => !placements.has(driver.driverId));
  for (const driver of drivers) {
    const position = placements.get(driver.driverId);
    if (position !== undefined) ordered[position - 1] = { ...driver, position };
  }
  let next = 0;
  for (let index = 0; index < ordered.length; index++) {
    if (!ordered[index]) ordered[index] = { ...remaining[next++], position: index + 1 };
  }
  const warnings: string[] = [];
  if (ignored) warnings.push(`${ignored} unreadable, unknown, or ambiguous row(s) were ignored.`);
  if (conflicts) warnings.push(`${conflicts} driver(s) had conflicting positions and were left for manual review.`);
  if (remaining.length) warnings.push(`Check positions for ${remaining.map(driver => driver.name).join(', ')}; they were not identified reliably.`);
  return { drivers: ordered, matched: placements.size, warnings };
}
