import { resolveApiUrl } from './api-url';

/**
 * Configuration structure for the Racing League UI
 */
export interface RacingLeagueConfig {
    api: {
        baseUrl: string;
    }
}

const config: RacingLeagueConfig = {
    api: {
        baseUrl: resolveApiUrl(import.meta.env.VITE_API_URL, import.meta.env.DEV),
    },
};
export default config;
