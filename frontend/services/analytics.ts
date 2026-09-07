import { api } from "./api";

export type AnalyticsReport = {
  start: string; end: string;
  summary: { sessions: number; rated_sessions: number; generated_sessions: number; selected_sessions: number; manual_sessions: number; copied_sessions: number; google_handoff_sessions: number; rating_average: number | null };
  daily: { day: string; sessions: number; rated_sessions: number; generated_sessions: number; selected_sessions: number; manual_sessions: number; copied_sessions: number; google_handoff_sessions: number; rating_sum: number; rating_count: number }[];
};
export function loadAnalytics(id: string) { return api<AnalyticsReport>(`/businesses/${id}/analytics`); }
