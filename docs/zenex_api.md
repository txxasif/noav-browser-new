# ZENEX Network Number Panel — API Reference (A–Z)

> Learned live 2026-10-15/16 against production with a real key. Base covers
> the 4 verified endpoints; nothing here is guessed — unverified panel-only
> actions are marked as such.

## 0. Base + auth

- Base URL: `https://api.zenexnetwork.com/v1`
- Broadcast sits on another host: `https://www.zenexnetwork.com/api/v1/global-broadcast`
- Every request is REST + JSON responses.
- Auth header on **every** call:
  ```
  mapikey: YOUR_ZENEX_KEY_HERE
  ```
- Key source: dashboard Profile Page → **API Access** section. Never put it in
  client-side code — call from backend only.
- No key → `{"success":false,"message":"Invalid API Key"}` (api host) or
  `{"meta":{"status":"error"},"message":"Access Denied: Missing or Invalid API Key. Server Protected by ZENEX Firewall."}` (www host).

## 1. Provision a virtual number

```
POST https://api.zenexnetwork.com/v1/getnum
Content-Type: application/json
mapikey: KEY
```

Body:

| Param        | Required | Type    | Description                                      |
| ------------ | -------- | ------- | ------------------------------------------------ |
| `range`      | Yes      | string  | Routing prefix, e.g. `"261385XXX"`, `"224655XXX"` |
| `is_national`| No       | boolean | `true` = local number formatting                 |
| `remove_plus`| No       | boolean | `true` = drop the leading `+`                    |

Success (HTTP 200):

```json
{
  "meta": {"status": "success", "code": 200},
  "data": {
    "copy": "+261385223034",
    "number": "+261385223034",
    "full_number": "261385223034",
    "country": "Madagascar",
    "iso": "Unknown",
    "operator": "TELMA",
    "status": "pending"
  }
}
```

Notes (verified live):
- Each call allocates a **new** number; `status` starts as `pending`.
- Provisioning consumes panel credit — don't loop it blindly.
- `iso` returns `"Unknown"` even on success; use `country` instead.

```bash
curl -X POST "https://api.zenexnetwork.com/v1/getnum" \
  -H "mapikey: KEY" -H "Content-Type: application/json" \
  -d '{"range":"261385XXX","is_national":false,"remove_plus":false}'
```

## 2. Fetch SMS / OTP payloads

```
GET https://api.zenexnetwork.com/v1/numsuccess/info
mapikey: KEY
```

Returns the inbox of **your active number queue**:

```json
{ "data": { "otps": [ { ... } ] } }
```

Each object in `data.otps`:

| Field                 | Description                                                        |
| --------------------- | ------------------------------------------------------------------ |
| `nid`                 | Message id; resends append an index suffix (`…_0`, then `…_1`)      |
| `number`              | Destination MSISDN the SMS arrived on                               |
| `otp`                 | Raw decoded SMS text (contains the code — parse it yourself)        |
| `country`, `operator` | Carrier details                                                     |
| `created_at`          | Timestamp, `YYYY-MM-DD HH:MM:SS`                                    |

Polling contract (from docs + live):
- Poll every **3–5 s**.
- Hold the number **15–20 min** before giving up / cancelling. Do not cancel early.
- Empty queue → `"otps": []` (or missing `data.otps` — treat as empty).

```bash
curl -s "https://api.zenexnetwork.com/v1/numsuccess/info" -H "mapikey: KEY"
```

## 3. Live routing ranges

```
GET https://api.zenexnetwork.com/v1/active-ranges
mapikey: KEY
```

Response: `data.active_ranges[]`, each:

| Field     | Description                                              |
| --------- | -------------------------------------------------------- |
| `range`   | Routing prefix, last 3 masked (`"261385XXX"`)            |
| `service` | Target service (`INSTAGRAM`, `FACEBOOK`/`Facebook`, `META`, `WhatsApp`, `Telegram`, `DISCORD`, `AIRBNB`, `AUTHMSG`, `VERIFY`, `NXCOMM`, `********`) |
| `tag`     | Route class (`General`, `Fb Clone`, `New Fb`)            |
| `hits`    | Recent success count — higher = hotter route              |

Contract: response micro-cached **60 s**; poll every **2–5 min**.
Strategy: filter by `service` (+ optional `tag`), pick highest `hits`.

```bash
curl -s "https://api.zenexnetwork.com/v1/active-ranges" -H "mapikey: KEY"
```

