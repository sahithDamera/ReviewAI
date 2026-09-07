"use client";

import { useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/services/api";
import { Brand } from "./Brand";

export function OwnerHeader() {
  const router = useRouter();
  const pathname = usePathname();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const links = [["/dashboard", "Overview"], ["/dashboard/activity", "Activity"], ["/dashboard/analytics", "Analytics"], ["/dashboard/qr", "QR code"], ["/dashboard/settings", "Settings"]] as const;
  async function logout() {
    setBusy(true); setError("");
    try { await api("/auth/logout", { method: "POST" }); router.replace("/login"); }
    catch { setError("Could not log out. Please try again."); }
    finally { setBusy(false); }
  }
  return <header className="border-b border-[#dce3d9] bg-white px-5 py-4 sm:px-6"><div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4"><Brand /><button onClick={logout} disabled={busy} className="order-2 min-h-11 underline sm:order-3">{busy ? "Logging out..." : "Log out"}</button><nav aria-label="Owner navigation" className="order-3 flex w-full gap-1 overflow-x-auto border-t border-[#eef1eb] pt-3 text-sm sm:order-2 sm:w-auto sm:border-0 sm:pt-0">{links.map(([href, label]) => <Link key={href} href={href} aria-current={pathname === href ? "page" : undefined} className={`whitespace-nowrap rounded-lg px-3 py-2 ${pathname === href ? "bg-[#edf2e7] font-semibold text-[#236b52]" : "hover:bg-[#f6f7f2]"}`}>{label}</Link>)}</nav></div>{error && <p className="error mx-auto mt-4 max-w-6xl" role="alert">{error}</p>}</header>;
}
