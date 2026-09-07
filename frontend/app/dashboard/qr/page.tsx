"use client";
/* eslint-disable @next/next/no-img-element */

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError, Business } from "@/services/api";
import { OwnerHeader } from "@/components/OwnerHeader";

export default function QRPage() {
  const router = useRouter();
  const [business, setBusiness] = useState<Business>();
  const [error, setError] = useState("");
  useEffect(() => { api<Business>("/businesses/me").then(setBusiness).catch(err => {
    if (err instanceof ApiError && err.status === 401) router.replace("/login");
    else setError("Could not load your QR code.");
  }); }, [router]);
  return <><OwnerHeader /><main className="mx-auto max-w-3xl px-6 py-12"><p className="eyebrow">QR code</p><h1 className="mt-3 text-4xl font-semibold">Make your review link easy to scan.</h1>{error ? <p className="error mt-8" role="alert">{error}</p> : !business ? <p className="muted mt-8" role="status">Loading…</p> : <section className="panel mt-8"><p className="muted text-sm">This QR code opens your ReviewFlow customer page. It does not send customers directly to Google.</p><div className="mt-8 flex justify-center rounded-xl bg-white p-6"><img className="h-64 w-64" src={`/api/businesses/${business.id}/qr?format=png`} alt={`QR code for ${business.name} review page`} /></div><p className="muted mt-6 break-all text-sm">{business.review_url}</p><div className="mt-7 flex flex-wrap gap-3"><a className="button" href={`/api/businesses/${business.id}/qr?format=png`}>Download PNG</a><a className="button secondary" href={`/api/businesses/${business.id}/qr?format=svg`}>Download SVG</a></div><p className="muted mt-6 text-sm">Test the code with your phone before printing it.</p></section>}</main></>;
}
