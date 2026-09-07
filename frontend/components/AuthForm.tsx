"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/services/api";
import { Brand } from "./Brand";

export function AuthForm({ signup = false }: { signup?: boolean }) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [registered, setRegistered] = useState(false);
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(""); setBusy(true);
    const fields = new FormData(event.currentTarget);
    const email = String(fields.get("email")).trim().toLowerCase();
    const password = String(fields.get("password"));
    try {
      if (signup && !registered) {
        await api("/auth/register", { method: "POST", body: JSON.stringify({ email, password }) });
        await api("/auth/request-verify-token", { method: "POST", body: JSON.stringify({ email }) });
        setRegistered(true);
      }
      await api("/auth/login", { method: "POST", body: new URLSearchParams({ username: email, password }) });
      router.replace("/dashboard");
    } catch (err) { setError(err instanceof Error ? err.message : "Please try again."); }
    finally { setBusy(false); }
  }
  return <main className="mx-auto max-w-6xl px-6 py-8"><Brand />
    <div className="mx-auto mt-14 max-w-md"><p className="eyebrow mb-4">For business owners</p>
      <h1 className="text-4xl font-semibold">{signup ? "A little effort.\nA better connection." : "Welcome back."}</h1>
      <p className="muted mb-8 mt-4">{signup ? "Create your account, then make this space your business’s own." : "Your business is right where you left it."}</p>
      <form onSubmit={submit} className="panel space-y-5">
        {registered && <p className="success" role="status">Your account is created. Log in to continue.</p>}
        <label>Email address<input name="email" type="email" required maxLength={320} autoComplete="email" placeholder="you@yourbusiness.com" /></label>
        <label>Password<input name="password" type="password" required minLength={signup ? 12 : 1} maxLength={128} autoComplete={signup ? "new-password" : "current-password"} aria-describedby={signup ? "password-help" : undefined} /></label>
        {signup && <p id="password-help" className="muted text-xs">Use 12–128 characters. A memorable passphrase works well.</p>}
        {error && <p className="error" role="alert">{error}</p>}
        <button className="button w-full" disabled={busy}>{busy ? "Please wait…" : signup && !registered ? "Create account" : "Log in"}</button>
      </form>
      <p className="muted mt-6 text-center text-sm">{signup ? "Already have an account?" : "New to ReviewFlow?"} <Link className="font-semibold underline" href={signup ? "/login" : "/signup"}>{signup ? "Log in" : "Create an account"}</Link></p>
    </div>
  </main>;
}
