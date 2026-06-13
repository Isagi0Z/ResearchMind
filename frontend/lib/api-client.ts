export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

// In a real app, this would use fetch to call the backend API.
// Since we have no backend endpoints yet, we'll expose a mock interface 
// that can be swapped out later.

export const apiClient = {
  // Add generic fetch methods if needed later
};
