/** Client-facing license endpoints: activate / validate / trial. */
import { jsonResponse } from '../http.js';

export async function handleActivate(db, body) {
  try {
    const inputKey = (body.licenseKey || body.username || '').trim();
    const hwid = (body.hwid || '').trim();

    if (!inputKey) {
      return jsonResponse({ isValid: false, status: 'ERROR', message: 'Please provide a license key.' }, 400);
    }

    const row = await db
      .prepare(
        'SELECT * FROM licenses WHERE license_key = ? COLLATE NOCASE OR customer_phone = ? OR username = ?'
      )
      .bind(inputKey, inputKey, inputKey)
      .first();

    if (!row) {
      return jsonResponse(
        {
          status: 'NOT_FOUND',
          message: `Invalid key or username. No active subscription found for: ${inputKey}`,
          isValid: false,
          hwid,
        },
        200
      );
    }

    if (row.status === 'REVOKED') {
      return jsonResponse({ isValid: false, status: 'REVOKED', message: 'This license has been revoked.' }, 200);
    }

    const now = new Date();
    if (row.expires_at && new Date(row.expires_at) < now) {
      return jsonResponse({ isValid: false, status: 'EXPIRED', message: 'This license has expired.' }, 200);
    }

    if (row.hwid && row.hwid !== hwid) {
      return jsonResponse(
        {
          isValid: false,
          status: 'HWID_MISMATCH',
          message: 'This key is bound to another machine. Contact support to reset HWID.',
        },
        200
      );
    }

    let expiresAt = row.expires_at;
    if (!expiresAt) {
      const expDate = new Date();
      if (row.license_type === 'LIFETIME') expDate.setFullYear(expDate.getFullYear() + 20);
      else if (row.license_type === 'YEARLY') expDate.setFullYear(expDate.getFullYear() + 1);
      else if (row.license_type === '3_MONTHS') expDate.setDate(expDate.getDate() + 90);
      else if (row.license_type === '3_DAYS' || row.license_type === 'TRIAL' || (row.plan && row.plan.includes('3 Day')))
        expDate.setDate(expDate.getDate() + 3);
      else expDate.setDate(expDate.getDate() + 30);
      expiresAt = expDate.toISOString();
    }

    await db
      .prepare('UPDATE licenses SET hwid = ?, activated_at = COALESCE(activated_at, ?), expires_at = ? WHERE license_key = ?')
      .bind(hwid, now.toISOString(), expiresAt, row.license_key)
      .run();

    return jsonResponse({
      isValid: true,
      status: 'ACTIVE',
      message: 'License activated successfully!',
      license: {
        license_key: row.license_key,
        username: row.username || 'Customer',
        customer_name: row.customer_name || row.username || 'Customer',
        license_type: row.license_type,
        plan: row.plan,
        expires_at: expiresAt,
        max_profiles: row.max_profiles || 999999,
        status: 'ACTIVE',
        hwid,
      },
      hwid,
      signature: 'cf-sig-' + Date.now(),
    });
  } catch (err) {
    return jsonResponse({ isValid: false, status: 'ERROR', message: err.message }, 500);
  }
}

export async function handleValidate(db, body) {
  try {
    const inputKey = (body.licenseKey || body.username || '').trim();
    const hwid = (body.hwid || '').trim();

    const row = await db
      .prepare(
        'SELECT * FROM licenses WHERE license_key = ? COLLATE NOCASE OR customer_phone = ? OR username = ?'
      )
      .bind(inputKey, inputKey, inputKey)
      .first();

    if (!row) return jsonResponse({ isValid: false, status: 'NOT_FOUND', message: 'License not found.' }, 200);
    if (row.status === 'REVOKED')
      return jsonResponse({ isValid: false, status: 'REVOKED', message: 'License revoked.' }, 200);
    if (row.expires_at && new Date(row.expires_at) < new Date())
      return jsonResponse({ isValid: false, status: 'EXPIRED', message: 'License expired.' }, 200);
    if (row.hwid && row.hwid !== hwid)
      return jsonResponse({ isValid: false, status: 'HWID_MISMATCH', message: 'HWID mismatch.' }, 200);

    return jsonResponse({
      isValid: true,
      status: 'ACTIVE',
      license: {
        license_key: row.license_key,
        username: row.username,
        customer_name: row.customer_name,
        license_type: row.license_type,
        plan: row.plan,
        expires_at: row.expires_at,
        max_profiles: row.max_profiles,
        status: 'ACTIVE',
        hwid,
      },
    });
  } catch (err) {
    return jsonResponse({ isValid: false, status: 'ERROR', message: err.message }, 500);
  }
}

export async function handleTrial(db, body) {
  try {
    const hwid = (body.hwid || '').trim();
    if (!hwid) return jsonResponse({ isValid: false, message: 'HWID required' }, 400);

    const existingTrial = await db.prepare('SELECT * FROM trials WHERE hwid = ?').bind(hwid).first();
    if (existingTrial) {
      const isExpired = new Date(existingTrial.expires_at) < new Date();
      return jsonResponse({
        isValid: !isExpired,
        status: isExpired ? 'TRIAL_EXPIRED' : 'ACTIVE',
        isTrial: true,
        expires_at: existingTrial.expires_at,
        message: isExpired ? '3-Day Free Trial has expired.' : 'Trial already active.',
      });
    }

    const claimedAt = new Date();
    const expiresAt = new Date(claimedAt.getTime() + 3 * 24 * 60 * 60 * 1000).toISOString();
    await db
      .prepare('INSERT INTO trials (hwid, claimed_at, expires_at) VALUES (?, ?, ?)')
      .bind(hwid, claimedAt.toISOString(), expiresAt)
      .run();

    return jsonResponse({
      isValid: true,
      status: 'ACTIVE',
      isTrial: true,
      message: '3-Day Free Trial activated!',
      license: {
        license_key: 'TRIAL-' + hwid.slice(-8),
        license_type: 'TRIAL',
        plan: '3-Day Free Trial',
        expires_at: expiresAt,
        max_profiles: 999999,
        status: 'ACTIVE',
        hwid,
      },
    });
  } catch (err) {
    return jsonResponse({ isValid: false, message: err.message }, 500);
  }
}
