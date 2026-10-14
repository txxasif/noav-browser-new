public final synthetic class Lj8 implements java.lang.Runnable {
    public final synthetic byte a;
    public final synthetic com.example.instatool.browser.BrowserActivity b;

    public synthetic j8(com.example.instatool.browser.BrowserActivity p1, byte p2)
    {
        this.a = p2;
        this.b = p1;
        return;
    }

    public final void run()
    {
        rx v1 = 0;
        String v14_1 = this.b;
        switch (this.a) {
            case 0:
                org.json.JSONObject v5_8;
                v14_1.S.getClass();
                boolean v0_24 = v14_1.getPackageManager().getPackageInfo(v14_1.getPackageName(), 0);
                int v2_2 = android.os.Build$VERSION.SDK_INT;
                if (v2_2 < 28) {
                    v5_8 = ((long) v0_24.versionCode);
                } else {
                    v5_8 = z.d(v0_24);
                }
                boolean v0_28;
                if (v2_2 < 28) {
                    v0_28 = v14_1.getPackageManager().getPackageInfo(v14_1.getPackageName(), 64).signatures;
                } else {
                    boolean v0_32 = z.e(v14_1.getPackageManager().getPackageInfo(v14_1.getPackageName(), 134217728));
                    if (!v0_32) {
                        v0_28 = 0;
                    } else {
                        v0_28 = z.r(v0_32);
                    }
                }
                boolean v0_36;
                if (!v0_28) {
                    v0_36 = "";
                } else {
                    boolean v0_33;
                    if (v0_28.length != 0) {
                        v0_33 = v0_28[0];
                    } else {
                        v0_33 = 0;
                    }
                    if (!v0_33) {
                    } else {
                        boolean v0_34 = v0_33.toByteArray();
                        if (v0_34) {
                            boolean v0_35 = java.security.MessageDigest.getInstance("SHA-256").digest(v0_34);
                            v0_35.getClass();
                            rx v7_6 = new StringBuilder();
                            v7_6.append("");
                            String v8_2 = v0_35.length;
                            int v9_2 = 0;
                            int v10_1 = 0;
                            while (v9_2 < v8_2) {
                                int v11_1 = v0_35[v9_2];
                                v10_1++;
                                if (v10_1 > 1) {
                                    v7_6.append("");
                                }
                                v7_6.append(String.format("%02x", java.util.Arrays.copyOf(new Object[] {Byte.valueOf(v11_1)}), 1)));
                                v9_2++;
                            }
                            v7_6.append("");
                            v0_36 = v7_6.toString();
                        }
                    }
                }
                rx v7_8 = new StringBuilder("https://email.yamin.bd/apis.php?action=app&version=");
                v7_8.append(v5_8);
                v7_8.append("&cert=");
                v7_8.append(v0_36);
                try {
                    boolean v0_2 = pg.j(v7_8.toString());
                } catch (boolean v0_3) {
                    v0_2 = new hy(v0_3);
                }
                if ((v0_2 instanceof hy)) {
                    v0_2 = 0;
                }
                boolean v0_5 = ((String) v0_2);
                if (v0_5) {
                    try {
                        org.json.JSONObject v5_5 = new org.json.JSONObject(v0_5);
                    } catch (boolean v0_6) {
                        v5_5 = new hy(v0_6);
                    }
                    if ((v5_5 instanceof hy)) {
                        v5_5 = 0;
                    }
                    org.json.JSONObject v5_7 = ((org.json.JSONObject) v5_5);
                    if (v5_7 != null) {
                        String v8_0;
                        boolean v0_9 = v5_7.optJSONObject("notification");
                        org.json.JSONObject v6_1 = v5_7.optJSONObject("update");
                        if (!v0_9) {
                            v8_0 = 0;
                        } else {
                            v8_0 = v0_9.optString("title");
                        }
                        if (v8_0 == null) {
                            v8_0 = "";
                        }
                        boolean v0_10;
                        if (!v0_9) {
                            v0_10 = 0;
                        } else {
                            v0_10 = v0_9.optString("body");
                        }
                        int v9_1;
                        if (v0_10) {
                            v9_1 = v0_10;
                        } else {
                            v9_1 = "";
                        }
                        if ((v6_1 == null) || (v6_1.optBoolean("required") != 1)) {
                            int v10_0 = 0;
                        } else {
                            v10_0 = 1;
                        }
                        boolean v0_14;
                        if (v6_1 == null) {
                            v0_14 = 0;
                        } else {
                            v0_14 = v6_1.optString("url");
                        }
                        int v11_0;
                        if (v0_14) {
                            v11_0 = v0_14;
                        } else {
                            v11_0 = "";
                        }
                        if (v6_1 != null) {
                            v1 = v6_1.optString("message");
                        }
                        String v12_0;
                        if (v1 != null) {
                            v12_0 = v1;
                        } else {
                            v12_0 = "";
                        }
                        if ((!v5_7.optBoolean("enforceCerts")) || (!v5_7.optBoolean("blocked"))) {
                            int v13 = 0;
                        } else {
                            v13 = 1;
                        }
                        v1 = new rx(v8_0, v9_1, v10_0, v11_0, v12_0, v13);
                    }
                }
                v14_1.runOnUiThread(new k3(v14_1, v1, 2));
                return;
            case 1:
                boolean v0_29 = v14_1.y;
                if (!v0_29) {
                    io.T("binding");
                    throw 0;
                } else {
                    boolean v0_4 = v0_29.autoTool.getRoot();
                    v0_4.getClass();
                    v14_1.r(v0_4);
                    return;
                }
            default:
                v14_1.Y();
                return;
        }
    }
}
