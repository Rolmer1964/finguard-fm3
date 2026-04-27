import axios from "axios";

const baseURL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export const api = axios.create({ baseURL, timeout: 120_000 });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("finguard_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem("finguard_token");
      if (!window.location.pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
    }
    return Promise.reject(err);
  }
);

export interface Analysis {
  blocked: boolean;
  block_reason?: string | null;
  category?: string | null;
  product?: string | null;
  sentiment?: string | null;
  urgency?: string | null;
  summary?: string | null;
  risk_level?: string | null;
  risk_justification?: string | null;
}

export interface Complaint {
  id: string;
  external_id?: string | null;
  raw_text: string;
  channel?: string | null;
  product_hint?: string | null;
  status: string;
  created_at: string;
  analysis?: Analysis | null;
}

export interface DashboardData {
  total: number;
  blocked: number;
  by_category: Record<string, number>;
  by_product: Record<string, number>;
  by_urgency: Record<string, number>;
  by_sentiment: Record<string, number>;
  by_risk: Record<string, number>;
  critical: Array<{
    id: string;
    category?: string;
    product?: string;
    urgency?: string;
    risk_level?: string;
    summary?: string;
    risk_justification?: string;
  }>;
  recommendations: string[];
}
