public final synthetic class Li8 implements android.view.View$OnClickListener {
    public final synthetic byte a;
    public final synthetic com.example.instatool.browser.BrowserActivity b;

    public synthetic i8(com.example.instatool.browser.BrowserActivity p1, byte p2)
    {
        this.a = p2;
        this.b = p1;
        return;
    }

    public final void onClick(android.view.View p14)
    {
        int v2_13 = "";
        long v4_3 = 0;
        boolean v5_2 = 1;
        String v6 = 0;
        bo v7_6 = this.b;
        switch (this.a) {
            case 0:
                String v13_88 = ((p9) v7_6.C.c);
                if (v13_88 != null) {
                    String v13_89 = v13_88.i;
                    if (v13_89 != null) {
                        v13_89.findNext(1);
                    }
                }
                return;
            case 1:
                String v13_84 = ((p9) v7_6.C.c);
                if (v13_84 != null) {
                    String v13_85 = v13_84.i;
                    if (v13_85 != null) {
                        v13_85.findNext(0);
                    }
                }
                return;
            case 2:
                v7_6.s();
                return;
            case 3:
                v7_6.B(0);
                return;
            case 4:
                String v13_79 = ((p9) v7_6.C.c);
                if (v13_79 != null) {
                    if (!v13_79.i.canGoBackOrForward(1)) {
                        v13_79 = 0;
                    }
                    if (v13_79 != null) {
                        v13_79.o = 0;
                        v13_79.i.goBackOrForward(1);
                    }
                }
                return;
            case 5:
                v7_6.F(v7_6.D());
                return;
            case 6:
                String v13_44 = v7_6.C;
                java.util.ArrayList v14_31 = ((p9) v13_44.c);
                if (v14_31 != null) {
                    v7_6.q(v14_31);
                }
                String v0_45 = v7_6.A().d;
                if (v0_45 == null) {
                    io.T("favicons");
                    throw 0;
                } else {
                    java.util.ArrayList v14_34 = new u20(v7_6, v13_44, v0_45, new o70(v7_6, 10));
                    String v13_46 = new z7;
                    v13_46(v7_6);
                    v14_34.e = v13_46;
                    String v13_48 = com.example.instatool.databinding.SheetTabsBinding.inflate(android.view.LayoutInflater.from(v7_6));
                    v13_48.getClass();
                    v14_34.f = v13_48;
                    String v13_52 = (v7_6.getResources().getConfiguration().screenWidthDp / 180);
                    if (v13_52 < 2) {
                        v13_52 = 2;
                    }
                    int v1_34 = v14_34.f;
                    if (v1_34 == 0) {
                        io.T("binding");
                        throw 0;
                    } else {
                        v1_34.tabsList.setLayoutManager(new androidx.recyclerview.widget.GridLayoutManager(v13_52));
                        String v13_53 = v14_34.f;
                        if (v13_53 == null) {
                            io.T("binding");
                            throw 0;
                        } else {
                            v13_53.tabsList.setAdapter(v14_34.h);
                            String v13_55 = new no;
                            v13_55(new t20(v14_34));
                            int v1_39 = v14_34.f;
                            if (v1_39 == 0) {
                                io.T("binding");
                                throw 0;
                            } else {
                                int v1_40 = v1_39.tabsList;
                                boolean v3_20 = v13_55.r;
                                if (v3_20 != v1_40) {
                                    bo v7_3 = v13_55.z;
                                    if (v3_20) {
                                        v3_20.a0(v13_55);
                                        boolean v3_21 = v13_55.r;
                                        v3_21.q.remove(v7_3);
                                        if (v3_21.r == v7_3) {
                                            v3_21.r = 0;
                                        }
                                        boolean v3_23 = v13_55.r.C;
                                        if (v3_23) {
                                            v3_23.remove(v13_55);
                                        }
                                        boolean v3_24 = v13_55.p;
                                        bo v8_7 = (v3_24.size() - 1);
                                        while (v8_7 >= null) {
                                            String v9_3 = ((ko) v3_24.get(0));
                                            v9_3.g.cancel();
                                            t20.b(v9_3.e);
                                            v8_7--;
                                        }
                                        v3_24.clear();
                                        v13_55.w = 0;
                                        boolean v3_25 = v13_55.t;
                                        if (v3_25) {
                                            v3_25.recycle();
                                            v13_55.t = 0;
                                        }
                                        boolean v3_26 = v13_55.y;
                                        if (v3_26) {
                                            v3_26.a = 0;
                                            v13_55.y = 0;
                                        }
                                        if (v13_55.x != null) {
                                            v13_55.x = 0;
                                        }
                                    }
                                    v13_55.r = v1_40;
                                    if (v1_40 != 0) {
                                        int v1_41 = v1_40.getResources();
                                        v13_55.f = v1_41.getDimension(2131099806);
                                        v13_55.g = v1_41.getDimension(2131099805);
                                        v13_55.q = android.view.ViewConfiguration.get(v13_55.r.getContext()).getScaledTouchSlop();
                                        v13_55.r.h(v13_55);
                                        v13_55.r.q.add(v7_3);
                                        int v1_50 = v13_55.r;
                                        boolean v3_31 = v1_50.C;
                                        if (!v3_31) {
                                            v3_31 = new java.util.ArrayList();
                                            v1_50.C = v3_31;
                                        }
                                        v3_31.add(v13_55);
                                        v13_55.y = new mo(v13_55);
                                        v13_55.x = new android.view.GestureDetector(v13_55.r.getContext(), v13_55.y);
                                    }
                                }
                                String v13_57 = v14_34.f;
                                if (v13_57 == null) {
                                    io.T("binding");
                                    throw 0;
                                } else {
                                    String v13_58 = v13_57.tabsBadge;
                                    v13_58.getClass();
                                    int v1_55 = v14_34.f;
                                    if (v1_55 == 0) {
                                        io.T("binding");
                                        throw 0;
                                    } else {
                                        hz.s(v13_58, p40.x(v1_55.getRoot(), 2130903320));
                                        String v13_59 = v14_34.f;
                                        if (v13_59 == null) {
                                            io.T("binding");
                                            throw 0;
                                        } else {
                                            v13_59.newTabButton.setOnClickListener(new o20(v14_34, 0));
                                            String v13_61 = v14_34.f;
                                            if (v13_61 == null) {
                                                io.T("binding");
                                                throw 0;
                                            } else {
                                                v13_61.newIncognitoButton.setOnClickListener(new o20(v14_34, 1));
                                                String v13_63 = v14_34.f;
                                                if (v13_63 == null) {
                                                    io.T("binding");
                                                    throw 0;
                                                } else {
                                                    v13_63.closeAllButton.setOnClickListener(new o20(v14_34, 2));
                                                    v14_34.b();
                                                    String v13_66 = v14_34.e;
                                                    if (v13_66 == null) {
                                                        io.T("dialog");
                                                        throw 0;
                                                    } else {
                                                        int v1_64 = v14_34.f;
                                                        if (v1_64 == 0) {
                                                            io.T("binding");
                                                            throw 0;
                                                        } else {
                                                            v13_66.setContentView(v1_64.getRoot());
                                                            String v13_67 = v14_34.e;
                                                            if (v13_67 == null) {
                                                                io.T("dialog");
                                                                throw 0;
                                                            } else {
                                                                if (v13_67.f == null) {
                                                                    v13_67.i();
                                                                }
                                                                v13_67.f.N(3);
                                                                String v13_70 = v14_34.e;
                                                                if (v13_70 == null) {
                                                                    io.T("dialog");
                                                                    throw 0;
                                                                } else {
                                                                    v13_70.show();
                                                                    String v13_73 = ((p9) v14_34.b.c);
                                                                    if (v13_73 != null) {
                                                                        String v0_50 = v14_34.f;
                                                                        if (v0_50 == null) {
                                                                            io.T("binding");
                                                                            throw 0;
                                                                        } else {
                                                                            String v0_51 = v0_50.tabsList;
                                                                            String v13_74 = v14_34.g.indexOf(v13_73);
                                                                            if (v13_74 >= null) {
                                                                                v6 = v13_74;
                                                                            }
                                                                            v0_51.e0(v6);
                                                                        }
                                                                    }
                                                                    return;
                                                                }
                                                            }
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            case 7:
                String v13_43 = ((p9) v7_6.C.c);
                if (v13_43 != null) {
                    v4_3 = v13_43.j;
                }
                if (v4_3 != 0) {
                    v2_13 = v4_3;
                }
                if (((!v2_13.startsWith("http://")) && (!v2_13.startsWith("https://"))) || (vm.a(v2_13))) {
                    v5_2 = 0;
                }
                v7_6.A().a().c(new a9(v2_13, v5_2), new y8(v13_43, v5_2, v7_6));
                return;
            case 8:
                String v13_33 = ((p9) v7_6.C.c);
                if (v13_33 != null) {
                    v4_3 = v13_33.j;
                }
                if (v4_3 != 0) {
                    v2_13 = v4_3;
                }
                if (((v13_33 == null) || ((!v2_13.startsWith("http://")) && (!v2_13.startsWith("https://")))) || (vm.a(v2_13))) {
                    java.util.ArrayList v14_17 = 0;
                } else {
                    v14_17 = 1;
                }
                String v0_41 = new java.util.ArrayList();
                if ((v13_33 != null) && (v14_17 != null)) {
                    int v1_21 = v7_6.getString(2131689953);
                    v1_21.getClass();
                    v0_41.add(new vu(v1_21, new s8(v7_6, v2_13, v13_33, 0)));
                    int v1_23 = v7_6.getString(2131689954);
                    v1_23.getClass();
                    String v13_34 = new vu;
                    v13_34(v1_23, new s8(v7_6, v2_13, v13_33, 1));
                    v0_41.add(v13_34);
                }
                java.util.ArrayList v14_19;
                String v13_36 = v7_6.getString(2131689697);
                v13_36.getClass();
                v0_41.add(new vu(v13_36, new m8(v7_6, 5)));
                String v13_39 = v7_6.getString(2131689733);
                v13_39.getClass();
                v0_41.add(new vu(v13_39, new m8(v7_6, 6)));
                String v13_40 = new rr;
                v13_40(v7_6);
                int v1_29 = ((f2) v13_40.b);
                if (v14_17 == null) {
                    v14_19 = v7_6.getString(2131689926);
                    v14_19.getClass();
                } else {
                    v14_19 = d50.a(v2_13);
                }
                v1_29.d = v14_19;
                java.util.ArrayList v14_21 = new java.util.ArrayList(tb.e0(v0_41));
                int v2_17 = v0_41.size();
                boolean v3_17 = 0;
                while (v3_17 < v2_17) {
                    long v4_6 = v0_41.get(v3_17);
                    v3_17++;
                    v14_21.add(((String) ((vu) v4_6).a));
                }
                int v2_18 = new String[0];
                java.util.ArrayList v14_23 = ((CharSequence[]) v14_21.toArray(v2_18));
                int v2_20 = new t8(v0_41, 0);
                v1_29.m = v14_23;
                v1_29.o = v2_20;
                v13_40.i();
                return;
            case 9:
                String v13_27 = ((p9) v7_6.C.c);
                if (v13_27 != null) {
                    if (!v13_27.n) {
                        java.util.ArrayList v14_12 = v13_27.r;
                        if (v14_12 == null) {
                            if (v13_27.o == null) {
                                v13_27.i.reload();
                            } else {
                                v13_27.g();
                            }
                        } else {
                            v13_27.e(v14_12);
                        }
                    } else {
                        v13_27.i.stopLoading();
                    }
                }
                return;
            case 10:
                bo v7_4 = this.b;
                String v13_56 = v7_4.T;
                if (((v13_56 == null) || (v13_56.c != 1)) && ((v13_56 == null) || (v13_56.f != 1))) {
                    String v13_4 = m10.P(v7_4.A().c().F()).toString();
                    if (v13_4.length() != 0) {
                        java.util.ArrayList v14_43 = java.util.regex.Pattern.compile("/spreadsheets/d/([a-zA-Z0-9-_]+)");
                        v14_43.getClass();
                        java.util.ArrayList v14_44 = v14_43.matcher(v13_4);
                        v14_44.getClass();
                        java.util.ArrayList v14_45 = io.o(v14_44, 0, v13_4);
                        if (v14_45 == null) {
                            java.util.ArrayList v14_47 = java.util.regex.Pattern.compile("[a-zA-Z0-9-_]{20,}");
                            v14_47.getClass();
                            if (!v14_47.matcher(v13_4).matches()) {
                                v13_4 = 0;
                            }
                        } else {
                            v13_4 = ((String) ((pr) v14_45.a()).get(1));
                        }
                    }
                    if (v13_4 != null) {
                        java.util.ArrayList v14_2 = new pz();
                        if (((android.content.SharedPreferences) v7_4.A().c().b).getBoolean("auto_cookies", 1)) {
                            v14_2.add(ao.COOKIES);
                        }
                        if (((android.content.SharedPreferences) v7_4.A().c().b).getBoolean("auto_two_factor", 0)) {
                            v14_2.add(ao.TWO_FACTOR);
                        }
                        String v0_14 = v14_2.a;
                        v0_14.b();
                        if (v0_14.i <= 0) {
                            v14_2 = pz.b;
                        }
                        if (!v14_2.a.isEmpty()) {
                            String v0_20 = ((p9) v7_4.C.c);
                            if ((v0_20 == null) || (v0_20.c)) {
                                com.example.instatool.browser.BrowserActivity.O(v7_4, "https://www.instagram.com/", 0, 0, 0, 12);
                            }
                            String v0_24 = new pz();
                            if (((android.content.SharedPreferences) v7_4.A().c().b).getBoolean("auto_photo_boy", 0)) {
                                v0_24.add(mv.BOY);
                            }
                            if (((android.content.SharedPreferences) v7_4.A().c().b).getBoolean("auto_photo_girl", 0)) {
                                v0_24.add(mv.GIRL);
                            }
                            int v1_16 = v0_24.a;
                            v1_16.b();
                            if (v1_16.i <= 0) {
                                v0_24 = pz.b;
                            }
                            int v1_18 = v7_4.A;
                            if (v1_18 == 0) {
                                io.T("autoTool");
                                throw 0;
                            } else {
                                int v2_6 = ((android.content.SharedPreferences) v7_4.A().c().b).getBoolean("auto_custom_username", 0);
                                boolean v3_5 = ((android.content.SharedPreferences) v7_4.A().c().b).getBoolean("auto_follow", 0);
                                v0_24.getClass();
                                bo v7_1 = v1_18.a;
                                if (io.d(v7_1.getPackageName(), "com.example.instatool")) {
                                    if (v1_18.g != bo.PAUSED) {
                                        if (v14_2.a.isEmpty()) {
                                            e6.g("Failed requirement.");
                                        } else {
                                            v1_18.e();
                                            v1_18.k = v13_4;
                                            v1_18.l = v14_2;
                                            v1_18.m = v0_24;
                                            v1_18.o = v2_6;
                                            v1_18.p = v3_5;
                                            v1_18.c0 = 0;
                                            v1_18.s = qh.a;
                                            v1_18.t = 0;
                                            v1_18.I = 0;
                                            v1_18.N = 0;
                                            v1_18.J.clear();
                                            v1_18.K = 0;
                                            v1_18.L = 0;
                                            v1_18.M = 0;
                                            v1_18.m(0);
                                        }
                                    } else {
                                        String v13_8 = v1_18.u;
                                        v1_18.u = 0;
                                        java.util.ArrayList v14_8 = ((nm) rb.i0(v1_18.s, v1_18.t));
                                        if ((v13_8 != bo.LOADING) && (v14_8 != null)) {
                                            String v0_27 = bo.SAVING;
                                            if (v13_8 != v0_27) {
                                                if ((!v1_18.a0) || (!v1_18.H)) {
                                                    if ((!v1_18.V) || (!v1_18.H)) {
                                                        if ((!v1_18.O) || (!v1_18.H)) {
                                                            String v0_34 = bo.FILLING;
                                                            if (((v13_8 != v0_34) && (v13_8 != bo.WAITING)) || (!v1_18.H)) {
                                                                v1_18.d();
                                                            } else {
                                                                String v13_13;
                                                                v1_18.w = 0;
                                                                String v13_12 = ((co) rb.i0(eo.n0, v1_18.v));
                                                                if (v13_12 == null) {
                                                                    v13_13 = v1_18.G;
                                                                } else {
                                                                    v13_13 = v13_12.a;
                                                                }
                                                                v1_18.x(v0_34, v1_18.E(v13_13));
                                                                v1_18.v(v14_8);
                                                            }
                                                        } else {
                                                            v1_18.P = (System.currentTimeMillis() + 480000);
                                                            v1_18.x(bo.FILLING, v1_18.E(v1_18.G));
                                                            v1_18.B(v14_8);
                                                        }
                                                    } else {
                                                        v1_18.Y = (System.currentTimeMillis() + 60000);
                                                        v1_18.x(bo.FILLING, v1_18.j(v14_8));
                                                        v1_18.i(v14_8);
                                                    }
                                                } else {
                                                    v1_18.b0 = (System.currentTimeMillis() + 45000);
                                                    v1_18.x(bo.FILLING, v1_18.E(2131689546));
                                                    v1_18.s(v14_8);
                                                }
                                            } else {
                                                v1_18.x(v0_27, v1_18.t(2131689548));
                                            }
                                        } else {
                                            v1_18.m(1);
                                        }
                                    }
                                } else {
                                    java.util.ArrayList v14_10 = v7_1.getString(2131689946);
                                    v14_10.getClass();
                                    v1_18.x(bo.ERROR, v14_10);
                                }
                            }
                        } else {
                            String v13_22 = v7_4.getString(2131689517);
                            v13_22.getClass();
                            v7_4.h0(v13_22);
                            v7_4.g0();
                        }
                    } else {
                        String v13_24 = v7_4.getString(2131689918);
                        v13_24.getClass();
                        v7_4.h0(v13_24);
                        v7_4.g0();
                    }
                } else {
                    v7_4.f0(v13_56);
                }
                return;
            case 11:
                String v13_37 = v7_6.A;
                if (v13_37 == null) {
                    io.T("autoTool");
                    throw 0;
                } else {
                    if (v13_37.k()) {
                        v13_37.e();
                        v13_37.u = v13_37.g;
                        v13_37.x(bo.PAUSED, v13_37.t(2131689545));
                    }
                    return;
                }
            case 12:
                String v13_28 = v7_6.A;
                if (v13_28 == null) {
                    io.T("autoTool");
                    throw 0;
                } else {
                    v13_28.z();
                    return;
                }
            case 13:
                v7_6.J = 1;
                v7_6.T();
                return;
            case 14:
                v7_6.J = 0;
                v7_6.T();
                return;
            case 15:
                v7_6.b0(0);
                return;
            case 16:
                String v13_1 = v7_6.W;
                java.util.ArrayList v14_3 = com.example.instatool.library.LibraryActivity$a.DOWNLOADS;
                v14_3.getClass();
                java.util.ArrayList v14_5 = new android.content.Intent(v7_6, com.example.instatool.library.LibraryActivity).putExtra("mode", v14_3.name());
                v14_5.getClass();
                v13_1.i0(v14_5);
                return;
            default:
                String v13_92 = ((p9) v7_6.C.c);
                if (v13_92 != null) {
                    v13_92.g();
                }
                return;
        }
    }
}
