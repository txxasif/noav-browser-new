/**
 * NEW — Admin money tracker. Manual per-user monthly ledger.
 * Backed by the `payments` table (created in db.js), keyed (license_key, month).
 */
import { jsonResponse } from '../http.js';

const VALID_MONTH = /^\d{4}-(0[1-9]|1[0-2])$/;
const VALID_STATUS = new Set(['PAID', 'UNPAID', 'FREE_TOKEN']);

function currentMonth() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}

/** GET /api/admin/payments?month=YYYY-MM — every user + their entry for the month. */
export async function handlePaymentsGet(db, month) {
  const m = month || currentMonth();
  if (!VALID_MONTH.test(m)) return jsonResponse({ success: false, message: 'month must be YYYY-MM' }, 400);
  try {
    const r = await db
      .prepare(
        `SELECT l.license_key, l.username, l.customer_name, l.plan, l.status AS license_status,
                p.billing_month, p.amount, p.currency, p.payment_status,
                p.payment_method, p.notes, p.updated_at
         FROM licenses l
         LEFT JOIN payments p
           ON p.license_key = l.license_key AND p.billing_month = ?
         ORDER BY l.username COLLATE NOCASE`
      )
      .bind(m)
      .all();
    return jsonResponse({ success: true, month: m, rows: r.results || [] });
  } catch (e) {
    return jsonResponse({ success: false, message: e.message }, 500);
  }
}

/** POST /api/admin/payments — manual upsert of one user/month entry. */
export async function handlePaymentsUpsert(db, body) {
  const license_key = String(body.license_key || '').trim().toUpperCase();
  const billing_month = String(body.billing_month || '').trim();
  const amount = Number(body.amount ?? 0);
  const payment_status = String(body.payment_status || 'UNPAID').trim().toUpperCase();
  const payment_method = String(body.payment_method || 'Cash').trim();
  const notes = String(body.notes || '').trim();

  if (!license_key) return jsonResponse({ success: false, message: 'license_key required' }, 400);
  if (!VALID_MONTH.test(billing_month))
    return jsonResponse({ success: false, message: 'billing_month must be YYYY-MM' }, 400);
  if (!Number.isFinite(amount) || amount < 0)
    return jsonResponse({ success: false, message: 'amount must be >= 0' }, 400);
  if (!VALID_STATUS.has(payment_status))
    return jsonResponse({ success: false, message: 'payment_status must be PAID, UNPAID or FREE_TOKEN' }, 400);

  try {
    const lic = await db
      .prepare('SELECT license_key FROM licenses WHERE license_key = ?')
      .bind(license_key)
      .first();
    if (!lic) return jsonResponse({ success: false, message: 'unknown license_key' }, 404);

    await db
      .prepare(
        `INSERT INTO payments
           (license_key, billing_month, amount, payment_status, payment_method, notes, updated_at)
         VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
         ON CONFLICT(license_key, billing_month) DO UPDATE SET
           amount = excluded.amount,
           payment_status = excluded.payment_status,
           payment_method = excluded.payment_method,
           notes = excluded.notes,
           updated_at = datetime('now')`
      )
      .bind(license_key, billing_month, amount, payment_status, payment_method, notes)
      .run();
    return jsonResponse({ success: true });
  } catch (e) {
    return jsonResponse({ success: false, message: e.message }, 500);
  }
}

/** DELETE /api/admin/payments?license_key=&billing_month= — remove one entry. */
export async function handlePaymentsDelete(db, license_key, billing_month) {
  const key = String(license_key || '').trim().toUpperCase();
  const month = String(billing_month || '').trim();
  if (!key || !VALID_MONTH.test(month)) {
    return jsonResponse({ success: false, message: 'license_key and billing_month=YYYY-MM required' }, 400);
  }
  try {
    await db
      .prepare('DELETE FROM payments WHERE license_key = ? AND billing_month = ?')
      .bind(key, month)
      .run();
    return jsonResponse({ success: true });
  } catch (e) {
    return jsonResponse({ success: false, message: e.message }, 500);
  }
}

function lastMonths(n) {
  const out = [];
  const d = new Date();
  d.setDate(1);
  for (let i = 0; i < n; i++) {
    out.unshift(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`);
    d.setMonth(d.getMonth() - 1);
  }
  return out;
}

/** GET /api/admin/payments/summary — per-month totals for the last 6 months. */
export async function handlePaymentsSummary(db) {
  try {
    const months = lastMonths(6);
    const marks = months.map(() => '?').join(',');
    const r = await db
      .prepare(
        `SELECT billing_month,
                COALESCE(SUM(CASE WHEN payment_status = 'PAID' THEN amount ELSE 0 END), 0) AS collected,
                COALESCE(SUM(CASE WHEN payment_status != 'PAID' THEN amount ELSE 0 END), 0) AS outstanding,
                COUNT(CASE WHEN payment_status = 'PAID' THEN 1 END) AS paid_n,
                COUNT(*) AS total_n
         FROM payments WHERE billing_month IN (${marks})
         GROUP BY billing_month`
      )
      .bind(...months)
      .all();
    const byMonth = new Map((r.results || []).map((x) => [x.billing_month, x]));
    return jsonResponse({
      success: true,
      months: months.map((m) => ({
        billing_month: m,
        collected: byMonth.get(m)?.collected ?? 0,
        outstanding: byMonth.get(m)?.outstanding ?? 0,
        paid_n: byMonth.get(m)?.paid_n ?? 0,
        total_n: byMonth.get(m)?.total_n ?? 0,
      })),
    });
  } catch (e) {
    return jsonResponse({ success: false, message: e.message }, 500);
  }
}

/** GET /api/admin/payments/history?license_key= — every month for one user, newest first. */
export async function handlePaymentsHistory(db, license_key) {
  const key = String(license_key || '').trim().toUpperCase();
  if (!key) return jsonResponse({ success: false, message: 'license_key required' }, 400);
  try {
    const r = await db
      .prepare('SELECT * FROM payments WHERE license_key = ? ORDER BY billing_month DESC')
      .bind(key)
      .all();
    return jsonResponse({ success: true, rows: r.results || [] });
  } catch (e) {
    return jsonResponse({ success: false, message: e.message }, 500);
  }
}
