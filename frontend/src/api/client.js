/**
 * API client communicating with FastAPI backend with Telegram authentication header.
 */

const getInitData = () => {
  if (typeof window !== "undefined" && window.Telegram?.WebApp?.initData) {
    return window.Telegram.WebApp.initData;
  }
  return "DEV_MOCK_USER";
};

const request = async (endpoint, options = {}) => {
  const headers = {
    "X-Telegram-Init-Data": getInitData(),
    ...options.headers,
  };

  // If payload is not FormData, default to application/json
  if (!(options.body instanceof FormData) && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(endpoint, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorDetail = `خطای سرور (${response.status})`;
    try {
      const errJson = await response.json();
      errorDetail = errJson.detail || errJson.message || errorDetail;
    } catch (e) {
      // Non-JSON response
    }
    throw new Error(errorDetail);
  }

  return response.json();
};

export const api = {
  getBootstrap: () => request("/api/v1/bootstrap"),

  createTrade: (tradeData) =>
    request("/api/v1/trades", {
      method: "POST",
      body: JSON.stringify(tradeData),
    }),

  updateTrade: (tradeId, patchData) =>
    request(`/api/v1/trades/${tradeId}`, {
      method: "PUT",
      body: JSON.stringify(patchData),
    }),

  publishTrade: (tradeId) =>
    request(`/api/v1/trades/${tradeId}/publish`, {
      method: "POST",
    }),

  getAdminTemplate: () => request("/api/v1/admin/template"),

  updateAdminTemplate: (template, channelId) =>
    request("/api/v1/admin/template", {
      method: "PUT",
      body: JSON.stringify({ template, channelId }),
    }),

  deleteTrade: (tradeId) =>
    request(`/api/v1/trades/${tradeId}`, {
      method: "DELETE",
    }),

  uploadTradeChart: (tradeId, file) => {
    const formData = new FormData();
    formData.append("file", file);
    return request(`/api/v1/trades/${tradeId}/chart-upload`, {
      method: "POST",
      body: formData,
      headers: {}, // Let browser set multipart boundary
    });
  },

  createStrategy: (name) =>
    request("/api/v1/strategies", {
      method: "POST",
      body: JSON.stringify({ name }),
    }),

  deleteStrategy: (name) =>
    request(`/api/v1/strategies/${encodeURIComponent(name)}`, {
      method: "DELETE",
    }),
};
