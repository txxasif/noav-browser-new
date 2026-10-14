public final synthetic class Lxn implements java.lang.Runnable {
    public final synthetic byte a;
    public final synthetic String b;
    public final synthetic Object c;
    public final synthetic Object d;
    public final synthetic Object e;
    public final synthetic Object f;

    public synthetic xn(eo p2, Object p3, ll p4, String p5, nm p6)
    {
        this.a = 0;
        this.c = p2;
        this.d = p3;
        this.e = p4;
        this.b = p5;
        this.f = p6;
        return;
    }

    public synthetic xn(j2 p2, com.example.instatool.databinding.DialogSheetConfigBinding p3, java.io.Serializable p4, com.example.instatool.browser.BrowserActivity p5, String p6)
    {
        this.a = 1;
        this.c = p2;
        this.d = p3;
        this.e = p4;
        this.f = p5;
        this.b = p6;
        return;
    }

    public final void run()
    {
        int v1_0 = 0;
        boolean v2_6 = this.b;
        int v3_5 = this.f;
        com.example.instatool.browser.BrowserActivity v4_1 = this.e;
        boolean v5_1 = this.d;
        ArithmeticException v7_6 = this.c;
        switch (this.a) {
            case 0:
                ArithmeticException v7_7 = ((eo) v7_6);
                com.example.instatool.browser.BrowserActivity v4_4 = ((ll) v4_1);
                int v3_0 = ((nm) v3_5);
                String v0_2 = v7_7.g;
                if ((v0_2 == bo.SAVING) || (v0_2 == bo.PAUSED)) {
                    String v0_8 = iy.a(v5_1);
                    if (v0_8 != null) {
                        if (v2_6) {
                            int v1_6 = v0_8.getMessage();
                            if (v1_6 == 0) {
                                v1_6 = v0_8.getClass().getSimpleName();
                            }
                            v7_7.h(new IllegalStateException(v7_7.a.getString(2131689538, new Object[] {v3_0.b, v2_6, v1_6}))));
                        } else {
                            v7_7.h(v0_8);
                        }
                    } else {
                        v7_7.O = 0;
                        v4_4.a();
                    }
                }
                return;
            default:
                boolean v5_0 = ((com.example.instatool.databinding.DialogSheetConfigBinding) v5_1);
                com.example.instatool.browser.BrowserActivity v4_2 = ((java.io.Serializable) v4_1);
                int v3_6 = ((com.example.instatool.browser.BrowserActivity) v3_5);
                if (((j2) v7_6).isShowing()) {
                    String v0_5;
                    v5_0.validateSheet.setEnabled(1);
                    ArithmeticException v7_5 = v5_0.sheetStatus;
                    String v0_13 = iy.a(v4_2);
                    if (v0_13 != null) {
                        int v1_9 = v0_13.getMessage();
                        if (v1_9 == 0) {
                            v1_9 = v0_13.getClass().getSimpleName();
                        }
                        String v0_16 = v3_6.getString(2131689917, new Object[] {v1_9}));
                        int v1_12 = new StringBuilder();
                        v1_12.append(v0_16);
                        v1_12.append("\n\n");
                        v1_12.append(v2_6);
                        v0_5 = v1_12.toString();
                    } else {
                        com.example.instatool.browser.BrowserActivity v4_3 = ((java.util.List) v4_2);
                        String v0_18 = v4_3.iterator();
                        while (v0_18.hasNext()) {
                            boolean v2_9 = v0_18.next();
                            boolean v5_3 = ((nm) v2_9);
                            if ((v5_3.a()) && (!jy.k(v5_3.b))) {
                            }
                            boolean v2_10 = ((nm) v2_9);
                            if (!v2_10) {
                                if (!v4_3.isEmpty()) {
                                    String v0_1 = v4_3.iterator();
                                    while (v0_1.hasNext()) {
                                        if (((nm) v0_1.next()).a()) {
                                            v1_0++;
                                            if (v1_0 < 0) {
                                                ArithmeticException v7_1 = new ArithmeticException;
                                                v7_1("Count overflow has happened.");
                                                throw v7_1;
                                            }
                                        }
                                        v0_5.getClass();
                                        v7_5.setText(v0_5);
                                        return;
                                    }
                                }
                                v0_5 = v3_6.getResources().getQuantityString(2131623939, v4_3.size(), new Object[] {Integer.valueOf(v4_3.size()), Integer.valueOf(v1_0)}));
                            } else {
                                v0_5 = v3_6.getString(2131689711, new Object[] {v2_10.b, Integer.valueOf(v2_10.a), v2_10.f}));
                            }
                        }
                        v2_9 = 0;
                    }
                }
                return;
        }
    }
}
