"use client";

import { useCallback, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import type { AssetRef, AssetRole } from "@/lib/asset-store/types";

/**
 * AssetDropzone — gemensam drag-drop/klick-välj-komponent för wizardens
 * AssetsStep. Hanterar:
 *   1. Drag-and-drop (visuell hover-state via `dragging`)
 *   2. Klick-att-välja via dolt <input type="file">
 *   3. POST till /api/upload-asset med rätt `role` via XMLHttpRequest
 *      så vi kan visa real upload-progress (fetch saknar
 *      ReadableStream-upload-progress i alla browsers idag).
 *   4. Felmeddelanden från servern (MIME, size, antal)
 *   5. Progress-bar 0-100% medan filen laddas upp + serverside-
 *      processing (sharp + GPT Vision). Bytes-fasen mappas till
 *      0-95 %; från full upload till response landar vi 95 → 100 %.
 *
 * När uppladdningen lyckas returnerar API:t en AssetRef som komponenten
 * skickar till `onUploaded` (parent uppdaterar WizardAnswers.assets).
 *
 * Stylen är minimalistisk för att inte konkurrera med övriga wizardsteg.
 */

const IMAGE_ACCEPT_ATTR = "image/png,image/jpeg,image/webp,image/svg+xml";
const VIDEO_ACCEPT_ATTR = "video/mp4,video/webm";

/**
 * Bytes-upload mappas till detta intervall. Hanteringen serverside
 * (sharp + GPT Vision för image-roles) saknar progress-events; vi
 * håller baren på 95 % medan vi väntar på XHR-response, sedan hoppar
 * 95 → 100 % när AssetRef kommer tillbaka. Det ger operatören en
 * tydlig "uppladdning klar, processar nu"-känsla utan att låsa
 * baren på t.ex. 100 % i sekunder vilket skulle se buggigt ut.
 */
const UPLOAD_PHASE_MAX_PERCENT = 95;

/**
 * Roles som accepterar video-uploads. Vid render avgör vi om
 * <input accept> ska peka mot image- eller video-mimes så browser:s
 * native file-picker pre-filtrerar rätt. Drag-and-drop-flödet använder
 * samma whitelist för att inte krascha sharp downstream.
 */
const VIDEO_ROLES = new Set<AssetRole>(["backgroundVideo"]);

type UploadResponse = {
  ok?: boolean;
  ref?: AssetRef;
  error?: string;
};

/**
 * Ladda upp en fil via XMLHttpRequest så `xhr.upload.onprogress`
 * triggar realtids-progress-events. `onProgress` får ett tal i
 * intervallet 0-100 där 0-95 % motsvarar bytes-upload och de sista
 * 5 % markerar att server bearbetar (sharp + GPT Vision för
 * bilder). Returnerar AssetRef vid lyckad upload, kastar Error
 * med beskrivande svenskt meddelande annars.
 *
 * Helpern är skriven som en fri funktion (inte hook) eftersom
 * `uploadFiles` itererar över flera filer i sekvens — vi vill inte
 * ha en useEffect-rerender per chunk.
 */
function uploadOne(
  file: File,
  role: AssetRole,
  siteId: string | undefined,
  onProgress: (percent: number) => void,
): Promise<AssetRef> {
  return new Promise<AssetRef>((resolve, reject) => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("role", role);
    if (siteId) formData.append("siteId", siteId);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/upload-asset");
    xhr.responseType = "json";

    xhr.upload.addEventListener("progress", (event) => {
      if (!event.lengthComputable) return;
      const ratio = event.total > 0 ? event.loaded / event.total : 0;
      // 0-95 % under bytes-fasen så vi inte sitter på 100 % medan
      // server fortfarande kör sharp/Vision.
      onProgress(
        Math.min(UPLOAD_PHASE_MAX_PERCENT, ratio * UPLOAD_PHASE_MAX_PERCENT),
      );
    });

    xhr.upload.addEventListener("load", () => {
      // Bytes är fullt sända — håll baren på 95 % tills response
      // returnerar (server processar nu).
      onProgress(UPLOAD_PHASE_MAX_PERCENT);
    });

    xhr.addEventListener("load", () => {
      const payload = (xhr.response ?? {}) as UploadResponse;
      const status = xhr.status;
      if (status >= 200 && status < 300 && payload.ok && payload.ref) {
        onProgress(100);
        resolve(payload.ref);
        return;
      }
      reject(
        new Error(
          payload.error ?? `Uppladdning misslyckades (HTTP ${status || "?"}).`,
        ),
      );
    });

    xhr.addEventListener("error", () => {
      reject(new Error("Nätverksfel vid uppladdning."));
    });
    xhr.addEventListener("abort", () => {
      reject(new Error("Uppladdningen avbröts."));
    });
    xhr.addEventListener("timeout", () => {
      reject(new Error("Uppladdningen tog för lång tid."));
    });

    xhr.send(formData);
  });
}

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
  // Aggregerat progress-värde 0-100 över hela batch:en (alla filer i
  // ett anrop). null när ingen upload pågår — då doldas baren helt.
  // Per-fil-procenten räknas via uploadOne:s progress-callback och
  // kombineras med antal redan klara filer enligt formel:
  //   ((completedFiles + currentFile / 100) / totalFiles) * 100
  // så multi-fil-uploads (t.ex. galleri-batch) får en jämn ramp i
  // stället för en bar som hoppar 0-100 per fil.
  const [progressPercent, setProgressPercent] = useState<number | null>(null);
  // Räkna ut "5 av 12 bilder"-text när mode==="multi". null vid
  // single-mode så vi slipper visa "1 av 1" som är distraherande.
  const [batchCounter, setBatchCounter] = useState<{
    current: number;
    total: number;
  } | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const acceptVideo = VIDEO_ROLES.has(role);
  const acceptAttr = acceptVideo ? VIDEO_ACCEPT_ATTR : IMAGE_ACCEPT_ATTR;

  const uploadFiles = useCallback(
    async (files: File[]) => {
      if (files.length === 0) return;
      setBusy(true);
      setError(null);
      setProgressPercent(0);
      setBatchCounter(
        files.length > 1 ? { current: 1, total: files.length } : null,
      );
      const uploaded: AssetRef[] = [];
      try {
        for (let index = 0; index < files.length; index += 1) {
          const file = files[index];
          if (files.length > 1) {
            setBatchCounter({ current: index + 1, total: files.length });
          }
          const ref = await uploadOne(file, role, siteId, (perFilePercent) => {
            // Aggregera till total-progress över hela batch:en.
            const aggregate =
              ((index + perFilePercent / 100) / files.length) * 100;
            setProgressPercent(aggregate);
          });
          uploaded.push(ref);
        }
        // När hela batch:en är klar — håll på 100 % en kort stund
        // så användaren ser att det landade innan baren faller bort.
        setProgressPercent(100);
        onUploaded(uploaded);
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : "Okänt fel.");
        // Partiellt fel: filerna FÖRE den som föll har redan landat på
        // servern. Lyft dem ändå så klient-state matchar disken — annars
        // blir de föräldralösa (finns på servern men osynliga i UI:t) och
        // en retry laddar upp dubbletter. onUploaded är additivt
        // (galleri-spread), så detta är säkert.
        if (uploaded.length > 0) onUploaded(uploaded);
      } finally {
        setBusy(false);
        // Liten timeout så 100 %-tillståndet är synligt en frame
        // innan baren försvinner. setTimeout(0) räcker — det
        // garanterar bara att React paintar 100 % innan vi nollar.
        setTimeout(() => {
          setProgressPercent(null);
          setBatchCounter(null);
        }, 200);
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
        <div className="text-foreground text-[13px] font-medium">
          {busy ? "Laddar upp och analyserar…" : emptyLabel}
        </div>
        {hintLabel && !busy ? (
          <div className="text-muted-foreground/80 text-[11px]">
            {hintLabel}
          </div>
        ) : null}
        {busy && progressPercent !== null ? (
          <UploadProgress
            percent={progressPercent}
            batchCounter={batchCounter}
          />
        ) : null}
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="min-tap sm:min-tap-0 mt-1 text-[12px] active:scale-95 sm:h-7 sm:text-[11px]"
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
        <p className="text-[11px] text-amber-600 dark:text-amber-300">
          {error}
        </p>
      ) : null}
    </div>
  );
}

