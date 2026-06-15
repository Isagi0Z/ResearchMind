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

export const apiClient = {
  async get<T>(url: string): Promise<T> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), API_TIMEOUT_MS);

    let res: Response;
    try {
      res = await fetch(`${getBaseUrl()}${url}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
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

    if (!res.ok) {
      let detail: unknown = res.statusText;
      try {
        const errData = await res.json();
        detail = errData.detail ?? detail;
      } catch {
        // Non-JSON error body — keep statusText
      }
      throw new ApiError(res.status, sanitizeErrorMessage(res.status, detail, res.statusText));
    }

    return res.json() as Promise<T>;
  },

  async post<T>(url: string, data: unknown): Promise<T> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), API_TIMEOUT_MS);

    let res: Response;
    try {
      res = await fetch(`${getBaseUrl()}${url}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(data),
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

    if (!res.ok) {
      let detail: unknown = res.statusText;
      try {
        const errData = await res.json();
        detail = errData.detail ?? detail;
      } catch {
        // Non-JSON error body — keep statusText
      }
      throw new ApiError(res.status, sanitizeErrorMessage(res.status, detail, res.statusText));
    }

    return res.json() as Promise<T>;
  }
};
