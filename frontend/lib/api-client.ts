/** Default request timeout in milliseconds (30 seconds). */
const API_TIMEOUT_MS = 30_000;

/**
 * Resolve the API base URL from environment configuration.
 * Fails clearly at call-time if NEXT_PUBLIC_API_URL is not set.
 */
function getBaseUrl(): string {
  const url = process.env.NEXT_PUBLIC_API_URL;
  if (!url) {
    throw new ApiError(
      0,
      'NEXT_PUBLIC_API_URL is not configured. Set it in .env.local or your environment.'
    );
  }
  return url;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

/**
 * Sanitize error detail from the backend.
 * For 5xx responses, suppress raw detail to avoid leaking stack traces.
 * For 4xx responses, preserve the validation detail for developer feedback.
 */
function sanitizeErrorMessage(status: number, detail: unknown, fallback: string): string {
  if (status >= 500) {
    return 'An internal server error occurred. Please try again later.';
  }
  if (typeof detail === 'string' && detail.length > 0) {
    return detail;
  }
  return fallback;
}

function getTokens() {
  if (typeof window === 'undefined') return { access: null, refresh: null };
  return {
    access: localStorage.getItem('access_token'),
    refresh: localStorage.getItem('refresh_token'),
  };
}

function setTokens(access: string, refresh: string) {
  if (typeof window === 'undefined') return;
  localStorage.setItem('access_token', access);
  localStorage.setItem('refresh_token', refresh);
}

function clearTokens() {
  if (typeof window === 'undefined') return;
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
}

let isRefreshing = false;
let refreshSubscribers: ((token: string) => void)[] = [];

function subscribeTokenRefresh(cb: (token: string) => void) {
  refreshSubscribers.push(cb);
}

function onRefreshed(token: string) {
  refreshSubscribers.map(cb => cb(token));
  refreshSubscribers = [];
}

async function handleFetchWithAuth(
  url: string,
  options: RequestInit,
  isRetry = false
): Promise<Response> {
  const { access } = getTokens();
  const headers = new Headers(options.headers);
  if (access) {
    headers.set('Authorization', `Bearer ${access}`);
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), API_TIMEOUT_MS);
  
  let res: Response;
  try {
    res = await fetch(`${getBaseUrl()}${url}`, {
      ...options,
      headers,
      signal: controller.signal,
    });
  } catch (err: unknown) {
    clearTimeout(timeoutId);
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new ApiError(408, 'Request timed out');
    }
    throw new ApiError(0, 'Network error: unable to reach the server.');
  } finally {
    clearTimeout(timeoutId);
  }

  if (res.status === 401 && !isRetry && !url.includes('/auth/login') && !url.includes('/auth/refresh')) {
    const { refresh } = getTokens();
    if (!refresh) {
      clearTokens();
      throw new ApiError(401, 'Unauthorized');
    }

    if (!isRefreshing) {
      isRefreshing = true;
      try {
        const refreshRes = await fetch(`${getBaseUrl()}/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: refresh }),
        });
        
        if (!refreshRes.ok) {
          throw new Error('Refresh failed');
        }
        
        const data = await refreshRes.json();
        setTokens(data.access_token, data.refresh_token);
        isRefreshing = false;
        onRefreshed(data.access_token);
      } catch (err) {
        isRefreshing = false;
        clearTokens();
        if (typeof window !== 'undefined') window.location.href = '/login';
        throw new ApiError(401, 'Session expired. Please log in again.');
      }
    }

    return new Promise((resolve) => {
      subscribeTokenRefresh((newToken: string) => {
        headers.set('Authorization', `Bearer ${newToken}`);
        resolve(handleFetchWithAuth(url, { ...options, headers }, true));
      });
    });
  }

  if (!res.ok) {
    let detail: unknown = res.statusText;
    try {
      const errData = await res.json();
      detail = errData.detail ?? detail;
    } catch {
      // Non-JSON error body ?" keep statusText
    }
    throw new ApiError(res.status, sanitizeErrorMessage(res.status, detail, res.statusText));
  }

  return res;
}

export const apiClient = {
  async get<T>(url: string): Promise<T> {
    const res = await handleFetchWithAuth(url, { method: 'GET', headers: { 'Content-Type': 'application/json' } });
    return res.json() as Promise<T>;
  },

  async post<T>(url: string, data: unknown): Promise<T> {
    const res = await handleFetchWithAuth(url, { 
      method: 'POST', 
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    return res.json() as Promise<T>;
  },

  setTokens,
  clearTokens,
  getTokens
};