### 3a. Live prefix → country table (observed 2026-10-16, 70 rows, 15 prefixes)

| Prefix | Country       | Hottest rows (service / hits)              |
| ------ | ------------- | ------------------------------------------ |
| 224    | Guinea        | FACEBOOK 171, INSTAGRAM 68, META live      |
| 225    | Ivory Coast   | AIRBNB / WhatsApp (low volume)             |
| 228    | Togo          | INSTAGRAM 14, WhatsApp                     |
| 229    | Benin         | VERIFY 4                                   |
| 232    | Sierra Leone  | FACEBOOK 113, INSTAGRAM 70                 |
| 234    | Nigeria       | WhatsApp 2                                 |
| 237    | Cameroon      | FACEBOOK 175 / 102                         |
| 244    | Angola        | 1 row                                      |
| 261    | Madagascar    | INSTAGRAM 146 / 109, FACEBOOK 80 (TELMA)   |
| 639    | Philippines   | AuthMSG                                    |
| 855    | Cambodia      | AUTHMSG 10                                 |
| 937    | Afghanistan   | INSTAGRAM 122 / 27 (MTN Areeba)            |
| 992    | Tajikistan    | NXCOMM 45                                  |
| 996    | Kyrgyzstan    | AUTHMSG cluster                            |
| 998    | Uzbekistan    | AUTHMSG / WhatsApp                         |

## 4. Public broadcast feed

```
GET https://www.zenexnetwork.com/api/v1/global-broadcast
mapikey: KEY
```

Network-wide recent OTP successes (proves routes are delivering):

| Field                | Description                                  |
| -------------------- | -------------------------------------------- |
| `id`                 | Record id                                    |
| `number`             | **Masked** to range format (`"237627XXX"`)   |
| `otp`                | Raw SMS text, e.g. `"631231 is your Meta confirmation code."` |
| `service`            | `FACEBOOK`, `INSTAGRAM`, `META`, …           |
| `country`, `operator`| e.g. Cameroon/Mobile, Madagascar/TELMA, Guinea/CELCOM, Afghanistan/MTN (Areeba) |
| `time`               | Epoch **milliseconds**                       |

Also returns `count` (observed 26). Cached **10 s**; poll every **5–8 s**.
Real samples seen live: `867 764 is your Instagram code`, `Use 351370 for
two-factor authentication on your Meta account`, `Facebook: Your code is 287796`.

## 5. Status codes

| Status | Meaning                                          |
| ------ | ------------------------------------------------ |
| 200    | OK                                               |
| 400    | Malformed syntax / validation failure            |
| 401    | Invalid key / auth rejected                      |
| 429    | IP blacklisted by the Zenex firewall (slow down) |

No hard request quota published — follow the polling guidance above.

## 6. Node.js example (from docs: pick hottest route)

```js
const res = await axios.get("https://api.zenexnetwork.com/v1/active-ranges",
  { headers: { mapikey: process.env.ZENEX_KEY } });
const rows = res.data.data.active_ranges.filter(r =>
  r.service === "INSTAGRAM"); // + optional r.tag === "General"
if (!rows.length) console.log("no route matches");
rows.sort((a, b) => b.hits - a.hits)
    .forEach(r => console.log(r.range, r.hits));
```

## 7. Integration notes for our stack

- Shape mirrors `core/mailfish_api.py`: key from env (`ZENEX_KEY`), `provision(range)`
  → number, `wait_code(number, timeout)` polling `numsuccess/info` matching on
  `number` + `nid` dedupe (same `_0/_1` resend pattern as mail).
- Suggested provider name if wired in: `zenex` next to `mailtd`/`mailfish`.
- Poll cadence: SMS 3–5 s (matches our `wait_code` interval style); ranges 2–5 min
  with 60 s cache in mind (don't hammer).
- Live lesson 2026-10-16: 4 fresh numbers (3× Madagascar TELMA, 1× Guinea CELCOM)
  all showed IG's code screen yet delivered **0 SMS** even after resend + 90 s —
  IG silently suppresses sends to fresh numbers from flagged egress. Budget for
  dead numbers; prefer hottest-`hits` ranges; confirm META-service delivery
  separately from INSTAGRAM-service delivery.
- Unverified (panel-only, not probed): number cancel/release, balance/credit
  readout, the `.txt` docs download. Probe before documenting.
