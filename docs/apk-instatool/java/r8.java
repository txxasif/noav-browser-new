public final synthetic class Lr8 implements wl {
    public final synthetic byte a;
    public final synthetic Object b;
    public final synthetic Object c;
    public final synthetic Object d;

    public synthetic r8(bn p1, o7 p2, an p3, com.example.instatool.databinding.ItemHomeTileBinding p4)
    {
        this.a = 1;
        this.b = p1;
        this.c = p2;
        this.d = p4;
        return;
    }

    public synthetic r8(com.example.instatool.browser.BrowserActivity p2, gf p3, p9 p4)
    {
        this.a = 0;
        this.b = p2;
        this.c = p3;
        this.d = p4;
        return;
    }

    public final Object d(Object p12)
    {
        a50 v1 = a50.a;
        int v2_4 = this.d;
        String v3_2 = this.c;
        String v11_5 = this.b;
        switch (this.a) {
            case 0:
                String v11_6 = ((com.example.instatool.browser.BrowserActivity) v11_5);
                gf v7_1 = ((gf) v3_2);
                int v2_7 = ((p9) v2_4);
                Class vtmp1 = ((String) p12).getClass();
                p00 v12_6 = v11_6.A().a();
                i8 v0_5 = v2_7.c;
                int v2_3 = v7_1.d;
                String v3_1 = v7_1.a;
                hf v4_2 = ((android.app.DownloadManager) v11_6.getSystemService(android.app.DownloadManager));
                try {
                    if (v4_2 != null) {
                        int v9_2;
                        long v5_3;
                        if (v2_3 == 0) {
                            long v5_4 = android.webkit.MimeTypeMap.getSingleton();
                            String v6_2 = m10.M(((String) p12), 46, "").toLowerCase(java.util.Locale.ROOT);
                            v6_2.getClass();
                            v5_3 = v5_4.getMimeTypeFromExtension(v6_2);
                            if (v5_3 != 0) {
                                v9_2 = v5_3;
                            } else {
                                v9_2 = v2_3;
                            }
                        } else {
                            if ((m10.G(v2_3)) || (v2_3.equals("application/octet-stream"))) {
                                v5_3 = 0;
                            } else {
                                v5_3 = v2_3;
                            }
                            if (v5_3 != 0) {
                            }
                        }
                        int v2_6 = new android.app.DownloadManager$Request(android.net.Uri.parse(v3_1));
                        if (v9_2 != 0) {
                            v2_6.setMimeType(v9_2);
                        }
                        i8 v0_7 = en.a(v0_5).getCookie(v3_1);
                        if (v0_7 != null) {
                            v2_6.addRequestHeader("Cookie", v0_7);
                        }
                        i8 v0_8 = v7_1.b;
                        if (v0_8 != null) {
                            v2_6.addRequestHeader("User-Agent", v0_8);
                        }
                        i8 v0_9 = v7_1.f;
                        if (v0_9 != null) {
                            v2_6.addRequestHeader("Referer", v0_9);
                        }
                        v2_6.setTitle(((String) p12));
                        v2_6.setDescription(android.net.Uri.parse(v3_1).getHost());
                        v2_6.setNotificationVisibility(1);
                        v2_6.setDestinationInExternalPublicDir(android.os.Environment.DIRECTORY_DOWNLOADS, ((String) p12));
                        v12_6.c(new hf(v4_2.enqueue(v2_6), v7_1, ((String) p12), v9_2), 0);
                        p00 v12_7 = v11_6.y;
                        if (v12_7 == null) {
                            io.T("binding");
                            throw 0;
                        } else {
                            p00 v12_1 = p00.h(v12_7.contentFrame, v11_6.getString(2131689650, new Object[] {((String) p12)})), 0);
                            v12_1.e(v11_6.i0());
                            v12_1.i(2131689952, new i8(v11_6, 16));
                            v12_1.j();
                        }
                    } else {
                        p00 v12_3 = v11_6.getString(2131689645);
                        v12_3.getClass();
                        v11_6.h0(v12_3);
                    }
                } catch (Exception) {
                }
                return v1;
            default:
                if (((android.graphics.Bitmap) p12) == null) {
                    return v1;
                } else {
                    if (!io.d(((bn) v11_5).u, ((o7) v3_2).b)) {
                        return v1;
                    } else {
                        an.e(((com.example.instatool.databinding.ItemHomeTileBinding) v2_4), ((android.graphics.Bitmap) p12));
                        return v1;
                    }
                }
        }
    }
}
