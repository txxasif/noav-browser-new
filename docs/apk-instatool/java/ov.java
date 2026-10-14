public final class Lov {
    public static final ox b;
    public final android.content.Context a;

    static ov()
    {
        ov.b = new ox("-(?:Male|Female)-(\\d+)\\.", px.IGNORE_CASE);
        return;
    }

    public ov(com.example.instatool.browser.BrowserActivity p1)
    {
        this.a = p1.getApplicationContext();
        return;
    }

    public final android.net.Uri a(java.util.Set p12)
    {
        p12.getClass();
        android.net.Uri$Builder v0_5 = new java.util.ArrayList();
        String v12_6 = p12.iterator();
        while(true) {
            int v2_8 = this.a;
            java.util.Map$Entry v4_1 = 0;
            if (!v12_6.hasNext()) {
                if (!v0_5.isEmpty()) {
                    android.net.Uri v11_8 = ((vu) rb.n0(v0_5));
                    android.net.Uri$Builder v0_6 = ((String) v11_8.a);
                    android.net.Uri v11_10 = ((String) v11_8.b);
                    String v1_9 = new java.io.File(v2_8.getCacheDir(), "profile");
                    v1_9.mkdirs();
                    java.util.Map$Entry v5_8 = new java.io.File(v1_9, v11_10);
                    String v1_10 = v2_8.getAssets();
                    int v6_9 = new StringBuilder();
                    v6_9.append(v0_6);
                    v6_9.append("/");
                    v6_9.append(v11_10);
                    android.net.Uri v11_12 = v1_10.open(v6_9.toString());
                    try {
                        String v1_12 = new java.io.FileOutputStream(v5_8);
                        try {
                            v11_12.getClass();
                            io.i(v11_12, v1_12);
                        } catch (String v12_7) {
                            try {
                                throw v12_7;
                            } catch (android.net.Uri$Builder v0_8) {
                                c8.i(v1_12, v12_7);
                                throw v0_8;
                            }
                        }
                        v1_12.close();
                        v11_12.close();
                        android.net.Uri v11_13 = v2_8.getPackageName();
                        String v1_14 = new StringBuilder();
                        v1_14.append(v11_13);
                        v1_14.append(".fileprovider");
                        v11_12 = androidx.core.content.FileProvider.b(0, v2_8, v1_14.toString());
                        try {
                            String v1_16 = v5_8.getCanonicalPath();
                            int v2_11 = v11_12.b.entrySet().iterator();
                            java.util.Map$Entry v4_0 = 0;
                        } catch (java.io.IOException) {
                            e6.f(v5_8, "Failed to resolve canonical path for ");
                            return 0;
                        }
                        while (v2_11.hasNext()) {
                            java.util.Map$Entry v5_1 = ((java.util.Map$Entry) v2_11.next());
                            int v6_2 = ((java.io.File) v5_1.getValue()).getPath();
                            if ((androidx.core.content.FileProvider.d(v1_16).startsWith(androidx.core.content.FileProvider.d(v6_2).concat("/"))) && ((v4_0 == null) || (v6_2.length() > ((java.io.File) v4_0.getValue()).getPath().length()))) {
                                v4_0 = v5_1;
                            }
                        }
                        if (v4_0 == null) {
                            e6.f(v1_16, "Failed to find configured root that contains ");
                            return 0;
                        } else {
                            String v12_1;
                            String v12_11 = ((java.io.File) v4_0.getValue()).getPath();
                            if (!v12_11.endsWith("/")) {
                                v12_1 = v1_16.substring((v12_11.length() + 1));
                            } else {
                                v12_1 = v1_16.substring(v12_11.length());
                            }
                            String v1_1 = new StringBuilder();
                            v1_1.append(android.net.Uri.encode(((String) v4_0.getKey())));
                            v1_1.append(47);
                            v1_1.append(android.net.Uri.encode(v12_1, "/"));
                            return new android.net.Uri$Builder().scheme("content").authority(v11_12.a).encodedPath(v1_1.toString()).build();
                        }
                    } catch (String v12_8) {
                        try {
                            throw v12_8;
                        } catch (android.net.Uri$Builder v0_9) {
                            c8.i(v11_12, v12_8);
                            throw v0_9;
                        }
                    }
                } else {
                    return 0;
                }
            } else {
                String v1_7;
                String v1_6 = nv.a[((mv) v12_6.next()).ordinal()];
                if (v1_6 == 1) {
                    v1_7 = "profile/boys";
                } else {
                    if (v1_6 != 2) {
                        break;
                    }
                    v1_7 = "profile/girls";
                }
                int v2_5 = v2_8.getAssets().list(v1_7);
                if (v2_5 == 0) {
                    v2_5 = new String[0];
                }
                java.util.Map$Entry v5_5 = new java.util.ArrayList();
                int v6_4 = v2_5.length;
                int v7_6 = 0;
                while (v7_6 < v6_4) {
                    String v8_2 = v2_5[v7_6];
                    v8_2.getClass();
                    int v9_1 = ox.a(ov.b, v8_2);
                    if (v9_1 != 0) {
                        int v9_5 = ((String) ((pr) v9_1.a()).get(1));
                        if (v9_5 != 0) {
                            int v9_6 = t10.w(v9_5);
                            if ((v9_6 != 0) && (v9_6.intValue() >= 18)) {
                                v5_5.add(v8_2);
                            }
                        }
                    }
                    v7_6++;
                }
                int v2_7 = new java.util.ArrayList(tb.e0(v5_5));
                int v3_1 = v5_5.size();
                while (v4_1 < v3_1) {
                    int v6_5 = v5_5.get(v4_1);
                    v4_1++;
                    v2_7.add(new vu(v1_7, ((String) v6_5)));
                }
                v0_5.addAll(v2_7);
            }
        }
        android.net.Uri v11_7 = new uk;
        v11_7();
        throw v11_7;
    }
}
