public final synthetic class Lgr implements android.view.View$OnClickListener {
    public final synthetic byte a;
    public final synthetic com.example.instatool.browser.ManageAccountsActivity b;

    public synthetic gr(com.example.instatool.browser.ManageAccountsActivity p1, byte p2)
    {
        this.a = p2;
        this.b = p1;
        return;
    }

    public final void onClick(android.view.View p4)
    {
        int v3_1 = this.b;
        switch (this.a) {
            case 0:
                v3_1.finish();
                return;
            case 1:
                v3_1.t();
                return;
            case 2:
                java.util.List v4_1 = v3_1.q();
                if (v4_1.isEmpty()) {
                    v4_1 = v3_1.B;
                }
                if (!v4_1.isEmpty()) {
                    k3 v1_2 = v3_1.y;
                    if (v1_2 == null) {
                        io.T("binding");
                        throw 0;
                    } else {
                        k3 v1_3 = v1_2.loading;
                        v1_3.getClass();
                        v1_3.setVisibility(0);
                        v3_1.A.execute(new k3(v3_1, v4_1, 12));
                    }
                }
                return;
            case 3:
                v3_1.p(new cr(v3_1, 0));
                return;
            default:
                v3_1.p(new cr(v3_1, 1));
                return;
        }
    }
}
