public final synthetic class Lhb implements android.widget.AdapterView$OnItemClickListener {
    public final synthetic lx a;
    public final synthetic zh b;
    public final synthetic com.example.instatool.databinding.DialogClearDataBinding c;
    public final synthetic lx d;
    public final synthetic k9 e;
    public final synthetic com.example.instatool.browser.BrowserActivity f;

    public synthetic hb(lx p1, zh p2, com.example.instatool.databinding.DialogClearDataBinding p3, lx p4, k9 p5, com.example.instatool.browser.BrowserActivity p6)
    {
        this.a = p1;
        this.b = p2;
        this.c = p3;
        this.d = p4;
        this.e = p5;
        this.f = p6;
        return;
    }

    public final void onItemClick(android.widget.AdapterView p3, android.view.View p4, int p5, long p6)
    {
        lx v3_2;
        lx v3_5 = ((ai) this.b).get(p5);
        p4 = this.a;
        p4.a = v3_5;
        com.example.instatool.databinding.DialogClearDataBinding v5_1 = this.c;
        jb v7 = jb.ALL_TIME;
        int v0 = 0;
        if (v3_5 != v7) {
            v3_2 = 0;
        } else {
            v3_2 = 1;
        }
        v5_1.clearCookies.setChecked(v3_2);
        if (p4.a == v7) {
            v0 = 1;
        }
        v5_1.clearCache.setChecked(v0);
        p40.a0(v5_1, this.d, p4, this.e, this.f);
        return;
    }
}
