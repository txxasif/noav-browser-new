// Cloudflare Email Worker + HTTP API for the mailcf catch-all domain.
//
// Bindings:  OTP_STORE (KV namespace)
// Secrets:   ADMIN_TOKEN  (wrangler secret put ADMIN_TOKEN)
//
// Endpoints:
//   GET  /?email=<addr>                 latest OTP code (public, 15 min) — used by the creator
//   POST /register   {email, token}     store the read token for an address (admin bearer auth)
//   GET  /messages?email=<addr>&token=  stored messages for an address (token required)
//   POST /retire     {email}            kill an address: wipe its token/codes/messages, reject future mail

const OTP_TTL = 900;             // latest code: 15 minutes
const MSG_TTL = 15 * 24 * 3600;  // full messages: 15 days
const MAX_BODY = 20000;          // characters kept per message
const MAX_MESSAGES = 1000;       // cap per /messages call
const DEAD_TTL = MSG_TTL;        // retired addresses stay dead this long

const JSON_HEADERS = { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" };
const json = (body, status = 200) => new Response(JSON.stringify(body), { status, headers: JSON_HEADERS });

const CODE_HEADER = /^\s*(\d{6,8})\b[^\n]*\b(code|confirm|verification)/i;
const CODE_PHRASE = /(?:confirmation code|security code|verification code|is your code|code is)\s*:?\s*(\d{6,8})\b/i;

// Meta sends quoted-printable bodies: "Confirma=\r\ntion code" and "=3D" must be decoded first.
function decodeQuotedPrintable(s) {
  return s
    .replace(/=\r?\n/g, "")
    .replace(/=([0-9A-F]{2})/gi, (_, hex) => String.fromCharCode(parseInt(hex, 16)));
}

function toText(raw) {
  return decodeQuotedPrintable(raw)
    .replace(/<style[\s\S]*?<\/style>/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/gi, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function extractCode(subject, rawEmail) {
  const fromSubject = subject.match(CODE_HEADER);
  if (fromSubject) return fromSubject[1];
  const fromBody = toText(rawEmail).match(CODE_PHRASE);
  return fromBody ? fromBody[1] : null;
}

async function latestCode(url, env) {
  const email = (url.searchParams.get("email") || "").toLowerCase().trim();
  if (!email) return json({ error: "Missing email parameter" }, 400);
  const stored = await env.OTP_STORE.get(`otp:${email}`);
  return stored ? new Response(stored, { headers: JSON_HEADERS }) : json({ code: null, status: "waiting" });
}

function isAdmin(request, env) {
  return Boolean(env.ADMIN_TOKEN) && request.headers.get("Authorization") === `Bearer ${env.ADMIN_TOKEN}`;
}

async function register(request, env) {
  if (!isAdmin(request, env)) return json({ error: "Unauthorized" }, 401);
  const body = await request.json().catch(() => null);
  const email = String(body?.email || "").toLowerCase().trim();
  const token = String(body?.token || "");
  if (!email || token.length < 16) return json({ error: "email and token (16+ chars) required" }, 400);
  if (await env.OTP_STORE.get(`dead:${email}`)) return json({ error: "Address is retired" }, 409);
  await env.OTP_STORE.put(`tok:${email}`, token);
  return json({ ok: true });
}

// Kill an address after its task: forget the token, delete stored codes and mail,
// and reject anything that arrives later.
async function retire(request, env) {
  if (!isAdmin(request, env)) return json({ error: "Unauthorized" }, 401);
  const body = await request.json().catch(() => null);
  const email = String(body?.email || "").toLowerCase().trim();
  if (!email) return json({ error: "email required" }, 400);

  await env.OTP_STORE.put(`dead:${email}`, "1", { expirationTtl: DEAD_TTL });
  await env.OTP_STORE.delete(`tok:${email}`);
  await env.OTP_STORE.delete(`otp:${email}`);

  let deleted = 0;
  let cursor;
  do {
    const page = await env.OTP_STORE.list({ prefix: `msg:${email}:`, cursor });
    for (const k of page.keys) {
      await env.OTP_STORE.delete(k.name);
      deleted++;
    }
    cursor = page.list_complete ? undefined : page.cursor;
  } while (cursor);
  return json({ ok: true, email, deleted });
}

async function listMessages(url, env) {
  const email = (url.searchParams.get("email") || "").toLowerCase().trim();
  const token = url.searchParams.get("token") || "";
  if (!email || !token) return json({ error: "email and token required" }, 400);

  const stored = await env.OTP_STORE.get(`tok:${email}`);
  if (!stored || stored !== token) return json({ error: "Forbidden" }, 403);

  // Collect message keys (paged), then load them.
  const prefix = `msg:${email}:`;
  const keys = [];
  let cursor;
  do {
    const page = await env.OTP_STORE.list({ prefix, cursor });
    keys.push(...page.keys.map((k) => k.name));
    cursor = page.list_complete ? undefined : page.cursor;
  } while (cursor && keys.length < MAX_MESSAGES);

  const messages = [];
  for (const key of keys.slice(0, MAX_MESSAGES)) {
    const raw = await env.OTP_STORE.get(key);
    if (raw) messages.push(JSON.parse(raw));
  }
  messages.sort((a, b) => b.timestamp - a.timestamp); // newest first
  return json({ email, count: messages.length, messages });
}

export default {
  async email(message, env) {
    const recipient = message.to.toLowerCase().trim();
    if (await env.OTP_STORE.get(`dead:${recipient}`)) return; // retired address: drop the mail

    const subject = message.headers.get("subject") || "";
    const rawEmail = await new Response(message.raw).text();
    const timestamp = Date.now();
    const code = extractCode(subject, rawEmail);

    // Latest code, for the creator's OTP polling.
    if (code) {
      await env.OTP_STORE.put(
        `otp:${recipient}`,
        JSON.stringify({ email: recipient, code, subject, timestamp }),
        { expirationTtl: OTP_TTL }
      );
    }

    // Full message, kept for later reads. Zero-padded timestamp keeps keys sortable.
    const key = `msg:${recipient}:${String(timestamp).padStart(13, "0")}:${crypto.randomUUID().slice(0, 8)}`;
    await env.OTP_STORE.put(
      key,
      JSON.stringify({ from: message.from, subject, timestamp, code, text: toText(rawEmail).slice(0, MAX_BODY) }),
      { expirationTtl: MSG_TTL }
    );
  },

  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method === "POST" && url.pathname === "/register") return register(request, env);
    if (request.method === "POST" && url.pathname === "/retire") return retire(request, env);
    if (request.method === "GET" && url.pathname === "/messages") return listMessages(url, env);
    if (request.method === "GET" && url.pathname === "/") return latestCode(url, env);
    return json({ error: "Not found" }, 404);
  },
};
