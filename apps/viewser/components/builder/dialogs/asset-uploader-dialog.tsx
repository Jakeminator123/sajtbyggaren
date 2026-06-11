"use client";

import {
  Crown,
  ImageIcon,
  ImagePlus,
  Loader2,
  Mountain,
  MousePointerClick,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  useFollowupBuild,
  type FollowupToolIntent,
  type OnFollowupBuildDone,
} from "@/components/builder/use-followup-build";
import { usePreviewInspector } from "@/components/preview-inspector-context";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { AssetRef, AssetRole } from "@/lib/asset-store/types";
import { cn } from "@/lib/utils";

/**
 * Asset-uppladdare med explicit roll-val. Komplement till paperclip-
 * knappen i FloatingChat (som alltid sätter role=gallery). Den här
 * dialogen är för "jag vill byta logon" eller "jag vill ha den här
 * bilden som hero" — fall där paperclip:s gallery-default är fel.
 *
 * Flöde:
 *   1. Operatören väljer en fil + roll (logo / hero / galleri).
 *   2. Vi POST:ar till `/api/upload-asset` med rollen och siteId
 *      → backenden lagrar den under aktuell sajt.
 *   3. Operatören får valfritt beskriva placering ("ska ligga på
 *      tjänster-sidan", "byt ut huvudbilden") — ELLER dra bilden till
 *      en plats i förhandsvisningen ("Dra till plats i previewn"):
 *      en thumbnail-ghost följer pekaren över previewn, "Placera här"
 *      bekräftar och bygget startar direkt med platskontexten
 *      ("efter Omdömen", högt upp/långt ner) i instruktionen.
 *   4. Vi skickar en följdprompt som refererar till asset:en så
 *      build-pipelinen vet att den ska användas och var.
 */

const ROLE_OPTIONS: ReadonlyArray<{
  value: AssetRole;
  label: string;
  description: string;
  Icon: typeof Crown;
}> = [
  {
    value: "logo",
    label: "Logotyp",
    description: "Visas i header och footer.",
    Icon: Crown,
  },
  {
    value: "hero",
    label: "Huvudbild",
    description: "Stor bild på startsidan.",
    Icon: Mountain,
  },
  {
    value: "gallery",
    label: "Galleri",
    description: "Läggs i bildbanken — placera fritt.",
    Icon: ImageIcon,
  },
];

const ALLOWED_UPLOAD_MIMES = new Set([
  "image/png",
  "image/jpeg",
  "image/webp",
  "image/svg+xml",
]);
const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;

type AssetUploaderDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  siteId: string;
  onBuildStart: () => void;
  onBuildEnd: () => void;
  onBuildDone: OnFollowupBuildDone;
  /** C2 globalt bygg-lås + C1 "Iterera från denna"-pin (från BuilderShell). */
  isBuilding?: boolean;
  baseRunId?: string | null;
  /**
   * Initial sektionskontext från sektionsmenyn i previewn ("Byt bild
   * här"): förifyller önskemåls-fältet med en placerings-hint
   * ('Bilden gäller sektionen "…"'). Null/utelämnad → oförändrat
   * beteende. Fylls bara i när fältet är tomt — operatörens egen text
   * skrivs aldrig över.
   */
  initialHint?: string | null;
};

