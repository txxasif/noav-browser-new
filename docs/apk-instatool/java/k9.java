public final class Lk9 extends android.database.sqlite.SQLiteOpenHelper {
    public static final synthetic int c;
    public final java.util.concurrent.ExecutorService a;
    public final android.os.Handler b;

    public k9(com.example.instatool.InstaToolApp p4)
    {
        super(p4, "browser.db", 0, 1);
        super.a = java.util.concurrent.Executors.newSingleThreadExecutor();
        super.b = new android.os.Handler(android.os.Looper.getMainLooper());
        return;
    }

    public static vu d(String p3)
    {
        String[] v3_9 = m10.P(p3).toString();
        if (v3_9.length() != 0) {
            return new vu("(url LIKE ? ESCAPE \'\\\' OR title LIKE ? ESCAPE \'\\\')", new String[] {g.e("%", u10.y(u10.y(u10.y(v3_9, "\\", "\\\\"), "%", "\\%"), "_", "\\_"), "%"), g.e("%", u10.y(u10.y(u10.y(v3_9, "\\", "\\\\"), "%", "\\%"), "_", "\\_"), "%")}));
        } else {
            return new vu(0, 0);
        }
    }

    public final void a(String p3, String p4)
    {
        p3.getClass();
        android.database.sqlite.SQLiteDatabase v2_1 = this.getWritableDatabase();
        android.content.ContentValues v0_1 = new android.content.ContentValues();
        v0_1.put("url", p3);
        v0_1.put("title", p4);
        v0_1.put("created", Long.valueOf(System.currentTimeMillis()));
        v2_1.insertWithOnConflict("bookmarks", 0, v0_1, 4);
        return;
    }

    public final long b(String p3, String p4, String p5, String p6, long p7)
    {
        p3.getClass();
        long v2_1 = this.getWritableDatabase();
        android.content.ContentValues v0_1 = new android.content.ContentValues();
        v0_1.put("download_id", Long.valueOf(p7));
        v0_1.put("url", p3);
        v0_1.put("file_name", p4);
        v0_1.put("mime_type", p5);
        v0_1.put("local_uri", p6);
        v0_1.put("created", Long.valueOf(System.currentTimeMillis()));
        return v2_1.insert("downloads", 0, v0_1);
    }

    public final void c(wl p3, wl p4)
    {
        this.a.execute(new x8(p3, this, p4, 1));
        return;
    }

    public final java.util.ArrayList e(String p10)
    {
        p10.getClass();
        Throwable v10_2 = k9.d(p10);
        android.database.Cursor v9_2 = this.getReadableDatabase().query("bookmarks", new String[] {"id", "url", "title", "created"}), ((String) v10_2.a), ((String[]) v10_2.b), 0, 0, "created DESC");
        try {
            v9_2.getClass();
            Throwable v10_4 = new java.util.ArrayList(v9_2.getCount());
        } catch (Throwable v0_4) {
            Throwable v10_5 = v0_4;
            try {
                throw v10_5;
            } catch (Throwable v0_5) {
                c8.i(v9_2, v10_5);
                throw v0_5;
            }
        }
        while (v9_2.moveToNext()) {
            long v2_2 = v9_2.getLong(0);
            String v4_1 = v9_2.getString(1);
            v4_1.getClass();
            String v5_0 = v9_2.getString(2);
            v5_0.getClass();
            v10_4.add(new o7(v2_2, v4_1, v5_0, v9_2.getLong(3)));
        }
        v9_2.close();
        return v10_4;
    }

    public final void f(long p7, String p9, String p10)
    {
        android.database.sqlite.SQLiteDatabase v0 = this.getWritableDatabase();
        android.content.ContentValues v2_1 = new android.content.ContentValues();
        v2_1.put("title", p9);
        v2_1.put("url", p10);
        v0.updateWithOnConflict("bookmarks", v2_1, "id = ?", new String[] {String.valueOf(p7)}), 4);
        return;
    }

    public final void onCreate(android.database.sqlite.SQLiteDatabase p1)
    {
        p1.getClass();
        p1.execSQL("CREATE TABLE history (id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT NOT NULL UNIQUE, title TEXT NOT NULL DEFAULT \'\', visits INTEGER NOT NULL DEFAULT 1, last_visit INTEGER NOT NULL)");
        p1.execSQL("CREATE INDEX history_last_visit ON history(last_visit)");
        p1.execSQL("CREATE TABLE bookmarks (id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT NOT NULL UNIQUE, title TEXT NOT NULL DEFAULT \'\', created INTEGER NOT NULL)");
        p1.execSQL("CREATE TABLE downloads (id INTEGER PRIMARY KEY AUTOINCREMENT, download_id INTEGER NOT NULL, url TEXT NOT NULL, file_name TEXT NOT NULL, mime_type TEXT, local_uri TEXT, created INTEGER NOT NULL)");
        return;
    }

    public final void onUpgrade(android.database.sqlite.SQLiteDatabase p1, int p2, int p3)
    {
        p1.getClass();
        return;
    }
}
