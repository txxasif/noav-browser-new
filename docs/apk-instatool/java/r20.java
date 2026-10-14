public final class Lr20 extends fw {
    public final synthetic u20 c;

    public r20(u20 p1)
    {
        this.c = p1;
        return;
    }

    public static void d(com.example.instatool.databinding.ItemTabBinding p1, android.graphics.Bitmap p2, int p3, int p4)
    {
        android.content.res.ColorStateList v0_0 = p1.tabIcon;
        if (p2 == null) {
            v0_0.setImageResource(p3);
            p1.tabIcon.setImageTintList(android.content.res.ColorStateList.valueOf(p4));
            p1.tabPlaceholder.setImageResource(p3);
            p1.tabPlaceholder.setImageTintList(android.content.res.ColorStateList.valueOf(p4));
            return;
        } else {
            v0_0.setImageTintList(0);
            p1.tabIcon.setImageBitmap(p2);
            p1.tabPlaceholder.setImageTintList(0);
            p1.tabPlaceholder.setImageBitmap(p2);
            return;
        }
    }

    public final int a()
    {
        return this.c.g.size();
    }

    public final void b(fx p11, int p12)
    {
        float v5_4;
        u20 v11_1 = this.c;
        jj v7 = v11_1.c;
        android.content.Context v8 = v11_1.a;
        p9 v2_1 = ((p9) v11_1.g.get(p12));
        com.example.instatool.databinding.ItemTabBinding v4 = ((s20) p11).t;
        ((s20) p11).u = v2_1;
        q20 v0_6 = v2_1.c;
        int v12_7 = vm.a(v2_1.j);
        com.google.android.material.card.MaterialCardView v3_4 = v4.tabTitle;
        if (v12_7 == 0) {
            int v6_0 = v2_1.c();
            if (!m10.G(v6_0)) {
                v5_4 = v6_0;
            } else {
                v5_4 = v8.getString(2131689873);
                v5_4.getClass();
            }
        } else {
            v5_4 = v8.getString(2131689873);
        }
        com.google.android.material.card.MaterialCardView v3_6;
        v3_4.setText(v5_4);
        if (v0_6 == null) {
            v3_6 = p40.x(v4.getRoot(), 2130903347);
        } else {
            v3_6 = v8.getColor(2131034214);
        }
        float v5_7;
        if (v0_6 == null) {
            v5_7 = p40.x(v4.getRoot(), 2130903320);
        } else {
            v5_7 = v8.getColor(2131034212);
        }
        int v6_3;
        if (v0_6 == null) {
            v6_3 = p40.x(v4.getRoot(), 2130903322);
        } else {
            v6_3 = v8.getColor(2131034213);
        }
        float v5_11;
        v4.card.setCardBackgroundColor(v3_6);
        v4.tabTitle.setTextColor(v5_7);
        v4.tabClose.setImageTintList(android.content.res.ColorStateList.valueOf(v5_7));
        com.google.android.material.card.MaterialCardView v3_10 = v4.tabPreview;
        if (v0_6 == null) {
            v5_11 = p40.x(v4.getRoot(), 2130903345);
        } else {
            v5_11 = v8.getColor(2131034211);
        }
        com.google.android.material.card.MaterialCardView v3_11;
        v3_10.setBackgroundColor(v5_11);
        if (v0_6 == null) {
            if (v12_7 == 0) {
                v3_11 = 2131165367;
            } else {
                v3_11 = 2131165345;
            }
        } else {
            v3_11 = 2131165347;
        }
        float v5_13 = v3_11;
        com.google.android.material.card.MaterialCardView v3_12 = 0;
        if ((v0_6 == null) && (v12_7 == 0)) {
            String v9_4 = v2_1.l;
            if (v9_4 != null) {
                v3_12 = v9_4;
            } else {
                String v9_5 = v2_1.j;
                v9_5.getClass();
                String v9_6 = jj.a(v9_5);
                if (v9_6 != null) {
                    v3_12 = ((android.graphics.Bitmap) v7.b.get(v9_6));
                }
            }
        }
        r20.d(v4, v3_12, v5_13, v6_3);
        if ((v3_12 == null) && ((v0_6 == null) && (v12_7 == 0))) {
            v7.b(v2_1.j, new p20(((s20) p11), v2_1, this, v4, v5_13, v6_3));
        }
        com.google.android.material.card.MaterialCardView v3_1;
        android.widget.ImageButton v10_1 = v2_1.q;
        int v12_2 = v4.tabThumbnail;
        v12_2.getClass();
        q20 v0_2 = 8;
        if (v10_1 == null) {
            v3_1 = 8;
        } else {
            v3_1 = 0;
        }
        v12_2.setVisibility(v3_1);
        v4.tabThumbnail.setImageBitmap(v10_1);
        int v12_4 = v4.tabPlaceholder;
        v12_4.getClass();
        if (v10_1 == null) {
            v0_2 = 0;
        }
        android.widget.ImageButton v10_5;
        v12_4.setVisibility(v0_2);
        if (v2_1 != ((p9) v11_1.b.c)) {
            v10_5 = 0;
        } else {
            v10_5 = 1;
        }
        float v5_0;
        q20 v0_4 = v8.getResources().getDisplayMetrics();
        if (v10_5 == null) {
            v5_0 = 1;
        } else {
            v5_0 = 3;
        }
        android.widget.ImageButton v10_6;
        v4.card.setStrokeWidth(((int) (((float) v5_0) * v0_4.density)));
        q20 v0_8 = v4.card;
        com.google.android.material.card.MaterialCardView v3_3 = v4.getRoot();
        if (v10_5 == null) {
            v10_6 = 2130903328;
        } else {
            v10_6 = 2130903329;
        }
        v0_8.setStrokeColor(p40.x(v3_3, v10_6));
        v4.card.setOnClickListener(new q20(v11_1, v2_1, 0));
        v4.tabClose.setOnClickListener(new q20(v11_1, v2_1, 1));
        return;
    }

    public final fx c(android.view.ViewGroup p3)
    {
        this = new s20;
        com.example.instatool.databinding.ItemTabBinding v3_1 = com.example.instatool.databinding.ItemTabBinding.inflate(android.view.LayoutInflater.from(p3.getContext()), p3, 0);
        v3_1.getClass();
        this(v3_1);
        return this;
    }
}
