public final synthetic class Lu8 implements android.view.View$OnTouchListener {
    public final synthetic com.example.instatool.browser.BrowserActivity a;
    public final synthetic jx b;
    public final synthetic jx c;
    public final synthetic jx d;
    public final synthetic jx e;
    public final synthetic ix f;
    public final synthetic int g;
    public final synthetic ll h;

    public synthetic u8(com.example.instatool.browser.BrowserActivity p1, jx p2, jx p3, jx p4, jx p5, ix p6, int p7, ll p8)
    {
        this.a = p1;
        this.b = p2;
        this.c = p3;
        this.d = p4;
        this.e = p5;
        this.f = p6;
        this.g = p7;
        this.h = p8;
        return;
    }

    public final boolean onTouch(android.view.View p11, android.view.MotionEvent p12)
    {
        p11 = this.a;
        com.google.android.material.card.MaterialCardView v0_0 = p11.y;
        if (v0_0 == null) {
            io.T("binding");
            throw 0;
        } else {
            com.google.android.material.card.MaterialCardView v0_2 = v0_0.autoTool.getRoot();
            v0_2.getClass();
            float v1_0 = p12.getActionMasked();
            int v2_0 = this.b;
            float v3_0 = this.c;
            jx v4 = this.d;
            jx v5 = this.e;
            ix v6 = this.f;
            if (v1_0 == 0) {
                v2_0.a = p12.getRawX();
                v3_0.a = p12.getRawY();
                v4.a = p11.K;
                v5.a = p11.L;
                v6.a = 0;
                return 1;
            } else {
                if (v1_0 == 1) {
                    if (!v6.a) {
                        this.h.a();
                        return 1;
                    } else {
                        p11.r(v0_2);
                        return 1;
                    }
                } else {
                    if (v1_0 == 2) {
                        float v1_2 = (p12.getRawX() - v2_0.a);
                        float v12_3 = (p12.getRawY() - v3_0.a);
                        int v2_3 = v6.a;
                        if ((v2_3 == 0) && (((v12_3 * v12_3) + (v1_2 * v1_2)) > ((float) (this.g * this.g)))) {
                            v6.a = 1;
                            v2_3 = 1;
                        }
                        if (v2_3 != 0) {
                            p11.K = (v4.a + v1_2);
                            p11.L = (v5.a + v12_3);
                            p11.r(v0_2);
                        }
                    } else {
                        if (v1_0 == 3) {
                            if (v6.a) {
                                p11.r(v0_2);
                                return 1;
                            }
                        } else {
                            return 0;
                        }
                    }
                    return 1;
                }
            }
        }
    }
}
