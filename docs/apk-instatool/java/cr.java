public final synthetic class Lcr implements ll {
    public final synthetic byte a;
    public final synthetic com.example.instatool.browser.ManageAccountsActivity b;

    public synthetic cr(com.example.instatool.browser.ManageAccountsActivity p1, byte p2)
    {
        this.a = p2;
        this.b = p1;
        return;
    }

    public final Object a()
    {
        a50 v3 = a50.a;
        int v9_4 = this.b;
        switch (this.a) {
            case 0:
                rr v0_5 = v9_4.B;
                java.util.ArrayList v4_1 = new java.util.ArrayList();
                rr v0_6 = v0_5.iterator();
                while (v0_6.hasNext()) {
                    er v5_17 = v0_6.next();
                    int v6_15 = ((nm) v5_17);
                    if ((v9_4.C.contains(Integer.valueOf(v6_15.a))) && (com.example.instatool.browser.ManageAccountsActivity.s(v6_15) == com.example.instatool.browser.ManageAccountsActivity$b.ISSUE)) {
                        v4_1.add(v5_17);
                    }
                }
                if (!v4_1.isEmpty()) {
                    rr v0_10 = new rr(v9_4);
                    v0_10.l(2131689738);
                    ((f2) v0_10.b).f = v9_4.getString(2131689737, new Object[] {Integer.valueOf(v4_1.size())}));
                    v0_10.k(2131689736, new er(v9_4, v4_1, 1));
                    v0_10.j(2131689596, 0);
                    v0_10.i();
                }
                return v3;
            case 1:
                rr v0_7 = v9_4.B;
                java.util.ArrayList v4_3 = new java.util.ArrayList();
                rr v0_1 = v0_7.iterator();
                while (v0_1.hasNext()) {
                    er v5_8 = v0_1.next();
                    if (v9_4.C.contains(Integer.valueOf(((nm) v5_8).a))) {
                        v4_3.add(v5_8);
                    }
                }
                if (!v4_3.isEmpty()) {
                    rr v0_4 = new rr(v9_4);
                    v0_4.l(2131689749);
                    ((f2) v0_4.b).f = v9_4.getString(2131689748, new Object[] {Integer.valueOf(v4_3.size())}));
                    v0_4.k(2131689638, new er(v9_4, v4_3, 0));
                    v0_4.j(2131689596, 0);
                    v0_4.i();
                }
                return v3;
            default:
                int v9_1 = v9_4.getApplication();
                v9_1.getClass();
                return ((com.example.instatool.InstaToolApp) v9_1);
        }
    }
}
