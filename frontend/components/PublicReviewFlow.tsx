"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError, GenerateResponse, PublicBusiness, ReviewAttribute, ReviewSession, SelectionResponse } from "@/services/api";

const tokenKey = (identifier: string) => `reviewflow_session_${identifier}`;
const draftKey = (identifier: string) => `reviewflow_draft_${identifier}`;
const stepKey = (identifier: string) => `reviewflow_step_${identifier}`;

export function PublicReviewFlow({ identifier }: { identifier: string }) {
  const [business, setBusiness] = useState<PublicBusiness>();
  const [session, setSession] = useState<ReviewSession>();
  const [step, setStep] = useState(1);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(true);
  const [draft, setDraft] = useState("");
  const [generation, setGeneration] = useState<GenerateResponse>();
  const [manualOnly, setManualOnly] = useState(false);
  const [selectedOptionId, setSelectedOptionId] = useState("1");
  const [handoffMessage, setHandoffMessage] = useState("");
  const googleLinkRef = useRef<HTMLAnchorElement>(null);
  const allowGoogleNavigation = useRef(false);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const profile = await api<PublicBusiness>(`/public/business/${encodeURIComponent(identifier)}`);
        const savedDraft = window.sessionStorage.getItem(draftKey(identifier));
        let draft: Pick<ReviewSession, "rating" | "selected_attributes" | "customer_comment"> | undefined;
        try { draft = savedDraft ? JSON.parse(savedDraft) : undefined; } catch { window.sessionStorage.removeItem(draftKey(identifier)); }
        const savedStep = Number(window.sessionStorage.getItem(stepKey(identifier)) || "1");
        const saved = window.sessionStorage.getItem(tokenKey(identifier));
        let current: ReviewSession | undefined;
        if (saved) {
          try {
            current = await api<ReviewSession>("/public/review-session", {
              headers: { Authorization: `Bearer ${saved}` },
            });
          } catch (err) {
            if (!(err instanceof ApiError) || (err.status !== 401 && err.status !== 410)) throw err;
            window.sessionStorage.removeItem(tokenKey(identifier));
          }
        }
        if (!current) {
          current = await api<ReviewSession>("/public/review-session", {
            method: "POST", body: JSON.stringify({ business_identifier: identifier, entry_source: "direct" }),
          });
          window.sessionStorage.setItem(tokenKey(identifier), current.session_token);
          if (draft && (draft.rating || draft.selected_attributes?.length || draft.customer_comment)) {
            current = await api<ReviewSession>("/public/review-session", {
              method: "PATCH", headers: { Authorization: `Bearer ${current.session_token}` },
              body: JSON.stringify({ input_version: current.input_version, ...draft }),
            });
          }
        }
        if (active) {
          setBusiness(profile); setSession(current); setError("");
          if (current.rating) setStep(savedStep >= 2 && savedStep <= 3 ? savedStep : 1);
          if (current.customer_comment) setDraft(current.customer_comment);
        }
      } catch (err) {
        if (active) setError(err instanceof Error ? err.message : "This review page is unavailable.");
      } finally { if (active) setBusy(false); }
    }
    load();
    return () => { active = false; };
  }, [identifier]);

  useEffect(() => {
    if (!session) return;
    window.sessionStorage.setItem(draftKey(identifier), JSON.stringify({
      rating: session.rating,
      selected_attributes: session.selected_attributes,
      customer_comment: session.customer_comment,
    }));
  }, [identifier, session]);

  useEffect(() => {
    window.sessionStorage.setItem(stepKey(identifier), String(step));
  }, [identifier, step]);

  const selected = useMemo(() => session?.selected_attributes || [], [session?.selected_attributes]);
  const selectedMap = useMemo(() => new Map(selected.map(item => [item.attribute_id, item.polarity])), [selected]);

  function setAttribute(attributeId: string, checked: boolean) {
    if (!session) return;
    const next = checked
      ? [...selected.filter(item => item.attribute_id !== attributeId), { attribute_id: attributeId, polarity: "mentioned" as const }]
      : selected.filter(item => item.attribute_id !== attributeId);
    setSession({ ...session, selected_attributes: next });
  }

  function setPolarity(attributeId: string, polarity: ReviewAttribute["polarity"]) {
    if (!session) return;
    setSession({ ...session, selected_attributes: selected.map(item => item.attribute_id === attributeId ? { ...item, polarity } : item) });
  }

  async function continueToWriting() {
    if (!session) return;
    setBusy(true); setError("");
    try {
      const updated = await api<ReviewSession>("/public/review-session", {
        method: "PATCH", headers: { Authorization: `Bearer ${session.session_token}` },
        body: JSON.stringify({ input_version: session.input_version, rating: session.rating,
          selected_attributes: session.selected_attributes, customer_comment: session.customer_comment }),
      });
      setSession(updated);
      try {
        const generated = await api<GenerateResponse>("/public/generate-review", {
          method: "POST", headers: { Authorization: `Bearer ${updated.session_token}`, "Idempotency-Key": crypto.randomUUID() },
          body: JSON.stringify({ input_version: updated.input_version }),
        });
        setGeneration(generated); setManualOnly(false); setSelectedOptionId("1"); setDraft(generated.reviews[0].text);
      } catch { setGeneration(undefined); setManualOnly(true); setError("Suggestions are unavailable right now. You can write your own review below."); }
      setStep(3);
    } catch (err) { setError(err instanceof Error ? err.message : "Could not save your answers. Please try again."); }
    finally { setBusy(false); }
  }

  async function copyAndContinue() {
    if (!session || !draft.trim()) return;
    const clipboardWrite = navigator.clipboard.writeText(draft);
    setBusy(true); setError(""); setHandoffMessage("");
    const eventId = crypto.randomUUID();
    let copied = false;
    try { await clipboardWrite; copied = true; }
    catch { setHandoffMessage("Copy was blocked by your browser. Your review is still available to copy manually."); }
    try {
      const selection = await api<SelectionResponse>("/public/select-review", {
        method: "POST", headers: { Authorization: `Bearer ${session.session_token}` },
        body: JSON.stringify({ source: manualOnly ? "manual" : "ai", generation_id: manualOnly ? null : generation?.generation_id,
          option_id: manualOnly ? null : selectedOptionId, final_text: draft }),
      });
      const eventBody = JSON.stringify({ event_id: eventId, selection_id: selection.selection_id, outcome: copied ? "success" : "failed" });
      void fetch("/api/public/copy-event", { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${session.session_token}` }, body: eventBody, keepalive: true });
      if (copied) {
        window.sessionStorage.removeItem(tokenKey(identifier));
        window.sessionStorage.removeItem(draftKey(identifier));
        window.sessionStorage.removeItem(stepKey(identifier));
      }
      void fetch("/api/public/google-open-event", { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${session.session_token}` }, body: JSON.stringify({ event_id: crypto.randomUUID(), selection_id: selection.selection_id }), keepalive: true });
      allowGoogleNavigation.current = true;
      googleLinkRef.current?.click();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not save your review. Please try again."); }
    finally { setBusy(false); }
  }

  if (busy && !business) return <main className="mx-auto max-w-xl px-6 py-16"><p role="status">Loading this review page…</p></main>;
  if (error && !business) return <main className="mx-auto max-w-xl px-6 py-16"><div className="panel"><h1 className="text-2xl font-semibold">This review page is unavailable.</h1><p className="error mt-4" role="alert">{error}</p></div></main>;
  if (!business || !session) return null;
  return <main className="mx-auto max-w-xl px-5 py-8 sm:px-6 sm:py-16">
    <header className="mb-10 text-center"><p className="eyebrow">Share your experience</p><h1 className="mt-3 text-4xl font-semibold">{business.name}</h1><p className="muted mt-3">{business.category_name}</p><p className="muted mt-8 text-sm">Step {step} of 3</p></header>
    {step === 1 && <section className="panel" aria-labelledby="rating-title"><h2 id="rating-title" className="text-2xl font-semibold">How was your experience?</h2><div className="mt-8 grid grid-cols-5 gap-2" role="radiogroup" aria-label="Overall rating">{[1,2,3,4,5].map(rating => <button key={rating} type="button" role="radio" aria-checked={session.rating === rating} aria-label={`${rating} out of 5 stars`} className={`min-h-14 rounded-xl border text-2xl ${session.rating === rating ? "border-[#236b52] bg-[#edf2e7]" : "border-[#cbd6c7]"}`} onClick={() => setSession({ ...session, rating })}>★</button>)}</div><button className="button mt-8 w-full" disabled={!session.rating} onClick={() => setStep(2)}>Continue</button></section>}
    {step === 2 && <section className="panel" aria-labelledby="topics-title"><h2 id="topics-title" className="text-2xl font-semibold">What stood out?</h2><p className="muted mt-2 text-sm">Choose any topics. You can skip this step.</p><div className="mt-6 space-y-3">{business.attributes.map(attribute => { const polarity = selectedMap.get(attribute.id); return <div key={attribute.id} className="flex items-center gap-3"><label className="flex min-h-11 flex-1 items-center gap-3"><input type="checkbox" checked={polarity !== undefined} onChange={event => setAttribute(attribute.id, event.target.checked)} />{attribute.label}</label>{polarity && <select aria-label={`${attribute.label} sentiment`} value={polarity} onChange={event => setPolarity(attribute.id, event.target.value as ReviewAttribute["polarity"])}><option value="mentioned">Mentioned</option><option value="positive">Liked</option><option value="negative">Could improve</option></select>}</div>; })}</div><label className="mt-7">Anything else? <span className="muted font-normal">(optional)</span><textarea className="mt-2" rows={4} maxLength={500} value={session.customer_comment || ""} onChange={event => setSession({ ...session, customer_comment: event.target.value })} placeholder="Share a detail in your own words." /></label>{error && <p className="error mt-4" role="alert">{error}</p>}<div className="mt-8 flex gap-3"><button className="button secondary flex-1" onClick={() => setStep(1)}>Back</button><button className="button flex-1" disabled={busy} onClick={continueToWriting}>{busy ? "Saving…" : "Continue"}</button></div></section>}
    {step === 3 && <section className="panel" aria-labelledby="write-title"><h2 id="write-title" className="text-2xl font-semibold">{generation && !manualOnly ? "Choose a review" : "Write your review"}</h2><p className="muted mt-2 text-sm">{generation && !manualOnly ? "Pick one, then edit it so it matches your experience." : "Use your own words. Only you decide what to share."}</p>{generation && !manualOnly && <div className="mt-7 space-y-3">{generation.reviews.map(option => <button key={option.id} type="button" className={`w-full rounded-xl border p-4 text-left leading-relaxed ${draft === option.text ? "border-[#236b52] bg-[#edf2e7]" : "border-[#cbd6c7]"}`} onClick={() => setDraft(option.text)}><span className="eyebrow">Option {option.id}</span><span className="mt-2 block">{option.text}</span></button>)}</div>}<label className="mt-7">Your review<textarea className="mt-2" rows={8} maxLength={2000} value={draft} onChange={event => setDraft(event.target.value)} placeholder="Write about your experience…" /></label><p className="muted mt-2 text-right text-sm">{draft.length}/2000</p>{handoffMessage && <p className="muted mt-4" role="status">{handoffMessage}</p>}{error && <p className="error mt-4" role="alert">{error}</p>}<a ref={googleLinkRef} className="button mt-6 block w-full text-center" href={session.business.google_review_url} target="_blank" rel="noopener" onClick={event => { if (allowGoogleNavigation.current) { allowGoogleNavigation.current = false; return; } event.preventDefault(); void copyAndContinue(); }}>{busy ? "Saving…" : "Copy & Continue to Google"}</a><button className="mt-4 min-h-11 w-full underline" onClick={() => setStep(2)}>Edit answers</button></section>}
  </main>;
}