export function AssetUploaderDialog({
  open,
  onOpenChange,
  siteId,
  onBuildStart,
  onBuildEnd,
  onBuildDone,
  isBuilding = false,
  baseRunId = null,
  initialHint = null,
}: AssetUploaderDialogProps) {
  const [role, setRole] = useState<AssetRole>("hero");
  const [file, setFile] = useState<File | null>(null);
  const [uploadedRef, setUploadedRef] = useState<AssetRef | null>(null);
  const [hint, setHint] = useState("");
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const {
    runFollowup,
    isBusy,
    error: buildError,
  } = useFollowupBuild({
    siteId,
    onBuildStart,
    onBuildEnd,
    onBuildDone,
    isBuilding,
    baseRunId,
  });

  const reset = useCallback(() => {
    setFile(null);
    setUploadedRef(null);
    setHint("");
    setUploadError(null);
  }, []);

  // Förifyll önskemåls-fältet med sektionsmenyns hint när dialogen
  // öppnas med en sektionskontext. setTimeout(0) deferar setState:n ur
  // effektkroppen (react-hooks/set-state-in-effect); funktions-settern
  // garanterar att en redan skriven operatörstext aldrig skrivs över.
  useEffect(() => {
    if (!open || !initialHint) return;
    const timerId = window.setTimeout(() => {
      setHint((current) => (current.trim() ? current : initialHint));
    }, 0);
    return () => window.clearTimeout(timerId);
  }, [open, initialHint]);

  const handleClose = useCallback(
    (next: boolean) => {
      if (next === false) reset();
      onOpenChange(next);
    },
    [onOpenChange, reset],
  );

  const handleFileChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const picked = event.target.files?.[0] ?? null;
      event.target.value = "";
      if (!picked) return;
      if (!ALLOWED_UPLOAD_MIMES.has(picked.type)) {
        setUploadError("Endast PNG, JPEG, WebP eller SVG tillåts.");
        return;
      }
      if (picked.size > MAX_UPLOAD_BYTES) {
        setUploadError(
          `Filen är ${(picked.size / 1024 / 1024).toFixed(1)} MB — max är 10 MB.`,
        );
        return;
      }
      setFile(picked);
      setUploadedRef(null);
      setUploadError(null);
    },
    [],
  );

  const handleUpload = useCallback(async () => {
    if (!file || isUploading) return;
    setIsUploading(true);
    setUploadError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("role", role);
      form.append("siteId", siteId);
      const response = await fetch("/api/upload-asset", {
        method: "POST",
        body: form,
      });
      const payload = (await response.json()) as {
        ok?: boolean;
        ref?: AssetRef;
        error?: string;
      };
      if (!response.ok || !payload.ok || !payload.ref) {
        throw new Error(payload.error ?? "Uppladdningen misslyckades.");
      }
      setUploadedRef(payload.ref);
    } catch (caught) {
      setUploadError(caught instanceof Error ? caught.message : "Okänt fel.");
    } finally {
      setIsUploading(false);
    }
  }, [file, isUploading, role, siteId]);

  const applyAsset = useCallback(
    async (placementHint?: string) => {
      if (!uploadedRef) return;
      const roleSentence = (() => {
        switch (uploadedRef.role) {
          case "logo":
            return "Använd den uppladdade bilden som ny logotyp i header och footer.";
          case "hero":
            return "Använd den uppladdade bilden som ny huvudbild (hero) på startsidan.";
          case "gallery":
          default:
            return "Lägg in den uppladdade bilden i sajtens bildbank.";
        }
      })();
      // Drag-flödets platskontext slås ihop med operatörens egna
      // önskemål — båda är fritext som LLM-steget förstår.
      const trimmedHint = [hint.trim(), placementHint?.trim()]
        .filter(Boolean)
        .join(" ");
      const promptParts = [
        roleSentence,
        `Referens: assetId=${uploadedRef.assetId}, filename=${uploadedRef.filename}, alt="${uploadedRef.alt ?? ""}".`,
        trimmedHint ? `Önskemål: ${trimmedHint}` : null,
      ].filter(Boolean);
      // Strukturerad intent (specialist-dispatch steg 2): roll + assetId
      // är exakta — backend slipper regex:a fram referensraden ur prompten.
      // hint-fritexten följer med strukturerat; den kan kräva copy-
      // specialisten och är det enda LLM-värdiga i detta verktyg.
      // Task A (2026-06-11): hela AssetRef:en följer med så Python-
      // konsumenten kan bygga en schema-komplett ref utan disk-lookup
      // (blob-drivern har ingen lokal manifest.json att falla tillbaka på).
      const toolIntent: FollowupToolIntent = {
        tool: "asset_set",
        params: {
          role: uploadedRef.role,
          assetId: uploadedRef.assetId,
          filename: uploadedRef.filename,
          mimeType: uploadedRef.mimeType,
          sizeBytes: uploadedRef.sizeBytes,
          ...(uploadedRef.width ? { width: uploadedRef.width } : {}),
          ...(uploadedRef.height ? { height: uploadedRef.height } : {}),
          ...(uploadedRef.placement
            ? { placement: uploadedRef.placement }
            : {}),
          ...(uploadedRef.sourceUrl
            ? { sourceUrl: uploadedRef.sourceUrl }
            : {}),
          ...(uploadedRef.alt ? { alt: uploadedRef.alt } : {}),
          ...(trimmedHint ? { hint: trimmedHint } : {}),
        },
      };
      const result = await runFollowup(promptParts.join("\n"), { toolIntent });
      if (result.ok) {
        handleClose(false);
      }
    },
    [uploadedRef, hint, runFollowup, handleClose],
  );

  const handleApply = useCallback(() => {
    void applyAsset();
  }, [applyAsset]);

  // Dra-till-plats: ghost-thumbnail av bilden följer pekaren över
  // previewn (PreviewInspectorOverlay). Logotypen har fast placering
  // (header/footer) så drag-knappen visas bara för hero/galleri.
  const {
    previewUrl,
    requestPlacementPick,
    lastPlacementPick,
    clearPlacementPick,
    placementRequester,
  } = usePreviewInspector();
  // Object-URL för ghost-thumbnailen — frigörs efter picken (eller när
  // dialogen stängs helt) så vi inte läcker blob-minne.
  const dragThumbUrlRef = useRef<string | null>(null);
  const releaseDragThumb = useCallback(() => {
    if (dragThumbUrlRef.current) {
      URL.revokeObjectURL(dragThumbUrlRef.current);
      dragThumbUrlRef.current = null;
    }
  }, []);
  useEffect(() => releaseDragThumb, [releaseDragThumb]);

  const handleDragToPreview = useCallback(() => {
    if (!uploadedRef) return;
    releaseDragThumb();
    let thumbnailUrl = uploadedRef.sourceUrl;
    if (!thumbnailUrl && file) {
      thumbnailUrl = URL.createObjectURL(file);
      dragThumbUrlRef.current = thumbnailUrl;
    }
    requestPlacementPick({
      payload: {
        kind: "image",
        label: uploadedRef.filename,
        ...(thumbnailUrl ? { thumbnailUrl } : {}),
      },
      requester: "asset",
    });
    // OBS: onOpenChange direkt (inte handleClose) — uppladdningen och
    // hint-texten ska överleva medan dialogen är stängd under draget.
    onOpenChange(false);
  }, [uploadedRef, file, releaseDragThumb, requestPlacementPick, onOpenChange]);

  // Konsumera platsvalet ÄVEN när dialogen är stängd: "Placera här" är
  // operatörens bekräftelse → bygg direkt med platskontexten i
  // instruktionen. Dialogen återöppnas inte längre efter bekräftat
  // släpp (operatörskrav 2026-06-10 — BuilderShell visar 0–100-bannern
  // i stället); komponenten är fortfarande monterad och bygger
  // härifrån. Requester-gaten hindrar oss från att äta modul-dialogens
  // pick. Avbruten pick (Esc) sätter aldrig lastPlacementPick.
  useEffect(() => {
    if (!lastPlacementPick || placementRequester !== "asset") return;
    const timerId = window.setTimeout(() => {
      const { point, coarsePosition, sizePercent } = lastPlacementPick;
      clearPlacementPick();
      releaseDragThumb();
      // Plats + vald storlek från drag-mockupen — fritext som LLM-steget
      // förstår: var (sektion + högt/långt ner), vilken sida (startsidan)
      // och hur stor bilden ska vara (% av sidbredden).
      const placementHint =
        `Placera bilden ${point.label.toLowerCase()} på startsidan ` +
        `(${coarsePosition === "top" ? "högt upp" : "långt ner"}). ` +
        `Bilden ska vara ungefär ${sizePercent} % av sidbredden.`;
      void applyAsset(placementHint);
    }, 0);
    return () => window.clearTimeout(timerId);
  }, [
    lastPlacementPick,
    placementRequester,
    clearPlacementPick,
    releaseDragThumb,
    applyAsset,
  ]);

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[520px]">
        <DialogHeader>
          <DialogTitle>Ladda upp bild</DialogTitle>
          <DialogDescription>
            Välj en bild och hur den ska användas. Filen lagras i sajtens
            bildbank och refereras i nästa bygge.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-4">
          <div>
            <Label className="text-muted-foreground mb-2 block text-[11px] tracking-tight uppercase">
              Roll
            </Label>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {ROLE_OPTIONS.map((option) => {
                const isActive = role === option.value;
                const Icon = option.Icon;
                return (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => setRole(option.value)}
                    aria-pressed={isActive}
                    disabled={isUploading || isBusy}
                    className={cn(
                      "min-tap sm:min-tap-0 flex flex-col items-start gap-1 rounded-lg border px-3 py-3 text-left transition-colors active:scale-[0.98] sm:py-2.5",
                      "focus-visible:ring-ring/50 focus-visible:ring-2 focus-visible:outline-none",
                      "disabled:cursor-not-allowed disabled:opacity-50",
                      isActive
                        ? "border-foreground bg-muted/60"
                        : "border-border/60 hover:border-border hover:bg-muted/30",
                    )}
                  >
                    <Icon
                      className={cn(
                        "h-4 w-4",
                        isActive ? "text-foreground" : "text-muted-foreground",
                      )}
                      aria-hidden
                    />
                    <span className="text-foreground text-[12px] font-medium">
                      {option.label}
                    </span>
                    <span className="text-muted-foreground text-[10.5px] leading-snug">
                      {option.description}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          <div>
            <Label className="text-muted-foreground mb-2 block text-[11px] tracking-tight uppercase">
              Fil
            </Label>
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => fileInputRef.current?.click()}
                disabled={isUploading || isBusy}
              >
                <ImagePlus className="h-4 w-4" />
                {file ? "Byt fil" : "Välj fil"}
              </Button>
              <span className="text-muted-foreground min-w-0 truncate text-[11.5px]">
                {file ? file.name : "PNG, JPEG, WebP, SVG · max 10 MB"}
              </span>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/png,image/jpeg,image/webp,image/svg+xml"
                onChange={handleFileChange}
                className="hidden"
                aria-hidden
              />
            </div>
            {file && !uploadedRef ? (
              <Button
                type="button"
                onClick={handleUpload}
                disabled={isUploading || isBusy}
                className="mt-2 w-full"
              >
                {isUploading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Laddar upp…
                  </>
                ) : (
                  <>
                    <ImagePlus className="h-4 w-4" />
                    Ladda upp filen
                  </>
                )}
              </Button>
            ) : null}
            {uploadedRef ? (
              <p className="text-muted-foreground mt-2 inline-flex items-center gap-1.5 text-[11.5px]">
                <span className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-500" />
                Uppladdad: {uploadedRef.filename}
              </p>
            ) : null}
            {uploadError ? (
              <p
                role="alert"
                className="text-destructive mt-2 text-[11.5px] leading-snug"
              >
                {uploadError}
              </p>
            ) : null}
          </div>

          {uploadedRef ? (
            <div>
              <Label
                htmlFor="builder-asset-hint"
                className="text-muted-foreground mb-1.5 block text-[11px] tracking-tight uppercase"
              >
                Önskemål (valfritt)
              </Label>
              <Textarea
                id="builder-asset-hint"
                value={hint}
                onChange={(event) => setHint(event.target.value)}
                placeholder="Ex: 'ska beskäras kvadratiskt och ligga på About-sidan'"
                rows={2}
                maxLength={400}
                disabled={isBusy}
                className="min-h-[60px] resize-none text-base sm:text-[12.5px]"
              />
              {/* Dra-till-plats: bara för roller där platsen är fri
                  (logotypen sitter alltid i header/footer) och bara när
                  en server-nåbar preview-URL finns (StackBlitz saknar). */}
              {previewUrl && uploadedRef.role !== "logo" ? (
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={handleDragToPreview}
                    disabled={isBusy || isUploading}
                    className="border-border/60 hover:border-border text-foreground inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-[11px] transition disabled:opacity-50"
                  >
                    <MousePointerClick className="h-3.5 w-3.5" aria-hidden />
                    Dra till plats i previewn
                  </button>
                  <span className="text-muted-foreground/70 text-[10.5px]">
                    Bilden följer pekaren — bekräfta med ”Placera här” så
                    byggs den in direkt.
                  </span>
                </div>
              ) : null}
            </div>
          ) : null}
        </div>

        {buildError ? (
          <p
            role="alert"
            className="text-destructive bg-destructive/10 border-destructive/40 rounded-md border px-3 py-2 text-[12px]"
          >
            {buildError}
          </p>
        ) : null}

        <DialogFooter>
          <Button
            type="button"
            variant="ghost"
            onClick={() => handleClose(false)}
            disabled={isUploading || isBusy}
          >
            Avbryt
          </Button>
          <Button
            type="button"
            onClick={handleApply}
            disabled={!uploadedRef || isBusy || isUploading}
          >
            {isBusy ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Bygger…
              </>
            ) : (
              <>
                <ImagePlus className="h-4 w-4" />
                Använd bilden
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
