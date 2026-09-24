/** D1 schema bootstrap. Runs on every request; CREATE IF NOT EXISTS is cheap. */

export async function ensureTables(db) {
  try {
    await db
      .prepare(
        `
      CREATE TABLE IF NOT EXISTS licenses (
        license_key TEXT PRIMARY KEY,
        username TEXT,
        customer_name TEXT,
        customer_phone TEXT,
        license_type TEXT DEFAULT 'MONTHLY',
        plan TEXT DEFAULT '1 Month Pro',
        max_profiles INTEGER DEFAULT 999999,
        status TEXT DEFAULT 'ACTIVE',
        hwid TEXT,
        activated_at TEXT,
        expires_at TEXT,
        created_at TEXT
      )
    `
      )
      .run();

    await db
      .prepare(
        `
      CREATE TABLE IF NOT EXISTS trials (
        hwid TEXT PRIMARY KEY,
        claimed_at TEXT,
        expires_at TEXT
      )
    `
      )
      .run();

    await db
      .prepare(
        `
      CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        license_key TEXT NOT NULL,
        billing_month TEXT NOT NULL,
        amount REAL DEFAULT 0,
        currency TEXT DEFAULT 'BDT',
        payment_status TEXT DEFAULT 'UNPAID',
        payment_method TEXT DEFAULT 'Cash',
        notes TEXT DEFAULT '',
        updated_at TEXT,
        UNIQUE(license_key, billing_month)
      )
    `
      )
      .run();
  } catch (err) {
    console.error('Table init error:', err);
  }
}
