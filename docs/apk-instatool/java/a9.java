public final synthetic class La9 implements wl {
    public final synthetic byte a;
    public final synthetic Object b;
    public final synthetic boolean c;

    public synthetic a9(com.example.instatool.browser.BrowserActivity p1, boolean p2, byte p3)
    {
        this.a = p3;
        this.b = p1;
        this.c = p2;
        return;
    }

    public synthetic a9(String p2, boolean p3)
    {
        this.a = 2;
        this.c = p3;
        this.b = p2;
        return;
    }

    public final Object d(Object p11)
    {
        a50 v1 = a50.a;
        String v2_0 = 0;
        d90 v3_10 = 0;
        com.example.instatool.browser.BrowserActivity v5_2 = this.b;
        android.webkit.WebView v10_33 = this.c;
        switch (this.a) {
            case 0:
                com.example.instatool.browser.BrowserActivity v5_1 = ((com.example.instatool.browser.BrowserActivity) v5_2);
                Class vtmp2 = ((jt) p11).getClass();
                int v0_7 = v5_1.W;
                int v6_3 = v5_1.C;
                String v7_1 = ((p9) v6_3.c);
                switch (f9.a[((jt) p11).ordinal()]) {
                    case 1:
                        if (v7_1 == null) {
                        } else {
                            v5_1.A().a().c(new y8(v7_1.j, v7_1.c(), v10_33), new a9(v5_1, v10_33, 1));
                        }
                        break;
                    case 2:
                        android.webkit.WebView v10_22 = ((p9) v6_3.c);
                        if (v10_22 == null) {
                        } else {
                            android.webkit.WebView v10_23 = v10_22.i;
                            if (v10_23 != null) {
                                String v11_9 = v5_1.y;
                                if (v11_9 == null) {
                                    io.T("binding");
                                    throw 0;
                                } else {
                                    String v11_10 = v11_9.findBar;
                                    v11_10.getClass();
                                    v11_10.setVisibility(0);
                                    v10_23.setFindListener(new e9(v5_1));
                                    String v11_13 = v5_1.y;
                                    if (v11_13 == null) {
                                        io.T("binding");
                                        throw 0;
                                    } else {
                                        v11_13.findInput.requestFocus();
                                        String v11_15 = v5_1.getWindow();
                                        d90 v3_0 = v5_1.y;
                                        if (v3_0 == null) {
                                            io.T("binding");
                                            throw 0;
                                        } else {
                                            d90 v3_4;
                                            hv v4_1 = new hv(v3_0.findInput);
                                            d90 v3_2 = android.os.Build$VERSION.SDK_INT;
                                            if (v3_2 < 35) {
                                                if (v3_2 < 30) {
                                                    if (v3_2 < 26) {
                                                        v3_4 = new d90(v11_15, v4_1);
                                                    } else {
                                                        v3_4 = new e90(v11_15, v4_1);
                                                    }
                                                } else {
                                                    v3_4 = new f90(v11_15, v4_1);
                                                }
                                            } else {
                                                v3_4 = new g90(v11_15, v4_1);
                                            }
                                            v3_4.v(8);
                                            String v11_18 = v5_1.y;
                                            if (v11_18 == null) {
                                                io.T("binding");
                                                throw 0;
                                            } else {
                                                String v11_20 = v11_18.findInput.getText();
                                                if (v11_20 == null) {
                                                } else {
                                                    String v11_21 = v11_20.toString();
                                                    if (v11_21 == null) {
                                                    } else {
                                                        if (v11_21.length() > 0) {
                                                            v2_0 = v11_21;
                                                        }
                                                        if (v2_0 == null) {
                                                        } else {
                                                            v10_23.findAllAsync(v2_0);
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            } else {
                            }
                        }
                        break;
                    case 3:
                        if (v7_1 == null) {
                        } else {
                            v5_1.c0(v7_1.j, v7_1.k);
                        }
                        break;
                    case 4:
                        if (v7_1 == null) {
                        } else {
                            android.webkit.WebView v10_14 = v7_1.p;
                            String v11_7 = (v10_14 ^ 1);
                            if (v10_14 != v11_7) {
                                v7_1.p = v11_7;
                                v7_1.a(v7_1.i);
                                if ((v7_1.j.length() <= 0) || (v7_1.r != null)) {
                                } else {
                                    v7_1.i.reload();
                                }
                            } else {
                            }
                        }
                        break;
                    case 5:
                        v5_1.K(0);
                        break;
                    case 6:
                        v5_1.K(1);
                        break;
                    case 7:
                        android.webkit.WebView v10_10 = com.example.instatool.library.LibraryActivity$a.BOOKMARKS;
                        v10_10.getClass();
                        android.webkit.WebView v10_13 = new android.content.Intent(v5_1, com.example.instatool.library.LibraryActivity).putExtra("mode", v10_10.name());
                        v10_13.getClass();
                        v0_7.i0(v10_13);
                        break;
                    case 8:
                        android.webkit.WebView v10_7 = com.example.instatool.library.LibraryActivity$a.HISTORY;
                        v10_7.getClass();
                        android.webkit.WebView v10_9 = new android.content.Intent(v5_1, com.example.instatool.library.LibraryActivity).putExtra("mode", v10_7.name());
                        v10_9.getClass();
                        v0_7.i0(v10_9);
                        break;
                    case 9:
                        android.webkit.WebView v10_4 = com.example.instatool.library.LibraryActivity$a.DOWNLOADS;
                        v10_4.getClass();
                        android.webkit.WebView v10_6 = new android.content.Intent(v5_1, com.example.instatool.library.LibraryActivity).putExtra("mode", v10_4.name());
                        v10_6.getClass();
                        v0_7.i0(v10_6);
                        break;
                    case 10:
                        v5_1.b0((v5_1.A().c().C() ^ 1));
                        break;
                    case 11:
                        android.webkit.WebView v10_37 = new android.content.Intent;
                        v10_37(v5_1, com.example.instatool.browser.ManageAccountsActivity);
                        v5_1.startActivity(v10_37);
                        break;
                    case 12:
                        v5_1.d0();
                        break;
                    case 13:
                        android.webkit.WebView v10_34 = new cn;
                        v10_34(v5_1, v5_1.A().b(), new m8(v5_1, 7), new g9(2, v5_1, com.example.instatool.browser.BrowserActivity, "openExtensionPage", "openExtensionPage(Lcom/example/instatool/extensions/Extension;Ljava/lang/String;)V", 2));
                        String v11_37 = ((com.example.instatool.databinding.SheetExtensionsBinding) v10_34.f);
                        v11_37.installButton.setOnClickListener(new p8(v10_34, 3));
                        v10_34.g();
                        android.webkit.WebView v10_36 = ((z7) v10_34.e);
                        v10_36.setContentView(v11_37.getRoot());
                        v10_36.show();
                        break;
                    case 14:
                        android.webkit.WebView v10_32 = new s5;
                        v10_32(v5_1, v5_1.A().c(), new h9(0, v5_1, com.example.instatool.browser.BrowserActivity, "showClearData", "showClearData()V", 1));
                        v10_32.v();
                        break;
                    default:
                        android.webkit.WebView v10_26 = new uk;
                        v10_26();
                        throw v10_26;
                }
                return v1;
            case 1:
                android.webkit.WebView v10_11;
                com.example.instatool.browser.BrowserActivity v5_3 = ((com.example.instatool.browser.BrowserActivity) v5_2);
                Class vtmp4 = ((a50) p11).getClass();
                if (v10_33 == null) {
                    v10_11 = 2131689574;
                } else {
                    v10_11 = 2131689575;
                }
                android.webkit.WebView v10_24 = v5_3.getString(v10_11);
                v10_24.getClass();
                v5_3.h0(v10_24);
                android.webkit.WebView v10_25 = v5_3.z;
                if (v10_25 == null) {
                    io.T("homeView");
                    throw 0;
                } else {
                    if (v10_25.e()) {
                        android.webkit.WebView v10_31 = v5_3.z;
                        if (v10_31 == null) {
                            io.T("homeView");
                            throw 0;
                        } else {
                            v10_31.f();
                        }
                    }
                    return v1;
                }
            default:
                com.example.instatool.browser.BrowserActivity v5_0 = ((String) v5_2);
                Class vtmp1 = ((k9) p11).getClass();
                if (v10_33 != null) {
                    android.webkit.WebView v10_28 = ((k9) p11).getReadableDatabase().rawQuery("SELECT 1 FROM bookmarks WHERE url = ? LIMIT 1", new String[] {v5_0}));
                    try {
                        String v11_27 = v10_28.moveToFirst();
                        v10_28.close();
                    } catch (int v0_5) {
                        String v11_28 = v0_5;
                        try {
                            throw v11_28;
                        } catch (int v0_6) {
                            c8.i(v10_28, v11_28);
                            throw v0_6;
                        }
                    }
                    if (v11_27 != null) {
                        v3_10 = 1;
                    }
                }
                return Boolean.valueOf(v3_10);
        }
    }
}
