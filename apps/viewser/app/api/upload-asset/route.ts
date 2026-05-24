import { NextRequest, NextResponse } from "next/server";

import { getAssetStore } from "@/lib/asset-store";
import type {
  AssetMimeType,
  AssetRole,
  VideoMimeType,
} from "@/lib/asset-store/types";
import { assertLocalhost } from "@/lib/localhost-guard";

/**
 * POST /api/upload-asset — operatör laddar upp en bild eller video
 * från discovery-wizardens MediaStep.
 *
 * multipart/form-data fält:
 *   - file:    Blob (image: png|jpeg|webp|svg+xml — video: mp4|webm)
 *   - role:    "logo" | "hero" | "gallery" | "favicon" | "ogImage" | "backgroundVideo"
 *   - siteId:  valfri; om utelämnad används "__draft" och build flyttar
 *              filen till rätt mapp vid copy_operator_uploads
 *
 * Returnerar `{ ok: true, ref: AssetRef }` eller `{ ok: false, error }`.
 *
 * Pipeline (image): sharp-komprimering → GPT Vision-klassificering →
 * manifest.json. Pipeline (video): direkt-skrivning utan sharp/vision.
 * Hela kedjan körs i LocalAssetStore.save() eller VercelBlobAssetStore.save().
 *
 * Localhost-only.
 */

export const runtime = "nodejs";

const ALLOWED_IMAGE_MIMES = new Set([
  "image/png",
  "image/jpeg",
  "image/webp",
  "image/svg+xml",
]);
const ALLOWED_VIDEO_MIMES = new Set<VideoMimeType>(["video/mp4", "video/webm"]);
// Video tillåts vara större än bilder — typiska hero-loops är 2–8 MB även
// efter kompression. 50 MB är hårda gränsen så att payload-parsern inte
// behöver buffra orimligt mycket; reella videos bör vara under 10 MB för
// att inte tynga LCP på den genererade sajten.
const MAX_IMAGE_BYTES = 10 * 1024 * 1024;
const MAX_VIDEO_BYTES = 50 * 1024 * 1024;
// W7 i scout-review 2026-05-24: build_site.py:s ``copy_operator_uploads``
// fetchar blob-hostade videos via ``ref.sourceUrl`` med en hard cap på
// 8 MB (``_REMOTE_ASSET_MAX_BYTES``). Videos mellan 8-50 MB skulle
// laddas upp framgångsrikt men sedan tyst skippas vid build — den
// genererade sajten får en trasig eller saknad hero-video. När
// driver är blob klampar vi därför video-gränsen till samma 8 MB.
const MAX_VIDEO_BYTES_BLOB = 8 * 1024 * 1024;
const ALLOWED_ROLES = new Set<AssetRole>([
  "logo",
  "hero",
  "gallery",
  "favicon",
  "ogImage",
  "backgroundVideo",
]);
const SITE_ID_PATTERN = /^[a-z0-9_-]{1,64}$/i;

function badRequest(message: string): NextResponse {
  return NextResponse.json({ ok: false, error: message }, { status: 400 });
}

