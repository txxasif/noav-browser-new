public final synthetic class Lq8 implements wl, am {
    public final synthetic byte a;
    public final synthetic Object b;
    public final synthetic Object c;

    public synthetic q8(com.example.instatool.databinding.DialogClearDataBinding p2, com.example.instatool.browser.BrowserActivity p3)
    {
        this.a = 1;
        this.c = p2;
        this.b = p3;
        return;
    }

    public synthetic q8(Object p1, Object p2, byte p3)
    {
        this.a = p3;
        this.b = p1;
        this.c = p2;
        return;
    }

    public Object c(Object p7, Object p8)
    {
        a50 v1 = a50.a;
        o7 v3_1 = this.c;
        cn v6_2 = this.b;
        switch (this.a) {
            case 2:
                cn v6_3 = ((cn) v6_2);
                o7 v3_2 = ((o7) v3_1);
                ((String) p7).getClass();
                ((String) p8).getClass();
                ((k9) v6_3.b).c(new ym(v3_2, ((String) p7), ((String) p8), 0), new xm(v6_3, 1));
                return v1;
            default:
                cn v6_1 = ((com.example.instatool.library.LibraryActivity) v6_2);
                o7 v3_0 = ((o7) v3_1);
                Class vtmp1 = ((String) p7).getClass();
                ((String) p8).getClass();
                v6_1.p().c(new ym(v3_0, ((String) p7), ((String) p8), 1), new ap(v6_1, 5));
                return v1;
        }
    }

    public Object d(Object p6)
    {
        a50 v1 = a50.a;
        com.example.instatool.browser.BrowserActivity v2_1 = this.b;
        String v5_3 = this.c;
        switch (this.a) {
            case 0:
                com.example.instatool.browser.BrowserActivity v2_3 = ((com.example.instatool.browser.BrowserActivity) v2_1);
                String v5_4 = ((String) v5_3);
                Class vtmp5 = ((String) p6).getClass();
                v2_3.D.execute(new x8(v2_3, v5_4, ((String) p6), 0));
                return v1;
            default:
                ((com.example.instatool.databinding.DialogClearDataBinding) v5_3).historySummary.setText(((com.example.instatool.browser.BrowserActivity) v2_1).getResources().getQuantityString(2131623936, ((Integer) p6).intValue(), new Object[] {((Integer) p6)})));
                return v1;
        }
    }
}
