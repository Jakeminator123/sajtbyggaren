import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";

import { chatWithOpenAi } from "@/lib/openai";
import { assertLocalhost } from "@/lib/localhost-guard";

const ChatMessageSchema = z.object({
  role: z.enum(["system", "user", "assistant"]),
  content: z.string().min(1).max(8000),
});

const ChatPayloadSchema = z.object({
  messages: z.array(ChatMessageSchema).min(1).max(40),
});

export async function POST(request: NextRequest) {
  const guard = assertLocalhost(request);
  if (guard) return guard;

  let payload: z.infer<typeof ChatPayloadSchema>;
  try {
    payload = ChatPayloadSchema.parse(await request.json());
  } catch (error) {
    const message = error instanceof Error ? error.message : "Ogiltig payload.";
    return NextResponse.json({ error: message }, { status: 400 });
  }

  try {
    const result = await chatWithOpenAi(payload.messages);
    return NextResponse.json(result);
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Okänt fel vid chat-anropet.";
    return NextResponse.json({ error: message }, { status: 502 });
  }
}
