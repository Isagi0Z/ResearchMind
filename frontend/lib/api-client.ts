const API_TIMEOUT_MS = 30_000;

function getBaseUrl(): string {
  const url = process.env.NEXT_PUBLIC_API_URL;
  if (!url) {
    throw new ApiError(
      0,
      'NEXT_PUBLIC_API_URL is not configured. Set it in .env.local or your environment.'
    );
  }
  return url.replace(/\/+$/, '');
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

const ERROR_MESSAGES: Record<number, string> = {
  401: 'Your session has expired. Please log in again.',
  403: 'You do not have permission to perform this action.',
  404: 'The requested resource was not found.',
  429: 'Too many requests. Please wait a moment and try again.',
};

function getErrorMessage(status: number, detail: unknown, fallback: string): string {
  if (status >= 500) {
    return 'An internal server error occurred. Please try again later.';
  }
  if (typeof detail === 'string' && detail.length > 0) {
    return detail;
  }
  return ERROR_MESSAGES[status] || fallback;
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
      credentials: 'include',
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

    if (!isRefreshing) {
      isRefreshing = true;
      try {
        const refreshRes = await fetch(`${getBaseUrl()}/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: refresh ? JSON.stringify({ refresh_token: refresh }) : '{}',
        });

        if (!refreshRes.ok) {
          throw new Error('Refresh failed');
        }

        const data = await refreshRes.json();
        if (data.access_token && data.refresh_token) {
          setTokens(data.access_token, data.refresh_token);
        }
        isRefreshing = false;
        onRefreshed(data.access_token);
      } catch {
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
      detail = errData.detail ?? errData.error?.message ?? detail;
    } catch {
      // Non-JSON error body — use statusText
    }
    throw new ApiError(res.status, getErrorMessage(res.status, detail, res.statusText));
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
      body: JSON.stringify(data),
    });
    return res.json() as Promise<T>;
  },

  async patch<T, B>(url: string, data: B): Promise<T> {
    const res = await handleFetchWithAuth(url, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    return res.json() as Promise<T>;
  },

  async postForm<T>(url: string, body: URLSearchParams): Promise<T> {
    const res = await handleFetchWithAuth(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: body.toString(),
      credentials: 'include',
    });
    return res.json() as Promise<T>;
  },

  setTokens,
  clearTokens,
  getTokens,
};
