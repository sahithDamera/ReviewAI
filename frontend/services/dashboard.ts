import { api } from "./api";

export type DashboardOverview = {
  summary: {
    review_link_opens: number; sessions: number; generations_completed: number;
    reviews_selected: number; successful_copies: number; google_handoff_clicks: number;
    average_rating: number | null;
  };
  activity: { id: string; event_type: string; occurred_at: string; rating: number | null }[];
};

export function loadOverview(businessId: string) {
  return api<DashboardOverview>(`/businesses/${businessId}/overview`);
}
