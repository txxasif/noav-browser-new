public final synthetic class Ld8 implements v1, wl, hu {
    public final synthetic byte a;
    public final synthetic com.example.instatool.browser.BrowserActivity b;

    public synthetic d8(com.example.instatool.browser.BrowserActivity p1, byte p2)
    {
        this.a = p2;
        this.b = p1;
        return;
    }

    public void a(Object p9)
    {
        x8 v2_0 = this.b;
        switch (this.a) {
            case 0:
                String v9_3 = ((u1) p9).b;
                x8 v2_3 = this.b;
                if (v9_3 != null) {
                    int v3_1 = v9_3.getStringExtra("url");
                    if (v3_1 != 0) {
                        cn v8_8 = ((p9) v2_3.C.c);
                        if (v8_8 != null) {
                            v8_8.e(v3_1);
                        } else {
                            com.example.instatool.browser.BrowserActivity.O(v2_3, v3_1, 0, 0, 0, 12);
                        }
                    }
                }
                cn v8_10 = v2_3.z;
                if (v8_10 == null) {
                    io.T("homeView");
                    throw 0;
                } else {
                    if (v8_10.e()) {
                        cn v8_12 = v2_3.z;
                        if (v8_12 == null) {
                            io.T("homeView");
                            throw 0;
                        } else {
                            v8_12.f();
                        }
                    }
                    return;
                }
            case 1:
                if (((android.net.Uri) p9) != null) {
                    cn v8_4 = v2_0.A().b();
                    v8_4.d.execute(new x8(v8_4, ((android.net.Uri) p9), new d8(v2_0, 3), 9));
                }
                return;
            case 2:
                cn v8_9 = v2_0.H;
                v2_0.H = 0;
                if (!((Boolean) p9).booleanValue()) {
                    cn v8_2 = v2_0.getString(2131689648);
                    v8_2.getClass();
                    v2_0.h0(v8_2);
                } else {
                    if (v8_9 != null) {
                        v8_9.a();
                    }
                }
                return;
            default:
                cn v8_13 = v2_0.G;
                if (v8_13 != null) {
                    v8_13.onReceiveValue(android.webkit.WebChromeClient$FileChooserParams.parseResult(((u1) p9).a, ((u1) p9).b));
                }
                v2_0.G = 0;
                return;
        }
    }

    public Object d(Object p11)
    {
        com.example.instatool.browser.BrowserActivity v1 = this.b;
        a50 v2 = a50.a;
        switch (this.a) {
            case 3:
                Class vtmp3 = ((iy) p11).getClass();
                throw 0;
                break;
            case 4:
            default:
                Class vtmp1 = ((String) p11).getClass();
                com.example.instatool.browser.BrowserActivity.O(this.b, ((String) p11), 0, 0, 0, 12);
                return v2;
            case 5:
                String v10_3 = ((Boolean) p11).booleanValue();
                int v11_2 = v1.A;
                if (v11_2 == 0) {
                    io.T("autoTool");
                    throw 0;
                } else {
                    int v11_6;
                    if (v11_2.k()) {
                        v11_6 = 1;
                    } else {
                        int v11_4 = v1.A;
                        if (v11_4 == 0) {
                            io.T("autoTool");
                            throw 0;
                        } else {
                            if (v11_4.g != bo.PAUSED) {
                                v11_6 = 0;
                            }
                        }
                    }
                    if ((v10_3 == null) || (v11_6 == 0)) {
                        String v10_5 = v1.getString(2131689919);
                        v10_5.getClass();
                        v1.h0(v10_5);
                    } else {
                        String v10_6 = v1.A;
                        if (v10_6 == null) {
                            io.T("autoTool");
                            throw 0;
                        } else {
                            v10_6.z();
                            String v10_8 = v1.getString(2131689907);
                            v10_8.getClass();
                            v1.h0(v10_8);
                        }
                    }
                    return v2;
                }
            case 6:
                Class vtmp5 = ((a50) p11).getClass();
                String v10_9 = v1.z;
                if (v10_9 == null) {
                    io.T("homeView");
                    throw 0;
                } else {
                    if (v10_9.e()) {
                        String v10_2 = v1.z;
                        if (v10_2 == null) {
                            io.T("homeView");
                            throw 0;
                        } else {
                            v10_2.f();
                        }
                    }
                    return v2;
                }
        }
    }

    public c90 k(android.view.View p9, c90 p10)
    {
        android.widget.LinearLayout v5_0;
        Class vtmp1 = p9.getClass();
        com.google.android.material.card.MaterialCardView v9_2 = p10.a;
        j8 v10_6 = v9_2.h(647);
        v10_6.getClass();
        int v0_0 = 8;
        int v1_1 = v9_2.h(8);
        v1_1.getClass();
        int v1_0 = v1_1.d;
        com.google.android.material.card.MaterialCardView v9_1 = v9_2.t(8);
        int v2 = v10_6.a;
        c90 v8_1 = this.b;
        v8_1.M = v2;
        int v3 = v10_6.b;
        v8_1.N = v3;
        int v4 = v10_6.c;
        v8_1.O = v4;
        j8 v10_1 = v10_6.d;
        if (v9_1 == null) {
            v5_0 = v10_1;
        } else {
            v5_0 = Math.max(v10_1, v1_0);
        }
        v8_1.P = v5_0;
        android.widget.LinearLayout v5_1 = v8_1.y;
        if (v5_1 == null) {
            io.T("binding");
            throw 0;
        } else {
            android.widget.LinearLayout v5_2 = v5_1.browserColumn;
            v5_2.getClass();
            if (v9_1 == null) {
                v1_0 = v10_1;
            }
            v5_2.setPadding(v2, v3, v4, v1_0);
            j8 v10_3 = v8_1.y;
            if (v10_3 == null) {
                io.T("binding");
                throw 0;
            } else {
                j8 v10_4 = v10_3.bottomBar;
                v10_4.getClass();
                if (v9_1 == null) {
                    v0_0 = 0;
                }
                v10_4.setVisibility(v0_0);
                if (v8_1.I == v9_1) {
                    com.google.android.material.card.MaterialCardView v9_3 = v8_1.y;
                    if (v9_3 == null) {
                        io.T("binding");
                        throw 0;
                    } else {
                        com.google.android.material.card.MaterialCardView v9_5 = v9_3.autoTool.getRoot();
                        v9_5.getClass();
                        if (v9_5.getVisibility() == 0) {
                            com.google.android.material.card.MaterialCardView v9_7 = v8_1.y;
                            if (v9_7 == null) {
                                io.T("binding");
                                throw 0;
                            } else {
                                v9_7.autoTool.getRoot().post(new j8(v8_1, 1));
                            }
                        }
                    }
                } else {
                    v8_1.I = v9_1;
                    v8_1.T();
                }
                return c90.b;
            }
        }
    }
}
