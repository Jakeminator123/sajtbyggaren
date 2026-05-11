"use client";

export default function GlobalError({
  error: _error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="sv">
      <body style={{ margin: 0, backgroundColor: "#000", color: "#e5e7eb", fontFamily: "system-ui, sans-serif" }}>
        <div style={{ display: "flex", minHeight: "100vh", alignItems: "center", justifyContent: "center", padding: "1rem" }}>
          <div style={{ maxWidth: 420, textAlign: "center" }}>
            <h2 style={{ fontSize: "1.25rem", fontWeight: 700, color: "#fff", marginBottom: "0.5rem" }}>
              Något gick fel
            </h2>
            <p style={{ color: "#9ca3af", marginBottom: "1.5rem" }}>
              Ett oväntat fel inträffade. Försök att ladda om sidan.
            </p>
            <button
              onClick={() => reset()}
              style={{
                padding: "0.5rem 1.5rem",
                backgroundColor: "#3b82f6",
                color: "#fff",
                border: "none",
                borderRadius: "0.5rem",
                cursor: "pointer",
                fontWeight: 500,
              }}
            >
              Försök igen
            </button>
          </div>
        </div>
      </body>
    </html>
  );
}
