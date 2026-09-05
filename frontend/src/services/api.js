/**
 * SoilSense AI — API service layer
 * All backend communication goes through this module.
 * Handles errors gracefully so components never see raw exceptions.
 */

// Empty string = use Vite's built-in proxy (vite.config.js routes /api/* → http://localhost:8000)
// Set VITE_API_URL in .env only if deploying to a different host
const BASE_URL = import.meta.env.VITE_API_URL || '';

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function request(method, path, body = null) {
  const options = {
    method,
    headers: { 'Content-Type': 'application/json' },
  };
  if (body) options.body = JSON.stringify(body);

  const response = await fetch(`${BASE_URL}${path}`, options);

  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch {}
    throw new ApiError(detail, response.status);
  }

  return response.json();
}

export const api = {
  health: () => request('GET', '/api/health'),

  analyzeSoil: (description, location, targetCrop, conversationHistory = []) =>
    request('POST', '/api/analyze-soil', {
      description,
      location,
      target_crop: targetCrop,
      conversation_history: conversationHistory,
    }),

  checkFollowUp: (description, location, targetCrop) =>
    request('POST', '/api/soil/follow-up', {
      description,
      location,
      target_crop: targetCrop,
    }),

  chat: (messages, location, targetCrop) =>
    request('POST', '/api/chat', {
      messages,
      location,
      target_crop: targetCrop,
    }),
};

export { ApiError };
