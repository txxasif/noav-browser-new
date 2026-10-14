public final class Ljj {
    public final java.io.File a;
    public final android.util.LruCache b;
    public final java.util.Set c;
    public final java.util.concurrent.ExecutorService d;
    public final android.os.Handler e;

    public jj(com.example.instatool.InstaToolApp p3)
    {
        this.a = new java.io.File(p3.getCacheDir(), "favicons");
        this.b = new android.util.LruCache(96);
        android.os.Handler v3_3 = java.util.Collections.synchronizedSet(new java.util.HashSet());
        v3_3.getClass();
        this.c = v3_3;
        this.d = java.util.concurrent.Executors.newFixedThreadPool(2);
        this.e = new android.os.Handler(android.os.Looper.getMainLooper());
        return;
    }

    public static String a(String p2)
    {
        int v2_1 = android.net.Uri.parse(p2);
        if ((io.d(v2_1.getScheme(), "http")) || (io.d(v2_1.getScheme(), "https"))) {
            int v2_2 = v2_1.getHost();
            if (v2_2 != 0) {
                int v2_3 = v2_2.toLowerCase(java.util.Locale.ROOT);
                v2_3.getClass();
                int v2_4 = m10.J(v2_3, "www.");
                if (v2_4.length() > 0) {
                    return v2_4;
                }
            }
        }
        return 0;
    }

    public final void b(String p4, wl p5)
    {
        p4.getClass();
        String v4_1 = jj.a(p4);
        if (v4_1 != null) {
            x8 v0_4 = ((android.graphics.Bitmap) this.b.get(v4_1));
            if ((v0_4 == null) || ((v0_4.getWidth() < 64) && (!this.c.contains(v4_1)))) {
                this.d.execute(new x8(this, v4_1, p5, 7));
                return;
            } else {
                p5.d(v0_4);
                return;
            }
        } else {
            p5.d(0);
            return;
        }
    }

    public final void c(java.io.File p2, android.graphics.Bitmap p3)
    {
        try {
            this.a.mkdirs();
            java.io.FileOutputStream v1_2 = new java.io.FileOutputStream;
            v1_2(p2);
            try {
                p3.compress(android.graphics.Bitmap$CompressFormat.PNG, 100, v1_2);
            } catch (Throwable v2_2) {
                try {
                    throw v2_2;
                } catch (Throwable v3_1) {
                    c8.i(v1_2, v2_2);
                    throw v3_1;
                }
            }
            v1_2.close();
            return;
        } catch (Throwable) {
            return;
        }
    }
}
