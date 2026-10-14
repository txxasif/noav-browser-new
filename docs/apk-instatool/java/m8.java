public final synthetic class Lm8 implements ll {
    public final synthetic byte a;
    public final synthetic com.example.instatool.browser.BrowserActivity b;

    public synthetic m8(com.example.instatool.browser.BrowserActivity p1, byte p2)
    {
        this.a = p2;
        this.b = p1;
        return;
    }

    public final Object a()
    {
        int v1_0 = 0;
        p9 v2_0 = 0;
        a50 v3 = a50.a;
        String v7_4 = this.b;
        switch (this.a) {
            case 0:
                String v7_8 = ((java.util.ArrayList) v7_4.C.b);
                String[] v0_5 = v7_8.size();
                while (v1_0 < v0_5) {
                    p9 v2_1 = v7_8.get(v1_0);
                    v1_0++;
                    p9 v2_2 = ((p9) v2_1);
                    if (v2_2.e.p() != v2_2.s) {
                        r6 v5_4;
                        android.webkit.WebView v4_2 = v2_2.i;
                        r6 v5_2 = v2_2.e.p();
                        v2_2.s = v5_2;
                        if (v5_2 == null) {
                            v5_4 = new r6(v2_2, 1);
                        } else {
                            v5_4 = new o9(v2_2);
                        }
                        v4_2.setWebViewClient(v5_4);
                    }
                }
                return v3;
            case 1:
                String v7_5 = ((p9) v7_4.C.c);
                if (v7_5 != null) {
                    v2_0 = v7_5.i;
                }
                return v2_0;
            case 2:
                v7_4.g0();
                return v3;
            case 3:
                v7_4.J = 0;
                v7_4.T();
                return v3;
            case 4:
                String[] v0_4 = v7_4.A;
                if (v0_4 == null) {
                    io.T("autoTool");
                    throw 0;
                } else {
                    v0_4.z();
                    v7_4.T();
                    return v3;
                }
            case 5:
                v7_4.g0();
                return v3;
            case 6:
                v7_4.startActivity(new android.content.Intent(v7_4, com.example.instatool.browser.ManageAccountsActivity));
                return v3;
            case 7:
                v7_4.X.i0(new String[] {"application/zip", "application/x-chrome-extension", "application/octet-stream"}));
                return v3;
            default:
                String v7_10 = v7_4.getApplication();
                v7_10.getClass();
                return ((com.example.instatool.InstaToolApp) v7_10);
        }
    }
}
