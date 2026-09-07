"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { OwnerHeader } from "@/components/OwnerHeader";
import { api, ApiError, Business } from "@/services/api";
import { DashboardOverview, loadOverview } from "@/services/dashboard";

const labels: Record<string, string> = {
  QR_OPENED: "Review link opened", RATING_SELECTED: "Rating selected", ATTRIBUTES_SELECTED: "Topics selected",
  AI_GENERATION_COMPLETED: "Suggestions created", REVIEW_SELECTED: "Review selected", COPY_SUCCEEDED: "Review copied",
  GOOGLE_OPENED: "Google handoff clicked", SESSION_COMPLETED: "Handoff attempted",
};

export default function ActivityPage() {
  const router = useRouter();
  const [business, setBusiness] = useState<Business>();
  const [data, setData] = useState<DashboardOverview>();
  const [error, setError] = useState("");
  useEffect(() => { api<Business>("/businesses/me").then(value => { setBusiness(value); return loadOverview(value.id); }).then(setData).catch(err => {
    if (err instanceof ApiError && err.status === 401) router.replace("/login"); else setError("Could not load activity.");
  }); }, [router]);
  const summary = data?.summary;
  const cards = summary ? [["Review-link opens", summary.review_link_opens], ["Sessions", summary.sessions], ["Suggestions created", summary.generations_completed], ["Reviews selected", summary.reviews_selected], ["Successful copies", summary.successful_copies], ["Google handoff clicks", summary.google_handoff_clicks], ["Average rating", summary.average_rating == null ? "—" : summary.average_rating.toFixed(1)]] : [];
  return <><OwnerHeader /><main className="mx-auto max-w-5xl px-6 py-12"><p className="eyebrow">Activity</p><h1 className="mt-3 text-4xl font-semibold">See how customers move through your link.</h1><p className="muted mt-4 max-w-2xl">Counts are directional activity signals. Google handoff clicks do not confirm that a review was submitted.</p>{error ? <p className="error mt-8" role="alert">{error}</p> : !data || !business ? <p className="muted mt-8" role="status">Loading activity…</p> : <><div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{cards.map(([label, value]) => <section className="panel" key={String(label)}><p className="muted text-sm">{label}</p><p className="mt-3 text-3xl font-semibold">{value}</p></section>)}</div><section className="panel mt-8"><h2 className="text-2xl font-semibold">Recent activity</h2>{data.activity.length === 0 ? <p className="muted mt-6">Activity will appear as customers use your review link.</p> : <ul className="mt-6 divide-y divide-[#e0e5db]">{data.activity.map(item => <li className="flex items-center justify-between gap-4 py-4" key={item.id}><span>{labels[item.event_type] || "Review activity"}</span><time className="muted text-sm" dateTime={item.occurred_at}>{new Date(item.occurred_at).toLocaleString()}</time></li>)}</ul>}</section></>}</main></>;
}
