import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";

import { chatWithOpenAi } from "@/lib/openai";

const ChatMessageSchema = z.object({
  role: z.enum(["system", "user", "assistant"]),
  content: z.string().min(1),
});

const ChatPayloadSchema = z.object({
  messages: z.array(ChatMessageSchema).min(1),
});

export async function POST(request: NextRequest) {
  try {
    const payload = ChatPayloadSchema.parse(await request.json());
    const result = await chatWithOpenAi(payload.messages);
    return NextResponse.json(result);
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Okänt fel vid chat-anropet.";
    return NextResponse.json({ error: message }, { status: 400 });
  }
}
