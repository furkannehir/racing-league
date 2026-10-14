export const LOCAL_API_URL = 'http://localhost:5000/api';

const invalidUrlMessage =
  'VITE_API_URL must be an absolute HTTP(S) URL ending in /api, without credentials, a query, or a fragment.';

export function resolveApiUrl(value: string | undefined, allowLocalDefault: boolean): string {
  const configured = value?.trim();
  if (!configured) {
    if (allowLocalDefault) return LOCAL_API_URL;
    throw new Error('VITE_API_URL is required for builds. Set it to the intended backend URL, including /api.');
  }

  let url: URL;
  try {
    url = new URL(configured);
  } catch {
    throw new Error(invalidUrlMessage);
  }
  const pathname = url.pathname.replace(/\/+$/, '');
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password ||
      configured.includes('?') || configured.includes('#') || !pathname.endsWith('/api')) {
    throw new Error(invalidUrlMessage);
  }
  url.pathname = pathname;
  return url.toString();
}
