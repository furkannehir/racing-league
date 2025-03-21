import configJson from './config.json';

/**
 * Configuration structure for the Racing League UI
 */
export interface RacingLeagueConfig {
    api: {
        baseUrl: string;
    }
}

/**
 * Get configuration from JSON file and optionally override with environment variables
 * @returns Configuration object
 */
const getConfig = (): RacingLeagueConfig => {
    // Use configuration from the imported JSON file
    const defaultConfig: RacingLeagueConfig = {
        api: {
            baseUrl: configJson.api?.baseUrl || 'http://localhost:5000'
        }
    };
    if (import.meta.env.VITE_API_URL) {
        defaultConfig.api.baseUrl = import.meta.env.VITE_API_URL;
    }
    
    return defaultConfig;
};

const config = getConfig();

export default config;