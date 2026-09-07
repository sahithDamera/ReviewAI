"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/services/api";
import { Brand } from "./Brand";

export function OwnerHeader() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function logout() {
    setBusy(true); setError("");
    try { await api("/auth/logout", { method: "POST" }); router.replace("/login"); }
    catch { setError("Could not log out. Please try again."); }
    finally { setBusy(false); }
  }
  return <header className="border-b border-[#dce3d9] bg-white px-6 py-5"><div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-4"><Brand /><nav className="flex items-center gap-5 text-sm"><Link href="/dashboard">My business</Link><button onClick={logout} disabled={busy} className="min-h-11 underline">{busy ? "Logging out…" : "Log out"}</button></nav></div>{error && <p className="error mx-auto mt-4 max-w-5xl" role="alert">{error}</p>}</header>;
}
