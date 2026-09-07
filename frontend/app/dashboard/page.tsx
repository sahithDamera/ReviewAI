"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, ApiError, Business } from "@/services/api";
import { OwnerHeader } from "@/components/OwnerHeader";

export default function Dashboard() {
  const router = useRouter();
  const [business, setBusiness] = useState<Business>();
  const [error, setError] = useState("");
  const [copyMessage, setCopyMessage] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    api<Business>("/businesses/me").then(value => {
      if (active) { setBusiness(value); setError(""); }
    }).catch(err => {
      if (!active) return;
      if (err instanceof ApiError && err.status === 401) router.replace("/login");
      else if (err instanceof ApiError && err.status === 404) router.replace("/onboarding");
      else setError("Could not load your business. Please try again.");
    });
    return () => { active = false; };
  }, [router, attempt]);
  function load() { setAttempt(value => value + 1); }
  async function copy() {
    if (!business) return;
    try { await navigator.clipboard.writeText(business.review_url); setCopyMessage("Review URL copied."); }
    catch { setCopyMessage("Could not copy automatically. Select the URL below and copy it manually."); }
  }
  return <><OwnerHeader /><main className="mx-auto max-w-5xl px-6 py-12">{error ? <div role="alert" className="error">{error}<button className="ml-3 underline" onClick={load}>Try again</button></div> : !business ? <p role="status">Loading your business…</p> : <>
    <div className="mb-10 flex flex-wrap items-end justify-between gap-5"><div><p className="eyebrow">Your business</p><h1 className="mt-3 text-4xl font-semibold">{business.name}</h1><p className="muted mt-3">{business.category_name} <span aria-hidden>·</span> <span className="capitalize">{business.status}</span></p></div><Link href="/dashboard/settings" className="button secondary">Edit business</Link></div>
    <div className="grid gap-6 md:grid-cols-[1.3fr_1fr]"><section className="panel"><span aria-hidden className="text-3xl text-[#568264]">↗</span><h2 className="mb-3 mt-5 text-2xl font-semibold">A link of your own.</h2><p className="muted text-sm leading-relaxed">Your unique review URL is reserved. The customer review page and QR downloads will be available in the next stages.</p><label className="mt-6">Business review URL<input value={business.review_url} readOnly onFocus={e => e.target.select()} /></label><button className="button mt-4" onClick={copy}>Copy URL</button><p role="status" className="muted mt-3 text-sm">{copyMessage}</p></section>
    <section className="panel"><p className="eyebrow">Business profile</p><h2 className="mt-5 text-2xl font-semibold">The details are in.</h2><dl className="mt-6 space-y-5 text-sm"><div><dt className="muted">Brand tone</dt><dd className="mt-1 capitalize">{business.brand_tone}</dd></div><div><dt className="muted">Google destination</dt><dd className="mt-1">{business.destination_confirmed ? "Confirmed by you" : "Awaiting your confirmation"}</dd></div>{business.description && <div><dt className="muted">About your business</dt><dd className="mt-1 leading-relaxed">{business.description}</dd></div>}</dl><a href={business.google_review_url} className="mt-6 inline-block min-h-11 py-2 font-semibold underline" target="_blank" rel="noopener noreferrer">Open Google destination ↗</a></section></div>
  </>}</main></>;
}
