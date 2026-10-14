public final synthetic class Lfr implements java.lang.Runnable {
    public final synthetic byte a;
    public final synthetic com.example.instatool.browser.ManageAccountsActivity b;
    public final synthetic String c;
    public final synthetic java.util.ArrayList d;

    public synthetic fr(com.example.instatool.browser.ManageAccountsActivity p2, String p3, java.util.ArrayList p4)
    {
        this.a = 1;
        this.b = p2;
        this.c = p3;
        this.d = p4;
        return;
    }

    public synthetic fr(com.example.instatool.browser.ManageAccountsActivity p2, java.util.ArrayList p3, String p4)
    {
        this.a = 0;
        this.b = p2;
        this.d = p3;
        this.c = p4;
        return;
    }

    public final void run()
    {
        hy v1_0 = a50.a;
        int v2_0 = this.c;
        switch (this.a) {
            case 0:
                com.example.instatool.browser.ManageAccountsActivity v5 = this.b;
                java.util.ArrayList v8 = this.d;
                try {
                    hy v7_0 = v5.v(v8, 1);
                } catch (Throwable v0_1) {
                    v7_0 = new hy(v0_1);
                }
                if (!(v7_0 instanceof hy)) {
                    Throwable v10_5;
                    Throwable v10_4 = ((nm) rb.h0(v8));
                    if (v10_4 == null) {
                        v10_5 = 0;
                    } else {
                        v10_5 = v10_4.f;
                    }
                    if (v10_5 == null) {
                        v10_5 = "";
                    }
                    Throwable v0_5 = v5.r().d();
                    java.util.ArrayList v3_1 = new java.util.ArrayList(tb.e0(v8));
                    tn v4_1 = v8.size();
                    hy v6_0 = 0;
                    while (v6_0 < v4_1) {
                        int v9_0 = v8.get(v6_0);
                        v6_0++;
                        v3_1.add(Integer.valueOf(((nm) v9_0).a));
                    }
                    v0_5.c(v2_0, v10_5, v3_1);
                    v5.runOnUiThread(new tn(v5, v1_0, v7_0, v8, 1));
                } else {
                    Throwable v10_7 = new k3;
                    v10_7(v5, ((hy) v7_0), 13);
                    v5.runOnUiThread(v10_7);
                }
                return;
            default:
                java.util.ArrayList v3_2 = this.b;
                Throwable v10_8 = this.d;
                try {
                    v3_2.r().d().b(v2_0, v10_8);
                } catch (Throwable v0_10) {
                    v1_0 = new hy(v0_10);
                }
                v3_2.runOnUiThread(new x8(v3_2, v1_0, v10_8, 8));
                return;
        }
    }
}
