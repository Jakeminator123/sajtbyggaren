"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export function LogoutButton() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function handleLogout() {
    setBusy(true);
    try {
      await fetch("/api/auth/logout", { method: "POST" });
    } finally {
      router.push("/");
      router.refresh();
    }
  }

  return (
    <button
      type="button"
      onClick={handleLogout}
      disabled={busy}
      className="border-border text-foreground hover:bg-muted focus-visible:ring-ring/50 inline-flex h-10 items-center justify-center rounded-full border px-5 text-[14px] font-medium transition-colors focus-visible:ring-2 focus-visible:outline-none disabled:opacity-60"
    >
      {busy ? "Loggar ut…" : "Logga ut"}
    </button>
  );
}
