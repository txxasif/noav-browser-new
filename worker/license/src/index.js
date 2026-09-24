/**
 * nova-license — Nova Browser Cloudflare Enterprise Licensing Authority.
 * Split from the single-file worker; routing only. Behavior unchanged,
 * plus the admin money tracker (see api/payments.js + ui/billing.js).
 */
import { corsPreflight, jsonResponse } from './http.js';
import { ensureTables } from './db.js';
import { checkAdminAuth } from './auth.js';
import { handleActivate, handleValidate, handleTrial } from './api/license.js';
import {
  handleAdminLogin,
  handleAdminLicenses,
  handleAdminGenerate,
  handleAdminAction,
} from './api/admin.js';
import { handlePaymentsGet, handlePaymentsUpsert, handlePaymentsDelete, handlePaymentsSummary, handlePaymentsHistory } from './api/payments.js';
import { adminHtml } from './ui/shell.js';

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;

    if (request.method === 'OPTIONS') return corsPreflight();

    const db = env.DB;
    if (db) await ensureTables(db);

    // 1. CLIENT API: ACTIVATE
    if (path === '/api/license/activate' && request.method === 'POST') {
      return handleActivate(db, await request.json());
    }

    // 2. CLIENT API: VALIDATE
    if (path === '/api/license/validate' && request.method === 'POST') {
      return handleValidate(db, await request.json());
    }

    // 3. CLIENT API: TRIAL
    if (path === '/api/license/trial' && request.method === 'POST') {
      return handleTrial(db, await request.json());
    }

    // 4. ADMIN AUTHENTICATION
    if (path === '/api/admin/login' && request.method === 'POST') {
      return handleAdminLogin(env, await request.json());
    }

    if (path.startsWith('/api/admin/')) {
      if (!checkAdminAuth(request, env)) {
        return jsonResponse({ success: false, message: 'Unauthorized access.' }, 401);
      }
    }

    // 5. ADMIN API: LIST + METRICS
    if (path === '/api/admin/licenses' && request.method === 'GET') {
      return handleAdminLicenses(db);
    }

    // 6. ADMIN API: GENERATE
    if (path === '/api/admin/generate' && request.method === 'POST') {
      return handleAdminGenerate(db, await request.json());
    }

    // 7. ADMIN API: ACTIONS
    if (path === '/api/admin/action' && request.method === 'POST') {
      return handleAdminAction(db, await request.json());
    }

    // 8. ADMIN API: MONEY TRACKER (manual per-user monthly ledger)
    if (path === '/api/admin/payments/summary' && request.method === 'GET') {
      return handlePaymentsSummary(db);
    }
    if (path === '/api/admin/payments/history' && request.method === 'GET') {
      return handlePaymentsHistory(db, url.searchParams.get('license_key'));
    }
    if (path === '/api/admin/payments' && request.method === 'GET') {
      return handlePaymentsGet(db, url.searchParams.get('month'));
    }
    if (path === '/api/admin/payments' && request.method === 'POST') {
      return handlePaymentsUpsert(db, await request.json());
    }
    if (path === '/api/admin/payments' && request.method === 'DELETE') {
      return handlePaymentsDelete(db, url.searchParams.get('license_key'), url.searchParams.get('billing_month'));
    }

    // 9. SERVE THE DASHBOARD
    if (path === '/admin' || path === '/') {
      return new Response(adminHtml(), { headers: { 'Content-Type': 'text/html; charset=utf-8' } });
    }

    return jsonResponse({ status: 'ONLINE', service: 'Nova Cloudflare Licensing Hub' });
  },
};
