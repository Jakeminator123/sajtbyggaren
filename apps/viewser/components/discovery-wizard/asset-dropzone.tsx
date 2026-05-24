"use client";

import { useCallback, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import type { AssetRef, AssetRole } from "@/lib/asset-store/types";

/**
 * AssetDropzone — gemensam drag-drop/klick-välj-komponent för wizardens
 * AssetsStep. Hanterar:
 *   1. Drag-and-drop (visuell hover-state via `dragging`)
 *   2. Klick-att-välja via dolt <input type="file">
 *   3. POST till /api/upload-asset med rätt `role`
 *   4. Felmeddelanden från servern (MIME, size, antal)
 *   5. Progress-spinner medan sharp + GPT Vision körs serverside
 *
 * När uppladdningen lyckas returnerar API:t en AssetRef som komponenten
 * skickar till `onUploaded` (parent uppdaterar WizardAnswers.assets).
 *
 * Stylen är minimalistisk för att inte konkurrera med övriga wizardsteg.
 */

const IMAGE_ACCEPT_ATTR = "image/png,image/jpeg,image/webp,image/svg+xml";
const VIDEO_ACCEPT_ATTR = "video/mp4,video/webm";

/**
 * Roles som accepterar video-uploads. Vid render avgör vi om
 * <input accept> ska peka mot image- eller video-mimes så browser:s
 * native file-picker pre-filtrerar rätt. Drag-and-drop-flödet använder
 * samma whitelist för att inte krascha sharp downstream.
 */
const VIDEO_ROLES = new Set<AssetRole>(["backgroundVideo"]);

export type AssetDropzoneProps = {
  role: AssetRole;
  /** "single" tillåter bara 1 fil/upload (logo, hero). "multi" tar flera. */
  mode: "single" | "multi";
  /** Visas i tom-state. Ex: "Släpp din logotyp här". */
  emptyLabel: string;
  /** Visas under emptyLabel som finstilt hint. */
  hintLabel?: string;
  onUploaded: (refs: AssetRef[]) => void;
  /** Optional bound siteId; om utelämnad används backend-default "__draft". */
  siteId?: string;
};

export function AssetDropzone({
  role,
  mode,
  emptyLabel,
  hintLabel,
  onUploaded,
  siteId,
}: AssetDropzoneProps) {
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const acceptVideo = VIDEO_ROLES.has(role);
  const acceptAttr = acceptVideo ? VIDEO_ACCEPT_ATTR : IMAGE_ACCEPT_ATTR;

  const uploadFiles = useCallback(
    async (files: File[]) => {
      if (files.length === 0) return;
      setBusy(true);
      setError(null);
      const uploaded: AssetRef[] = [];
      try {
        for (const file of files) {
          const formData = new FormData();
          formData.append("file", file);
          formData.append("role", role);
          if (siteId) formData.append("siteId", siteId);
          const response = await fetch("/api/upload-asset", {
            method: "POST",
            body: formData,
          });
          const payload = (await response.json().catch(() => ({}))) as {
            ok?: boolean;
            ref?: AssetRef;
            error?: string;
          };
          if (!response.ok || !payload.ok || !payload.ref) {
            throw new Error(
              payload.error ?? `Uppladdning misslyckades (HTTP ${response.status}).`,
            );
          }
          uploaded.push(payload.ref);
        }
        onUploaded(uploaded);
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : "Okänt fel.");
      } finally {
        setBusy(false);
      }
    },
    [onUploaded, role, siteId],
  );

  const onInputChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const files = Array.from(event.target.files ?? []);
      // Reset input så att samma fil kan väljas igen efter borttagning.
      event.target.value = "";
      const limited = mode === "single" ? files.slice(0, 1) : files;
      void uploadFiles(limited);
    },
    [mode, uploadFiles],
  );

  const onDrop = useCallback(
    (event: React.DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      setDragging(false);
      const prefix = acceptVideo ? "video/" : "image/";
      const files = Array.from(event.dataTransfer.files).filter((f) =>
        f.type.startsWith(prefix),
      );
      const limited = mode === "single" ? files.slice(0, 1) : files;
      void uploadFiles(limited);
    },
    [acceptVideo, mode, uploadFiles],
  );

  return (
    <div className="space-y-2">
      <div
        role="button"
        tabIndex={0}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            inputRef.current?.click();
          }
        }}
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={[
          "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed px-6 py-8 text-center transition-colors",
          dragging
            ? "border-primary/70 bg-primary/5"
            : "border-border/70 bg-card/50 hover:border-foreground/40",
          busy ? "pointer-events-none opacity-70" : "",
        ].join(" ")}
      >
        <input
          ref={inputRef}
          type="file"
          accept={acceptAttr}
          multiple={mode === "multi"}
          onChange={onInputChange}
          className="sr-only"
          aria-label={emptyLabel}
        />
        <div className="text-[13px] font-medium text-foreground">
          {busy ? "Laddar upp och analyserar…" : emptyLabel}
        </div>
        {hintLabel ? (
          <div className="text-[11px] text-muted-foreground/80">{hintLabel}</div>
        ) : null}
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="mt-1 h-7 text-[11px]"
          disabled={busy}
          onClick={(event) => {
            event.stopPropagation();
            inputRef.current?.click();
          }}
        >
          {mode === "single" ? "Välj fil" : "Välj filer"}
        </Button>
      </div>
      {error ? (
        <p className="text-[11px] text-amber-600 dark:text-amber-300">{error}</p>
      ) : null}
    </div>
  );
}
