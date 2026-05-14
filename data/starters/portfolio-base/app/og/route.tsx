import { ImageResponse } from "next/og";

export function GET(request: Request) {
  const url = new URL(request.url);
  const title = url.searchParams.get("title") ?? "";

  return new ImageResponse(
    <div tw="flex h-full w-full items-center justify-center bg-background text-foreground">
      <div tw="flex w-full flex-col p-12">
        <h1 tw="text-5xl font-bold tracking-tight">{title}</h1>
      </div>
    </div>,
    {
      width: 1200,
      height: 630,
    },
  );
}
