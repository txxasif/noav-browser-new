public final synthetic class Ldr implements java.lang.Runnable {
    public final synthetic byte a;
    public final synthetic com.example.instatool.browser.ManageAccountsActivity b;
    public final synthetic java.io.Serializable c;

    public synthetic dr(com.example.instatool.browser.ManageAccountsActivity p1, java.io.Serializable p2, byte p3)
    {
        this.a = p3;
        this.b = p1;
        this.c = p2;
        return;
    }

    public final void run()
    {
        int v1_0 = 0;
        boolean v4_6 = this.c;
        com.google.android.material.button.MaterialButton v6_4 = this.b;
        switch (this.a) {
            case 0:
                String v0_16 = v6_4.y;
                if (v0_16 == null) {
                    io.T("binding");
                    throw 0;
                } else {
                    String v0_4 = v0_16.loading;
                    v0_4.getClass();
                    v0_4.setVisibility(8);
                    String v0_9 = iy.a(v4_6);
                    if (v0_9 != null) {
                        boolean v4_3 = v6_4.y;
                        if (!v4_3) {
                            io.T("binding");
                            throw 0;
                        } else {
                            boolean v4_4 = v4_3.tableScroll;
                            v4_4.getClass();
                            v4_4.setVisibility(8);
                            android.widget.TextView v2_3 = v6_4.y;
                            if (v2_3 == null) {
                                io.T("binding");
                                throw 0;
                            } else {
                                android.widget.TextView v2_4 = v2_3.empty;
                                v2_4.getClass();
                                v2_4.setVisibility(0);
                                android.widget.TextView v2_5 = v6_4.y;
                                if (v2_5 == null) {
                                    io.T("binding");
                                    throw 0;
                                } else {
                                    android.widget.TextView v2_6 = v2_5.empty;
                                    boolean v4_5 = v0_9.getMessage();
                                    if (!v4_5) {
                                        v4_5 = v0_9.getClass().getSimpleName();
                                    }
                                    v2_6.setText(v6_4.getString(2131689917, new Object[] {v4_5})));
                                    com.google.android.material.button.MaterialButton v6_5 = v6_4.y;
                                    if (v6_5 == null) {
                                        io.T("binding");
                                        throw 0;
                                    } else {
                                        v6_5.btnDownload.setEnabled(0);
                                    }
                                }
                            }
                        }
                    } else {
                        boolean v4_8 = ((java.util.List) v4_6);
                        String v0_14 = new java.util.ArrayList();
                        android.widget.TextView v2_7 = v4_8.iterator();
                        while (v2_7.hasNext()) {
                            java.util.ArrayList v3_5 = v2_7.next();
                            boolean v4_12 = ((nm) v3_5);
                            if ((!m10.G(v4_12.b)) || ((!m10.G(v4_12.c)) || ((!m10.G(v4_12.d)) || (!m10.G(v4_12.e))))) {
                                v0_14.add(v3_5);
                            }
                        }
                        v6_4.B = v0_14;
                        android.widget.TextView v2_8 = v6_4.C;
                        java.util.ArrayList v3_4 = new java.util.ArrayList(tb.e0(v0_14));
                        boolean v4_10 = v0_14.size();
                        while (v1_0 < v4_10) {
                            Integer v5_2 = v0_14.get(v1_0);
                            v1_0++;
                            v3_4.add(Integer.valueOf(((nm) v5_2).a));
                        }
                        v2_8.retainAll(rb.s0(v3_4));
                        v6_4.u();
                        v6_4.x();
                    }
                    return;
                }
            default:
                String v0_1 = v6_4.y;
                if (v0_1 == null) {
                    io.T("binding");
                    throw 0;
                } else {
                    String v0_2 = v0_1.loading;
                    v0_2.getClass();
                    v0_2.setVisibility(8);
                    String v0_3 = iy.a(v4_6);
                    if (v0_3 != null) {
                        android.widget.TextView v2_0 = v6_4.y;
                        if (v2_0 == null) {
                            io.T("binding");
                            throw 0;
                        } else {
                            android.widget.TextView v2_1 = v2_0.root;
                            String v0_5 = v0_3.getMessage();
                            if (v0_5 == null) {
                                v0_5 = "";
                            }
                            p00.h(v2_1, v6_4.getString(2131689754, new Object[] {v0_5})), 0).j();
                        }
                    } else {
                        android.widget.Toast.makeText(v6_4, v6_4.getString(2131689755, new Object[] {((String) v4_6)})), 1).show();
                    }
                    return;
                }
        }
    }
}
