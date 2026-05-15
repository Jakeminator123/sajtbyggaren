"use client";

/*
 * Demo-baseline-fix 1A (B41 follow-up): provide an explicit
 * `app/global-error.tsx` so Next.js does not fall back to its synthetic
 * `/_global-error` prerender, which crashes during `next build` with
 * `TypeError: Cannot read properties of null (reading 'useContext')`
 * on Next 16.x + Turbopack. Keep the component minimal (no third-party
 * imports, no React context usage) so it cannot itself reintroduce the
 * same failure mode.
 *
 * Kept in starter-source so every generated site inherits the fix
 * without per-build patching. The in-memory StackBlitz override in
 * `apps/viewser/lib/stackblitz-files.ts` skips when this file is
 * present.
 */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="sv">
      <body
        style={{
          fontFamily: "system-ui, sans-serif",
          padding: "2rem",
          color: "#111",
          background: "#fff",
        }}
      >
        <h2>Något gick fel</h2>
        <p>{error?.message ?? "Okänt fel"}</p>
        <button
          onClick={() => reset()}
          style={{
            marginTop: "1rem",
            padding: "0.5rem 1rem",
            border: "1px solid #111",
            background: "transparent",
            cursor: "pointer",
          }}
        >
          Försök igen
        </button>
      </body>
    </html>
  );
}
