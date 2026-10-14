public final synthetic class Lk8 implements ll {
    public final synthetic com.example.instatool.browser.BrowserActivity a;
    public final synthetic android.content.Intent b;
    public final synthetic String c;
    public final synthetic p9 d;

    public synthetic k8(com.example.instatool.browser.BrowserActivity p1, android.content.Intent p2, String p3, p9 p4)
    {
        this.a = p1;
        this.b = p2;
        this.c = p3;
        this.d = p4;
        return;
    }

    public final Object a()
    {
        com.example.instatool.browser.BrowserActivity v0 = this.a;
        try {
            v0.startActivity(this.b);
        } catch (android.content.ActivityNotFoundException) {
            String v1_1 = this.c;
            if (v1_1 != null) {
                if (!v1_1.startsWith("https://")) {
                    if (!v1_1.startsWith("http://")) {
                        p9 v3_2 = v0.getString(2131689874);
                        v3_2.getClass();
                        v0.h0(v3_2);
                    }
                }
                this.d.e(v1_1);
            }
        }
        return a50.a;
    }
}
