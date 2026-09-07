"use client";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api } from "@/services/api";
function VerifyStatus() { const token = useSearchParams().get("token"); const [message, setMessage] = useState(token ? "Verifying your email…" : "Verification token is missing."); useEffect(() => { if (token) api("/auth/verify", { method: "POST", body: JSON.stringify({ token }) }).then(() => setMessage("Email verified. You can now publish your business."), () => setMessage("This verification link is invalid or expired.")); }, [token]); return <section className="panel"><h1 className="text-2xl font-semibold">Email verification</h1><p className="muted mt-4" role="status">{message}</p></section>; }
export default function VerifyPage() { return <main className="mx-auto max-w-md px-6 py-16"><Suspense fallback={<p role="status">Loading…</p>}><VerifyStatus /></Suspense></main>; }
