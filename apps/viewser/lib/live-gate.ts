import { NextResponse } from "next/server";

/**
 * Gate för de hostade /api/live/*-routerna. De är AVSIKTLIGT inte
 * localhost-låsta (måste funka hostat), så vi vill ändå kunna stänga av
 * dem enkelt. ``VIEWSER_ENABLE_LIVE=1`` slår på funktionen; allt annat
 * (osatt/``0``) gör att routerna svarar 404 — operatörens "släck ned
 * efteråt"-strömbrytare.
 */
export function liveDisabled(): NextResponse | null {
  if (process.env.VIEWSER_ENABLE_LIVE !== "1") {
    return NextResponse.json(
      {
        error:
          "Live-läget är avstängt. Sätt VIEWSER_ENABLE_LIVE=1 i miljön för att aktivera.",
        code: "live_disabled",
      },
      { status: 404 },
    );
  }
  return null;
}
