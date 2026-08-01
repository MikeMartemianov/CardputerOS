// Cloudflare Worker — YouTube Proxy for CardputerOS
// Deploy at: https://workers.dev
// Usage: https://your-worker.workers.dev/search?q=query
//        https://your-worker.workers.dev/streams?v=VIDEO_ID
//        https://your-worker.workers.dev/thumb?url=THUMBNAIL_URL

const PIPED_INSTANCES = [
  "https://api.piped.private.coffee",
  "https://pipedapi.adminforge.de",
];

async function fetchWithFallback(path) {
  for (const instance of PIPED_INSTANCES) {
    try {
      const res = await fetch(`${instance}${path}`, {
        headers: { "Accept": "application/json" },
        signal: AbortSignal.timeout(8000),
      });
      if (res.ok) return res;
    } catch (e) {
      continue;
    }
  }
  return new Response(JSON.stringify({ error: "All instances failed" }), { status: 502 });
}

async function handleSearch(url) {
  const q = url.searchParams.get("q");
  if (!q) return new Response(JSON.stringify({ error: "Missing ?q=" }), { status: 400 });
  const res = await fetchWithFallback(`/search?q=${encodeURIComponent(q)}&filter=videos`);
  const data = await res.json();
  
  // Return only what ESP32 needs (save bandwidth)
  const items = (data.items || []).slice(0, 20).map(item => ({
    id: (item.url || "").replace("/watch?v=", ""),
    title: (item.title || "").substring(0, 64),
    channel: (item.uploaderName || "").substring(0, 32),
    thumb: item.thumbnail || "",
    duration: item.duration || 0,
    views: item.views || 0,
  }));
  
  return new Response(JSON.stringify({ items }), {
    headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
  });
}

async function handleStreams(url) {
  const v = url.searchParams.get("v");
  if (!v) return new Response(JSON.stringify({ error: "Missing ?v=" }), { status: 400 });
  const res = await fetchWithFallback(`/streams/${v}`);
  const data = await res.json();
  
  // Extract only what ESP32 needs
  const audioStreams = (data.audioStreams || []).map(s => ({
    url: s.url, bitrate: s.bitrate, mimeType: s.mimeType, codec: s.codec,
  }));
  const videoStreams = (data.videoStreams || []).filter(s => !s.videoOnly).map(s => ({
    url: s.url, quality: s.quality, mimeType: s.mimeType,
  }));
  const storyboards = (data.previewFrames || []).map(pf => ({
    urls: pf.urls, frameWidth: pf.frameWidth, frameHeight: pf.frameHeight,
    totalCount: pf.totalCount, durationPerFrame: pf.durationPerFrame,
    framesPerPageX: pf.framesPerPageX, framesPerPageY: pf.framesPerPageY,
  }));
  
  return new Response(JSON.stringify({
    title: data.title, duration: data.duration, views: data.views,
    thumbnailUrl: data.thumbnailUrl,
    audioStreams, videoStreams, storyboards,
  }), {
    headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
  });
}

async function handleThumb(url) {
  const thumbUrl = url.searchParams.get("url");
  if (!thumbUrl) return new Response("Missing ?url=", { status: 400 });
  
  try {
    const res = await fetch(thumbUrl, { signal: AbortSignal.timeout(5000) });
    const contentType = res.headers.get("content-type") || "image/jpeg";
    return new Response(res.body, {
      headers: {
        "Content-Type": contentType,
        "Access-Control-Allow-Origin": "*",
        "Cache-Control": "public, max-age=86400",
      },
    });
  } catch (e) {
    return new Response("Thumbnail fetch failed", { status: 502 });
  }
}

export default {
  async fetch(request) {
    const url = new URL(request.url);
    
    // CORS preflight
    if (request.method === "OPTIONS") {
      return new Response(null, {
        headers: { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "GET" },
      });
    }
    
    const path = url.pathname;
    if (path === "/search") return handleSearch(url);
    if (path === "/streams") return handleStreams(url);
    if (path === "/thumb") return handleThumb(url);
    
    return new Response(JSON.stringify({
      service: "CardputerOS YouTube Proxy",
      endpoints: ["/search?q=...", "/streams?v=...", "/thumb?url=..."],
    }), {
      headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
    });
  },
};
