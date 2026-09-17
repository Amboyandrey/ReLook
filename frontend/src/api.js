const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, options);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      // response wasn't JSON -- fall back to statusText
    }
    throw new Error(detail);
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  listDocuments: (filters = {}) => {
    const params = new URLSearchParams();
    if (filters.status) params.set("status", filters.status);
    if (filters.needsHuman !== undefined) params.set("needs_human", filters.needsHuman);
    const qs = params.toString();
    return request(`/documents${qs ? `?${qs}` : ""}`);
  },

  getDocument: (id) => request(`/documents/${id}`),

  fileUrl: (id) => `${API_BASE}/documents/${id}/file`,

  uploadDocument: async (file) => {
    const formData = new FormData();
    formData.append("file", file);
    return request("/documents", { method: "POST", body: formData });
  },

  submitReview: (id, submission) =>
    request(`/documents/${id}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(submission),
    }),

  getTaxonomy: () => request("/taxonomy"),

  listTasks: (filters = {}) => {
    const params = new URLSearchParams();
    if (filters.status) params.set("status", filters.status);
    const qs = params.toString();
    return request(`/tasks${qs ? `?${qs}` : ""}`);
  },

  completeTask: (id) => request(`/tasks/${id}/complete`, { method: "POST" }),

  listNotifications: () => request("/notifications"),
};
