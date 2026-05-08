import { NextResponse, type NextRequest } from "next/server";
import { Resend } from "resend";

interface ContactPayload {
  name?: unknown;
  email?: unknown;
  subject?: unknown;
  message?: unknown;
}

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function asTrimmedString(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

export async function POST(request: NextRequest) {
  const apiKey = process.env.RESEND_API_KEY;
  const from = process.env.EMAIL_FROM;
  const to = process.env.CONTACT_EMAIL_TO;

  if (!apiKey || !from || !to) {
    return NextResponse.json(
      { ok: false, error: "email-not-configured" },
      { status: 503 },
    );
  }

  let payload: ContactPayload;
  try {
    payload = (await request.json()) as ContactPayload;
  } catch {
    return NextResponse.json({ ok: false, error: "invalid-json" }, { status: 400 });
  }

  const name = asTrimmedString(payload.name);
  const email = asTrimmedString(payload.email);
  const subject = asTrimmedString(payload.subject) || "Contact form submission";
  const message = asTrimmedString(payload.message);

  if (!name || !email || !message) {
    return NextResponse.json(
      { ok: false, error: "missing-required-fields" },
      { status: 422 },
    );
  }
  if (!EMAIL_RE.test(email)) {
    return NextResponse.json(
      { ok: false, error: "invalid-email" },
      { status: 422 },
    );
  }
  if (message.length > 5000) {
    return NextResponse.json(
      { ok: false, error: "message-too-long" },
      { status: 422 },
    );
  }

  const resend = new Resend(apiKey);

  try {
    const result = await resend.emails.send({
      from,
      to,
      replyTo: email,
      subject,
      text: `From: ${name} <${email}>\n\n${message}`,
    });
    if ("error" in result && result.error) {
      console.error("[contact] Resend error", result.error);
      return NextResponse.json(
        { ok: false, error: "send-failed" },
        { status: 502 },
      );
    }
    return NextResponse.json({ ok: true });
  } catch (err) {
    console.error("[contact] Unexpected error", err);
    return NextResponse.json(
      { ok: false, error: "send-failed" },
      { status: 502 },
    );
  }
}
