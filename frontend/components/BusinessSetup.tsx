"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError, Business, Category } from "@/services/api";
import { OwnerHeader } from "./OwnerHeader";
import { BusinessForm } from "./BusinessForm";

async function fetchSetup() {
  await api("/auth/me");
  const categories = await api<Category[]>("/business-categories");
  let business: Business | undefined;
  try { business = await api<Business>("/businesses/me"); }
  catch (err) { if (!(err instanceof ApiError && err.status === 404)) throw err; }
  return { categories, business };
}

export function BusinessSetup({ editing = false }: { editing?: boolean }) {
  const router = useRouter();
  const [data, setData] = useState<{ categories: Category[]; business?: Business }>();
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    fetchSetup().then(({ categories, business }) => {
      if (!active) return;
      if (editing && !business) { router.replace("/onboarding"); return; }
      if (!editing && business) { router.replace("/dashboard"); return; }
      setData({ categories, business }); setError("");
    }).catch(err => {
      if (!active) return;
      if (err instanceof ApiError && err.status === 401) router.replace("/login");
      else setError("Could not load your business setup. Please try again.");
    });
    return () => { active = false; };
  }, [editing, router, attempt]);
  function load() { setAttempt(value => value + 1); }
  return <><OwnerHeader /><main className="mx-auto max-w-2xl px-6 py-12"><p className="eyebrow">{editing ? "Business settings" : "Your business, your space"}</p><h1 className="mb-4 mt-3 text-4xl font-semibold">{editing ? "Keep your details current." : "Let’s set the table."}</h1><p className="muted mb-8">{editing ? "Manage the details customers will see and where your Google link leads." : "Add your business details and the Google page you’d like customers to visit."}</p>{error ? <div role="alert" className="error">{error}<button onClick={load} className="ml-3 underline">Try again</button></div> : data ? <BusinessForm {...data} /> : <p role="status" className="muted">Loading your business details…</p>}</main></>;
}
