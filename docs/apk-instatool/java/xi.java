public final synthetic class Lxi implements android.widget.CompoundButton$OnCheckedChangeListener {
    public final synthetic cn a;
    public final synthetic ei b;
    public final synthetic com.example.instatool.databinding.ItemExtensionBinding c;

    public synthetic xi(cn p1, ei p2, com.example.instatool.databinding.ItemExtensionBinding p3)
    {
        this.a = p1;
        this.b = p2;
        this.c = p3;
        return;
    }

    public final void onCheckedChanged(android.widget.CompoundButton p7, boolean p8)
    {
        p7.getClass();
        cn v7_1 = this.a;
        ri v0_1 = ((ri) v7_1.b);
        ei v1 = this.b;
        String v2 = v1.a;
        if (v0_1.n(v1) != p8) {
            int v3_8 = v0_1.e;
            v3_8.getClass();
            int v3_0 = v3_8.edit();
            v3_0.getClass();
            v3_0.putBoolean("enabled:".concat(v2), p8);
            v3_0.apply();
            if (p8 == null) {
                v0_1.x(v2);
            } else {
                v0_1.w(v1);
            }
            if (p8 == null) {
                java.util.Iterator v8_2 = v0_1.o.values();
                v8_2.getClass();
                java.util.Iterator v8_3 = v8_2.iterator();
                while (v8_3.hasNext()) {
                    int v3_6;
                    int v3_3 = ((hi) v8_3.next());
                    v3_3.getClass();
                    if ((!v3_3.a.equals(v2)) || (!(v3_3.d instanceof mi))) {
                        v3_6 = 0;
                    } else {
                        v3_6 = 1;
                    }
                    if (v3_6 == 1) {
                        v8_3.remove();
                    }
                }
            }
            v0_1.s();
        }
        v7_1.i(this.c, v1);
        return;
    }
}