export async function POST(request: NextRequest) {
  const guard = assertLocalhost(request);
  if (guard) return guard;

  // Early payload-size guard: reject oversize uploads BEFORE awaiting
  // request.formData(), which would otherwise buffer the entire payload
  // in memory just to discover it is too large. Vi guardar mot
  // worst-case (video × 2 för multipart-overhead). Per-file-storlek
  // valideras mot rätt limit (image vs video) längre ner när mime är
  // känt.
  const contentLength = request.headers.get("content-length");
  if (contentLength) {
    const declared = Number.parseInt(contentLength, 10);
    if (Number.isFinite(declared) && declared > MAX_VIDEO_BYTES * 2) {
      return badRequest(
        `Payload är ${(declared / 1024 / 1024).toFixed(1)} MB; max är 50 MB för video, 10 MB för bild ` +
          `(${((MAX_VIDEO_BYTES * 2) / 1024 / 1024).toFixed(0)} MB inklusive multipart-overhead).`,
      );
    }
  }

  let form: FormData;
  try {
    form = await request.formData();
  } catch (caught) {
    const message =
      caught instanceof Error
        ? caught.message
        : "Kunde inte parsa multipart-payloaden.";
    return badRequest(`Ogiltig multipart-payload: ${message}`);
  }

  const file = form.get("file");
  if (!(file instanceof Blob)) {
    return badRequest("Fält 'file' saknas eller är inte en Blob.");
  }

  const roleRaw = form.get("role");
  const role = typeof roleRaw === "string" ? (roleRaw as AssetRole) : null;
  if (!role || !ALLOWED_ROLES.has(role)) {
    return badRequest(
      "Fält 'role' måste vara logo, hero, gallery, favicon, ogImage eller backgroundVideo.",
    );
  }

  const siteIdRaw = form.get("siteId");
  const siteId =
    typeof siteIdRaw === "string" && siteIdRaw.trim()
      ? siteIdRaw.trim()
      : "__draft";
  if (!SITE_ID_PATTERN.test(siteId)) {
    return badRequest(
      "Fält 'siteId' måste matcha [a-z0-9_-]{1,64} eller utelämnas.",
    );
  }

  const mime = (file.type || "").toLowerCase();
  const isVideo = ALLOWED_VIDEO_MIMES.has(mime as VideoMimeType);
  const isImage = ALLOWED_IMAGE_MIMES.has(mime);
  if (!isVideo && !isImage) {
    return badRequest(
      `Filtyp ${mime || "okänd"} är inte tillåten. ` +
        `Tillåtna: PNG, JPEG, WebP, SVG, MP4, WebM.`,
    );
  }

  // Role × mime cross-check: backgroundVideo måste vara video, övriga
  // roles måste vara image. Detta förhindrar att operatören laddar upp
  // en .mp4 som "logo" (vilket skulle krascha sharp downstream) eller
  // en .png som "backgroundVideo" (vilket skulle ge ett tomt <video>-
  // element vid render).
  if (role === "backgroundVideo" && !isVideo) {
    return badRequest(
      "Rollen 'backgroundVideo' kräver en video-fil (MP4 eller WebM).",
    );
  }
  if (role !== "backgroundVideo" && isVideo) {
    return badRequest(
      `Rollen '${role}' kräver en bild-fil. Endast 'backgroundVideo' accepterar video.`,
    );
  }

  // W7: när blob är aktiv driver är effektiv video-gräns 8 MB
  // eftersom build:en fetchar via ref.sourceUrl och har den capen.
  // Vi vill inte att operatören laddar upp 30 MB video som sedan
  // tyst skippas — bättre att blockera direkt med tydligt felmeddelande.
  const driver = (process.env.ASSET_STORE_DRIVER || "local").toLowerCase();
  const effectiveVideoMax =
    driver === "vercel-blob" ? MAX_VIDEO_BYTES_BLOB : MAX_VIDEO_BYTES;
  const maxBytes = isVideo ? effectiveVideoMax : MAX_IMAGE_BYTES;
  if (file.size > maxBytes) {
    const kind = isVideo ? "video" : "bild";
    const note =
      isVideo && driver === "vercel-blob"
        ? " (8 MB-cap på blob-driver — build:en fetchar via sourceUrl)"
        : "";
    return badRequest(
      `Filen är ${(file.size / 1024 / 1024).toFixed(1)} MB; max är ${(maxBytes / 1024 / 1024).toFixed(0)} MB för ${kind}${note}.`,
    );
  }

  const originalName =
    typeof (file as File).name === "string" && (file as File).name
      ? (file as File).name
      : "upload";

  const arrayBuf = await file.arrayBuffer();
  const buffer = Buffer.from(arrayBuf);

  try {
    const store = getAssetStore();
    const result = await store.save({
      siteId,
      buffer,
      originalName,
      mimeType: mime as AssetMimeType,
      role,
    });
    return NextResponse.json(
      { ok: true, ref: result.ref, variant: result.variant },
      { status: 200 },
    );
  } catch (caught) {
    const message =
      caught instanceof Error ? caught.message : "Okänt fel vid asset-spar.";
    console.error("[/api/upload-asset] save misslyckades:", caught);
    return NextResponse.json({ ok: false, error: message }, { status: 500 });
  }
}