/**
 * UploadProgress — tunn 0-100 % bar under "Laddar upp och analyserar…".
 *
 * Två rader:
 *   1. "47 %" + "(3 av 12)" — siffror för operatören som vill
 *      verifiera att något händer.
 *   2. <div role="progressbar"> med animerad fyllning. Width
 *      transitioneras med 150ms ease-out så bytes-events känns
 *      smooth utan att ligga efter den faktiska uppladdningen.
 *
 * Reduced-motion respekteras automatiskt: Tailwind-class
 * ``motion-reduce:transition-none`` stänger av easing där.
 *
 * Komponenten är intern i denna fil (inte exporterad) eftersom
 * den bara används av AssetDropzone idag.
 */
function UploadProgress({
  percent,
  batchCounter,
}: {
  percent: number;
  batchCounter: { current: number; total: number } | null;
}) {
  // Klamp till heltal vid render — float-procent ser jittrigt ut
  // och fyller ingen funktion när bytes-events ändå firar
  // diskret. ARIA-värdet rapporterar exakt floatvärdet via
  // aria-valuenow så assistive tech får bättre granularitet.
  const visiblePercent = Math.max(0, Math.min(100, Math.round(percent)));
  const widthStyle = `${Math.max(0, Math.min(100, percent))}%`;
  return (
    <div
      className="mt-2 flex w-full max-w-[28rem] flex-col gap-1.5"
      aria-live="polite"
    >
      <div className="flex items-baseline justify-between gap-2 text-[11px] tabular-nums">
        <span className="text-foreground/80 font-medium">
          {visiblePercent} %
        </span>
        {batchCounter ? (
          <span className="text-muted-foreground/80">
            {batchCounter.current} av {batchCounter.total}
          </span>
        ) : null}
      </div>
      <div
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent}
        aria-label="Uppladdningsförlopp"
        className="bg-foreground/10 relative h-1.5 w-full overflow-hidden rounded-full"
      >
        <div
          className="bg-foreground h-full rounded-full transition-[width] duration-150 ease-out motion-reduce:transition-none"
          style={{ width: widthStyle }}
        />
      </div>
    </div>
  );
}
