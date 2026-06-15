export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

export const apiClient = {
  async post<T>(url: string, data: any): Promise<T> {
    const res = await fetch(`http://localhost:8000${url}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    });

    if (!res.ok) {
      let message = res.statusText;
      try {
        const errData = await res.json();
        message = errData.detail || message;
      } catch (e) {
        // ignore
      }
      throw new ApiError(res.status, message);
    }

    return res.json() as Promise<T>;
  }
};
