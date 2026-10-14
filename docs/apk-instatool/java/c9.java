public final synthetic class Lc9 implements java.lang.Runnable {
    public final synthetic byte a;
    public final synthetic boolean b;
    public final synthetic Object c;
    public final synthetic java.io.Serializable d;

    public synthetic c9(com.example.instatool.browser.BrowserActivity p2, boolean p3, String p4)
    {
        this.a = 0;
        this.c = p2;
        this.b = p3;
        this.d = p4;
        return;
    }

    public synthetic c9(eo p2, java.io.Serializable p3, boolean p4)
    {
        this.a = 1;
        this.c = p2;
        this.d = p3;
        this.b = p4;
        return;
    }

    public final void run()
    {
        java.util.Iterator v1_0 = this.b;
        Object v2_0 = this.d;
        com.example.instatool.browser.BrowserActivity v12_2 = this.c;
        switch (this.a) {
            case 0:
                boolean v0_1;
                com.example.instatool.browser.BrowserActivity v12_3 = ((com.example.instatool.browser.BrowserActivity) v12_2);
                if (v1_0 == null) {
                    v0_1 = 2131689645;
                } else {
                    v0_1 = 2131689649;
                }
                boolean v0_2 = v12_3.getString(v0_1, new Object[] {((String) v2_0)}));
                v0_2.getClass();
                v12_3.h0(v0_2);
                return;
            default:
                com.example.instatool.browser.BrowserActivity v12_1 = ((eo) v12_2);
                java.util.LinkedHashSet v3 = v12_1.J;
                if (v12_1.g == bo.LOADING) {
                    boolean v0_4 = iy.a(v2_0);
                    if (v0_4) {
                        if (v1_0 == null) {
                            v12_1.h(v0_4);
                        } else {
                            v12_1.C();
                        }
                    } else {
                        Object v2_1 = ((java.util.List) v2_0);
                        boolean v0_6 = new java.util.ArrayList();
                        java.util.Iterator v1_2 = v2_1.iterator();
                        while (v1_2.hasNext()) {
                            int v4_0 = v1_2.next();
                            boolean v5_1 = ((nm) v4_0);
                            if ((v5_1.a()) && (!jy.k(v5_1.b))) {
                                v0_6.add(v4_0);
                            }
                        }
                        java.util.Iterator v1_3 = v0_6.size();
                        boolean v5_4 = 0;
                        while (v5_4 < v1_3) {
                            boolean v6_4 = v0_6.get(v5_4);
                            v5_4++;
                            boolean v6_5 = ((nm) v6_4);
                            v12_1.M = (v12_1.M + 1);
                            v3.add(Integer.valueOf(v6_5.a));
                            java.util.Map v7_0 = java.util.Collections.singletonMap(Character.valueOf(67), v12_1.a.getString(2131689711, new Object[] {v6_5.b, Integer.valueOf(v6_5.a), v6_5.f})));
                            v7_0.getClass();
                            eo.r(v12_1, v6_5, v7_0);
                        }
                        boolean v0_8 = new java.util.ArrayList();
                        java.util.Iterator v1_4 = v2_1.iterator();
                        while (v1_4.hasNext()) {
                            Object v2_3 = v1_4.next();
                            boolean v5_6 = ((nm) v2_3);
                            if ((v5_6.a()) && ((jy.k(v5_6.b)) && (!v3.contains(Integer.valueOf(v5_6.a))))) {
                                v0_8.add(v2_3);
                            }
                        }
                        v12_1.s = v0_8;
                        v12_1.t = 0;
                        if (!v0_8.isEmpty()) {
                            v12_1.d();
                        } else {
                            v12_1.C();
                        }
                    }
                }
                return;
        }
    }
}
