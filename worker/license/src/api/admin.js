/** Admin license endpoints: login / list / generate / actions. */
import { jsonResponse } from '../http.js';
import { DEFAULT_ADMIN_PASSWORD, generateKey } from '../auth.js';

export async function handleAdminLogin(env, body) {
  try {
    const adminPass = (env.ADMIN_PASSWORD || DEFAULT_ADMIN_PASSWORD).trim();
    const enteredPass = (body.password || '').trim();
    if (enteredPass === adminPass) {
      return jsonResponse({ success: true, token: adminPass });
    }
    return jsonResponse({ success: false, message: 'Incorrect admin password.' }, 401);
  } catch (e) {
    return jsonResponse({ success: false, message: 'Invalid request body.' }, 400);
  }
}

export async function handleAdminLicenses(db) {
  try {
    const rows = await db.prepare('SELECT * FROM licenses ORDER BY created_at DESC').all();
    const trialCount = await db.prepare('SELECT COUNT(*) as count FROM trials').first();
    return jsonResponse({
      success: true,
      licenses: rows.results || [],
      trialCount: trialCount ? trialCount.count : 0,
    });
  } catch (e) {
    return jsonResponse({ success: false, message: e.message }, 500);
  }
}

export async function handleAdminGenerate(db, body) {
  try {
    const plan = body.plan || '1 Month Pro';
    const quantity = Math.min(Math.max(parseInt(body.quantity, 10) || 1, 1), 500);
    const customerName = body.customer_name || '';
    const customerPhone = body.customer_phone || '';

    let type = 'MONTHLY';
    if (plan.includes('Lifetime')) type = 'LIFETIME';
    else if (plan.includes('Year')) type = 'YEARLY';
    else if (plan.includes('3 Month')) type = '3_MONTHS';
    else if (plan.includes('3 Day')) type = '3_DAYS';

    const keys = [];
    const now = new Date().toISOString();

    for (let i = 0; i < quantity; i++) {
      const key = generateKey();
      await db
        .prepare(
          `
            INSERT INTO licenses (license_key, username, customer_name, customer_phone, license_type, plan, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE', ?)
          `
        )
        .bind(key, customerName || key, customerName, customerPhone, type, plan, now)
        .run();
      keys.push(key);
    }

    return jsonResponse({ success: true, keys });
  } catch (e) {
    return jsonResponse({ success: false, message: e.message }, 500);
  }
}

export async function handleAdminAction(db, body) {
  try {
    const { action, licenseKey } = body;

    if (action === 'revoke') {
      await db.prepare('UPDATE licenses SET status = \'REVOKED\' WHERE license_key = ?').bind(licenseKey).run();
    } else if (action === 'activate') {
      await db.prepare('UPDATE licenses SET status = \'ACTIVE\' WHERE license_key = ?').bind(licenseKey).run();
    } else if (action === 'unbind_hwid') {
      await db.prepare('UPDATE licenses SET hwid = NULL WHERE license_key = ?').bind(licenseKey).run();
    } else if (action === 'delete') {
      await db.prepare('DELETE FROM licenses WHERE license_key = ?').bind(licenseKey).run();
    }

    return jsonResponse({ success: true });
  } catch (e) {
    return jsonResponse({ success: false, message: e.message }, 500);
  }
}
