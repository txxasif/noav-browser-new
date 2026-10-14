public final synthetic class Lvn implements java.lang.Runnable {
    public final synthetic byte a;
    public final synthetic String b;
    public final synthetic String c;
    public final synthetic Object d;
    public final synthetic Object e;
    public final synthetic Object f;
    public final synthetic Object g;

    public synthetic vn(com.example.instatool.browser.BrowserActivity p2, pm p3, String p4, j2 p5, com.example.instatool.databinding.DialogSheetConfigBinding p6, String p7)
    {
        this.a = 1;
        this.d = p2;
        this.e = p3;
        this.b = p4;
        this.f = p5;
        this.g = p6;
        this.c = p7;
        return;
    }

    public synthetic vn(eo p2, String p3, nm p4, java.util.Map p5, ll p6, String p7)
    {
        this.a = 0;
        this.d = p2;
        this.b = p3;
        this.e = p4;
        this.f = p5;
        this.g = p6;
        this.c = p7;
        return;
    }

    public final void run()
    {
        eo v1_0 = this.g;
        hy v2_0 = this.f;
        hy v3_1 = this.b;
        String v4_2 = this.e;
        nm v5_1 = this.d;
        switch (this.a) {
            case 0:
                nm v5_2 = ((eo) v5_1);
                String v4_3 = ((nm) v4_2);
                hy v2_3 = ((java.util.Map) v2_0);
                eo v1_1 = ((ll) v1_0);
                xn v0_1 = 0;
                while(true) {
                    android.os.Handler v6_0 = v5_2.b;
                    int v7_0 = v4_3.a;
                    if (v0_1 >= 4) {
                        break;
                    }
                    v6_0.g(v3_1, v7_0, v2_3);
                    hy v2_2 = a50.a;
                    v5_2.i.post(new xn(v5_2, v2_2, v1_1, this.c, v4_3));
                    return;
                    Thread.sleep(4000);
                    v0_1++;
                }
                v6_0.g(v3_1, v7_0, v2_3);
            default:
                com.example.instatool.browser.BrowserActivity v10_1 = ((com.example.instatool.browser.BrowserActivity) v5_1);
                int v7_2 = ((j2) v2_0);
                int v8_2 = ((com.example.instatool.databinding.DialogSheetConfigBinding) v1_0);
                try {
                    xn v0_6 = ((pm) v4_2).e(v3_1);
                } catch (xn v0_7) {
                    v0_6 = new hy(v0_7);
                }
                v10_1.runOnUiThread(new xn(v7_2, v8_2, ((java.io.Serializable) v0_6), v10_1, this.c));
                return;
        }
    }
}
