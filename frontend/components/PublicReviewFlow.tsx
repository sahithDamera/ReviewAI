"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  api, ApiError, GenerateResponse, PublicBusiness, ReviewAttribute, ReviewSession,
  SelectionResponse,
} from "@/services/api";

const tokenKey = (identifier: string) => `reviewflow_session_${identifier}`;
const draftKey = (identifier: string) => `reviewflow_draft_${identifier}`;

export function PublicReviewFlow({ identifier }: { identifier: string }) {
  const [business, setBusiness] = useState<PublicBusiness>();
  const [session, setSession] = useState<ReviewSession>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(true);
  const [draft, setDraft] = useState("");
  const [generation, setGeneration] = useState<GenerateResponse>();
  const [manualOnly, setManualOnly] = useState(false);
  const [editing, setEditing] = useState(false);
  const [selectedOptionId, setSelectedOptionId] = useState("1");
  const [handoffMessage, setHandoffMessage] = useState("");
  const [generationAttempts, setGenerationAttempts] = useState(0);
  const topicsRef = useRef<HTMLElement>(null);
  const writingRef = useRef<HTMLElement>(null);
  const googleLinkRef = useRef<HTMLAnchorElement>(null);
  const allowGoogleNavigation = useRef(false);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const profile = await api<PublicBusiness>(`/public/business/${encodeURIComponent(identifier)}`);
        const savedDraft = window.sessionStorage.getItem(draftKey(identifier));
        const draftData = savedDraft ? JSON.parse(savedDraft) : undefined;
        const saved = window.sessionStorage.getItem(tokenKey(identifier));
        let current: ReviewSession | undefined;
        if (saved) {
          try { current = await api<ReviewSession>("/public/review-session", { headers: { Authorization: `Bearer ${saved}` } }); }
          catch (err) { if (!(err instanceof ApiError) || (err.status !== 401 && err.status !== 410)) throw err; window.sessionStorage.removeItem(tokenKey(identifier)); }
        }
        if (!current) {
          current = await api<ReviewSession>("/public/review-session", { method: "POST", body: JSON.stringify({ business_identifier: identifier, entry_source: "direct" }) });
          window.sessionStorage.setItem(tokenKey(identifier), current.session_token);
          if (draftData && (draftData.rating || draftData.selected_attributes?.length || draftData.customer_comment)) {
            current = await api<ReviewSession>("/public/review-session", { method: "PATCH", headers: { Authorization: `Bearer ${current.session_token}` }, body: JSON.stringify({ input_version: current.input_version, ...draftData }) });
          }
        }
        if (active) { setBusiness(profile); setSession(current); setDraft(current.customer_comment || ""); setError(""); }
      } catch (err) { if (active) setError(err instanceof Error ? err.message : "This review page is unavailable."); }
      finally { if (active) setBusy(false); }
    }
    load();
    return () => { active = false; };
  }, [identifier]);

  useEffect(() => {
    if (!session) return;
    window.sessionStorage.setItem(draftKey(identifier), JSON.stringify({ rating: session.rating, selected_attributes: session.selected_attributes, customer_comment: session.customer_comment }));
  }, [identifier, session]);

  const selected = useMemo(() => session?.selected_attributes || [], [session?.selected_attributes]);
  const selectedMap = useMemo(() => new Map(selected.map(item => [item.attribute_id, item.polarity])), [selected]);
  const canGenerate = Boolean(session?.rating) && !busy;
  const canRegenerate = generationAttempts < 3 && Boolean(session?.rating) && !busy;

  function chooseRating(rating: number) {
    if (!session) return;
    setSession({ ...session, rating });
    window.setTimeout(() => topicsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 0);
  }
  function setAttribute(attributeId: string, checked: boolean) {
    if (!session) return;
    const next = checked ? [...selected.filter(item => item.attribute_id !== attributeId), { attribute_id: attributeId, polarity: "mentioned" as const }] : selected.filter(item => item.attribute_id !== attributeId);
    setSession({ ...session, selected_attributes: next });
  }
  function setPolarity(attributeId: string, polarity: ReviewAttribute["polarity"]) {
    if (session) setSession({ ...session, selected_attributes: selected.map(item => item.attribute_id === attributeId ? { ...item, polarity } : item) });
  }
  async function generateSuggestions() {
    if (!session?.rating || busy) return;
    setBusy(true); setError("");
    try {
      const updated = await api<ReviewSession>("/public/review-session", { method: "PATCH", headers: { Authorization: `Bearer ${session.session_token}` }, body: JSON.stringify({ input_version: session.input_version, rating: session.rating, selected_attributes: session.selected_attributes, customer_comment: session.customer_comment }) });
      // The PATCH advances input_version. Keep the local session current before
      // generating so a failed provider request can be safely retried.
      setSession(updated);
      const generated = await api<GenerateResponse>("/public/generate-review", { method: "POST", headers: { Authorization: `Bearer ${updated.session_token}`, "Idempotency-Key": crypto.randomUUID() }, body: JSON.stringify({ input_version: updated.input_version }) });
      setGeneration(generated); setGenerationAttempts(value => value + 1); setManualOnly(false); setEditing(false); setSelectedOptionId("1"); setDraft(generated.reviews[0].text);
      window.setTimeout(() => writingRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 0);
    } catch (err) {
      if (err instanceof ApiError && err.code === "REVIEW_INPUT_CHANGED") {
        try {
          const current = await api<ReviewSession>("/public/review-session", { headers: { Authorization: `Bearer ${session.session_token}` } });
          setSession(current);
          setError("Your answers were refreshed. Tap Get suggestions again.");
        } catch {
          setError("Your review session changed. Refresh the page and try again.");
        }
      } else {
        setGenerationAttempts(value => err instanceof ApiError && err.status === 429 ? 3 : value + 1);
        setManualOnly(true); setEditing(true);
        setError(err instanceof Error ? err.message : "Suggestions are unavailable. You can write your own review.");
      }
    }
    finally { setBusy(false); }
  }
  async function copyAndContinue() {
    if (!session || !draft.trim()) return;
    const clipboardWrite = navigator.clipboard.writeText(draft);
    setBusy(true); setError(""); setHandoffMessage("");
    const eventId = crypto.randomUUID(); let copied = false;
    try { await clipboardWrite; copied = true; } catch { setHandoffMessage("Copy was blocked. Your review is still available to copy manually."); }
    try {
      const selection = await api<SelectionResponse>("/public/select-review", { method: "POST", headers: { Authorization: `Bearer ${session.session_token}` }, body: JSON.stringify({ source: manualOnly ? "manual" : "ai", generation_id: manualOnly ? null : generation?.generation_id, option_id: manualOnly ? null : selectedOptionId, final_text: draft }) });
      void fetch("/api/public/copy-event", { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${session.session_token}` }, body: JSON.stringify({ event_id: eventId, selection_id: selection.selection_id, outcome: copied ? "success" : "failed" }), keepalive: true });
      if (copied) { window.sessionStorage.removeItem(tokenKey(identifier)); window.sessionStorage.removeItem(draftKey(identifier)); }
      void fetch("/api/public/google-open-event", { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${session.session_token}` }, body: JSON.stringify({ event_id: crypto.randomUUID(), selection_id: selection.selection_id }), keepalive: true });
      allowGoogleNavigation.current = true; googleLinkRef.current?.click();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not save your review. Please try again."); }
    finally { setBusy(false); }
  }

  if (busy && !business) return <main className="mx-auto max-w-xl px-6 py-16"><p role="status">Loading this review page…</p></main>;
  if (error && !business) return <main className="mx-auto max-w-xl px-6 py-16"><div className="panel"><h1 className="text-2xl font-semibold">This review page is unavailable.</h1><p className="error mt-4" role="alert">{error}</p></div></main>;
  if (!business || !session) return null;
  return <main className="mx-auto max-w-xl space-y-6 px-5 py-8 sm:px-6 sm:py-16">
    <header className="text-center"><p className="eyebrow">Share your experience</p><h1 className="mt-3 text-4xl font-semibold">{business.name}</h1><p className="muted mt-3">{business.category_name}</p></header>
    <section className="panel" aria-labelledby="rating-title"><h2 id="rating-title" className="text-2xl font-semibold">How was your visit?</h2><div className="mt-8 grid grid-cols-5 gap-2" role="radiogroup" aria-label="Overall rating">{[1, 2, 3, 4, 5].map(rating => <button key={rating} type="button" role="radio" aria-checked={session.rating === rating} aria-label={`${rating} out of 5 stars`} className={`min-h-14 rounded-xl border text-2xl focus:outline-none focus:ring-2 focus:ring-[#236b52] ${session.rating === rating ? "border-[#236b52] bg-[#edf2e7]" : "border-[#cbd6c7]"}`} onClick={() => chooseRating(rating)}>★</button>)}</div></section>
    {session.rating && <section ref={topicsRef} className="panel space-y-6" aria-live="polite" aria-labelledby="topics-title"><div><h2 id="topics-title" className="text-2xl font-semibold">What stood out?</h2><p className="muted mt-2 text-sm">Topics and comments are optional.</p></div><div className="flex flex-wrap gap-2">{business.attributes.map(attribute => { const polarity = selectedMap.get(attribute.id); return <button key={attribute.id} type="button" aria-pressed={polarity !== undefined} className={`min-h-11 rounded-full border px-4 ${polarity ? "border-[#236b52] bg-[#edf2e7]" : "border-[#cbd6c7]"}`} onClick={() => setAttribute(attribute.id, polarity === undefined)}>{attribute.label}{polarity && <select aria-label={`${attribute.label} sentiment`} value={polarity} onClick={event => event.stopPropagation()} onChange={event => setPolarity(attribute.id, event.target.value as ReviewAttribute["polarity"])}><option value="mentioned">Mentioned</option><option value="positive">Liked</option><option value="negative">Could improve</option></select>}</button>; })}</div><label>Anything you’d like to add? <span className="muted font-normal">(optional)</span><textarea className="mt-2" rows={4} maxLength={500} value={session.customer_comment || ""} onChange={event => setSession({ ...session, customer_comment: event.target.value })} placeholder="Share a detail in your own words." /></label>{error && <p className="error" role="alert">{error}</p>}{!generation && !editing && <><button className="button w-full" disabled={!canGenerate} onClick={generateSuggestions}>{busy ? "Writing a few options…" : "Get suggestions"}</button><button className="min-h-11 w-full underline" onClick={() => { setManualOnly(true); setEditing(true); }}>Write my own</button></>}</section>}
    {session.rating && (generation || editing) && <section ref={writingRef} className="panel space-y-5" aria-labelledby="write-title"><h2 id="write-title" className="text-2xl font-semibold">{generation && !manualOnly && !editing ? "Choose a review" : "Your review"}</h2>{generation && !manualOnly && !editing && <div className="space-y-3">{generation.reviews.map(option => <article key={option.id} className="rounded-xl border border-[#cbd6c7] p-4"><p className="leading-relaxed">{option.text}</p><button className="button secondary mt-4" onClick={() => { setSelectedOptionId(option.id); setDraft(option.text); setEditing(true); }}>Use this</button></article>)}</div>}{editing && <><textarea aria-label="Your review" className="mt-2" rows={8} maxLength={2000} value={draft} onChange={event => setDraft(event.target.value)} /><p className="muted text-right text-sm">{draft.length}/2000</p>{generation && <button className="min-h-11 underline" onClick={() => { setManualOnly(false); setEditing(false); }}>Back to suggestions</button>}{manualOnly && !generation && <button className="button secondary w-full" disabled={!canGenerate} onClick={generateSuggestions}>{canGenerate ? "Get suggestions" : "Suggestion limit reached"}</button>}{generation && !manualOnly && <button className="button secondary w-full" disabled={!canRegenerate} onClick={generateSuggestions}>{canRegenerate ? "Regenerate" : "Suggestion limit reached"}</button>}<a ref={googleLinkRef} className="button block w-full text-center" href={session.business.google_review_url} target="_blank" rel="noopener" onClick={event => { if (allowGoogleNavigation.current) { allowGoogleNavigation.current = false; return; } event.preventDefault(); void copyAndContinue(); }}>{busy ? "Saving…" : "Copy & Continue to Google"}</a></>}{handoffMessage && <p className="muted" role="status">{handoffMessage}</p>}{error && <p className="error" role="alert">{error}</p>}</section>}
  </main>;
}
