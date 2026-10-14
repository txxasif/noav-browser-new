public final synthetic class Ler implements android.content.DialogInterface$OnClickListener {
    public final synthetic byte a;
    public final synthetic com.example.instatool.browser.ManageAccountsActivity b;
    public final synthetic java.util.ArrayList c;

    public synthetic er(com.example.instatool.browser.ManageAccountsActivity p1, java.util.ArrayList p2, byte p3)
    {
        this.a = p3;
        this.b = p1;
        this.c = p2;
        return;
    }

    public final void onClick(android.content.DialogInterface p7, int p8)
    {
        String v2_1 = this.c;
        com.example.instatool.browser.ManageAccountsActivity v6_1 = this.b;
        switch (this.a) {
            case 0:
                String v7_3 = v6_1.E;
                if (v7_3 != null) {
                    com.example.instatool.databinding.ActivityManageAccountsBinding v3_0 = v6_1.y;
                    if (v3_0 == null) {
                        io.T("binding");
                        throw 0;
                    } else {
                        java.util.concurrent.ExecutorService v8_1 = v3_0.loading;
                        v8_1.getClass();
                        v8_1.setVisibility(0);
                        v6_1.A.execute(new fr(v6_1, v2_1, v7_3));
                    }
                }
                return;
            default:
                String v7_2 = new java.util.ArrayList(tb.e0(v2_1));
                com.example.instatool.databinding.ActivityManageAccountsBinding v3_2 = v2_1.size();
                int v4 = 0;
                while (v4 < v3_2) {
                    Integer v5_0 = v2_1.get(v4);
                    v4++;
                    v7_2.add(Integer.valueOf(((nm) v5_0).a));
                }
                String v2_0 = v6_1.E;
                if (v2_0 != null) {
                    com.example.instatool.databinding.ActivityManageAccountsBinding v3_3 = v6_1.y;
                    if (v3_3 == null) {
                        io.T("binding");
                        throw 0;
                    } else {
                        java.util.concurrent.ExecutorService v8_3 = v3_3.loading;
                        v8_3.getClass();
                        v8_3.setVisibility(0);
                        v6_1.A.execute(new fr(v6_1, v2_0, v7_2));
                    }
                }
                return;
        }
    }
}
