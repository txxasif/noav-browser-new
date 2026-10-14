public final synthetic class Lcp implements wl {
    public final synthetic byte a;
    public final synthetic com.example.instatool.library.LibraryActivity b;
    public final synthetic Object c;

    public synthetic cp(com.example.instatool.library.LibraryActivity p1, Object p2, byte p3)
    {
        this.a = p3;
        this.b = p1;
        this.c = p2;
        return;
    }

    public final Object d(Object p9)
    {
        a50 v1 = a50.a;
        long v4_2 = this.c;
        android.content.ContentResolver v8_4 = this.b;
        switch (this.a) {
            case 0:
                Class vtmp3 = ((a50) p9).getClass();
                v8_4.q();
                String[] v9_1 = v8_4.y;
                if (v9_1 == null) {
                    io.T("binding");
                    throw 0;
                } else {
                    String[] v9_2 = v9_1.root;
                    String[] v9_3 = p00.h(v9_2, v9_2.getResources().getText(2131689897), 0);
                    v9_3.i(2131689945, new b9(v8_4, v4_2, 3));
                    v9_3.j();
                    return v1;
                }
            default:
                Class vtmp1 = ((k9) p9).getClass();
                String v0_5 = ((ef) v4_2).a;
                v8_4.getClass();
                long v4_1 = v0_5.b;
                try {
                    if (v4_1 <= 0) {
                        android.net.Uri v2_2 = v0_5.f;
                        if (v2_2 != null) {
                            v8_4.getContentResolver().delete(android.net.Uri.parse(v2_2), 0, 0);
                        }
                    } else {
                        android.content.ContentResolver v8_6 = ((android.app.DownloadManager) v8_4.getSystemService(android.app.DownloadManager));
                        if (v8_6 != null) {
                            long[] v3_4 = new long[1];
                            v3_4[0] = v4_1;
                            v8_6.remove(v3_4);
                        }
                    }
                } catch (Throwable) {
                }
                ((k9) p9).getWritableDatabase().delete("downloads", "id = ?", new String[] {String.valueOf(v0_5.a)}));
                return v1;
        }
    }
}
