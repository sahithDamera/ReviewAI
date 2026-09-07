"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, Business, Category } from "@/services/api";

export function BusinessForm({ categories, business }: { categories: Category[]; business?: Business }) {
  const router = useRouter();
  const [url, setUrl] = useState(business?.google_review_url || "");
  const [confirmed, setConfirmed] = useState(business?.destination_confirmed || false);
  const [category, setCategory] = useState(business?.category_id || "");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  let testable = false;
  try {
    const destination = new URL(url);
    testable = destination.protocol === "https:" && !!destination.hostname
      && !destination.username && !destination.password && !/[\s\\\x00-\x1f\x7f]/.test(url);
  } catch { /* Keep the test link hidden until the URL is valid. */ }
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(""); setBusy(true);
    const fields = new FormData(event.currentTarget);
    if (!testable) { setError("Enter a complete link starting with https://."); setBusy(false); return; }
    try {
      await api(business ? `/businesses/${business.id}` : "/businesses", {
        method: business ? "PUT" : "POST",
        body: JSON.stringify({ name: fields.get("name"), category_id: category,
          google_review_url: url, description: fields.get("description") || null,
          brand_tone: fields.get("brand_tone"), destination_confirmed: confirmed,
          status: business ? fields.get("status") : "active" }),
      });
      router.push("/dashboard?saved=1");
    } catch (err) { setError(err instanceof Error ? err.message : "Please try again."); }
    finally { setBusy(false); }
  }
  return <form onSubmit={submit} className="panel space-y-6">
    <label>Business name<input name="name" required maxLength={120} defaultValue={business?.name} placeholder="Mario’s Italian Kitchen" /></label>
    <label>Business category<select name="category_id" required value={category} onChange={e => setCategory(e.target.value)}><option value="" disabled>Select a category</option>{categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
    {category && <p className="muted text-sm">Experience topics: {categories.find(c => c.id === category)?.attributes.map(a => a.label).join(" · ")}</p>}
    <div className="border-t border-[#e0e5db] pt-6"><label>Google review link<input name="google_review_url" type="url" required maxLength={2048} value={url} onChange={e => { setUrl(e.target.value.trim()); setConfirmed(false); }} placeholder="https://g.page/r/…/review" aria-describedby="google-help" /></label>
      <p id="google-help" className="muted mt-2 text-sm">Paste any complete HTTPS link, including a Google Search or Maps link. Test it to confirm customers will reach the correct business.</p>
      {testable && <a className="mt-3 inline-block min-h-11 py-2 font-semibold underline" href={url} target="_blank" rel="noopener noreferrer">Test destination ↗</a>}
      <label className="mt-3 flex items-start gap-3 leading-relaxed"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} />I opened this link and confirmed it shows the correct business.</label>
    </div>
    <label>Description <span className="muted font-normal">(optional)</span><textarea name="description" maxLength={500} rows={3} defaultValue={business?.description || ""} placeholder="A few words about your business." /></label>
    <label>Brand tone<select name="brand_tone" defaultValue={business?.brand_tone || "friendly"}><option value="friendly">Friendly</option><option value="casual">Casual</option><option value="professional">Professional</option><option value="luxury">Luxury</option></select></label>
    <p className="muted text-xs">Tone guides wording. It never changes a customer’s rating or experience.</p>
    {business && <label>Business status<select name="status" defaultValue={business.status}><option value="active">Active</option><option value="paused">Paused</option><option value="draft">Draft</option></select></label>}
    {error && <p className="error" role="alert">{error}</p>}
    <button className="button w-full" disabled={busy}>{busy ? "Saving your business…" : business ? "Save changes" : "Create business"}</button>
  </form>;
}
