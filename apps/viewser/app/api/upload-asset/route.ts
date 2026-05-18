import { NextRequest, NextResponse } from "next/server";

import { getAssetStore } from "@/lib/asset-store";
import type { AssetRole } from "@/lib/asset-store/types";
import { assertLocalhost } from "@/lib/localhost-guard";

/**
 * POST /api/upload-asset — operatör laddar upp en bild från
 * discovery-wizardens AssetsStep.
 *
 * multipart/form-data fält:
 *   - file:    Blob (image/png|jpeg|webp|svg+xml)
 *   - role:    "logo" | "hero" | "gallery"
 *   - siteId:  valfri; om utelämnad används "__draft" och build flyttar
 *              filen till rätt mapp vid copy_operator_uploads
 *
 * Returnerar `{ ok: true, ref: AssetRef }` eller `{ ok: false, error }`.
 *
 * Pipeline: sharp-komprimering → GPT Vision-klassificering →
 * manifest.json. Hela kedjan körs i LocalAssetStore.save().
 *
 * Localhost-only.
 */

export const runtime = "nodejs";

const ALLOWED_MIMES = new Set([
  "image/png",
  "image/jpeg",
  "image/webp",
  "image/svg+xml",
]);
const MAX_FILE_BYTES = 10 * 1024 * 1024; // 10 MB rå
const ALLOWED_ROLES = new Set<AssetRole>(["logo", "hero", "gallery"]);
const SITE_ID_PATTERN = /^[a-z0-9_-]{1,64}$/i;

function badRequest(message: string): NextResponse {
  return NextResponse.json({ ok: false, error: message }, { status: 400 });
}

export async function POST(request: NextRequest) {
  const guard = assertLocalhost(request);
  if (guard) return guard;

  // Early payload-size guard: reject oversize uploads BEFORE awaiting
  // request.formData(), which would otherwise buffer the entire payload
  // in memory just to discover it is too large. We allow some multipart
  // overhead (~2x MAX_FILE_BYTES headroom for boundaries + extra form
  // fields like role/siteId) so well-formed uploads near the limit are
  // not rejected on the Content-Length check alone. The exact per-file
  // size is still enforced below on file.size.
  const contentLength = request.headers.get("content-length");
  if (contentLength) {
    const declared = Number.parseInt(contentLength, 10);
    if (Number.isFinite(declared) && declared > MAX_FILE_BYTES * 2) {
      return badRequest(
        `Payload är ${(declared / 1024 / 1024).toFixed(1)} MB; max är 10 MB per fil ` +
          `(${((MAX_FILE_BYTES * 2) / 1024 / 1024).toFixed(0)} MB inklusive multipart-overhead).`,
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
    return badRequest("Fält 'role' måste vara logo, hero eller gallery.");
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
  if (!ALLOWED_MIMES.has(mime)) {
    return badRequest(
      `Filtyp ${mime || "okänd"} är inte tillåten. Tillåtna: PNG, JPEG, WebP, SVG.`,
    );
  }

  if (file.size > MAX_FILE_BYTES) {
    return badRequest(
      `Filen är ${(file.size / 1024 / 1024).toFixed(1)} MB; max är 10 MB.`,
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
      mimeType: mime as
        | "image/png"
        | "image/jpeg"
        | "image/webp"
        | "image/svg+xml",
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
