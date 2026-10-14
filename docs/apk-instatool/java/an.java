public final class Lan extends jq {
    public final synthetic cn d;

    public an(cn p1)
    {
        this.d = p1;
        super(cn.h);
        return;
    }

    public static void e(com.example.instatool.databinding.ItemHomeTileBinding p2, android.graphics.Bitmap p3)
    {
        android.widget.ImageView v0_0 = p2.tileLetter;
        v0_0.getClass();
        v0_0.setVisibility(8);
        android.widget.ImageView v0_1 = p2.tileIcon;
        v0_1.getClass();
        v0_1.setVisibility(0);
        p2.tileIcon.setImageBitmap(p3);
        p2.tileCircle.setBackgroundResource(2131165309);
        return;
    }

    public final void b(fx p12, int p13)
    {
        android.widget.FrameLayout v0_0 = this.d;
        jj v1_1 = ((jj) v0_0.c);
        o7 v13_2 = ((o7) this.c.f.get(p13));
        com.example.instatool.databinding.ItemHomeTileBinding v2_2 = ((bn) p12).t;
        String v3 = v13_2.b;
        int v4_0 = v13_2.c;
        int[] v5_1 = android.net.Uri.parse(v3).getHost();
        if (v5_1 == null) {
            v5_1 = "";
        }
        int v7_1;
        int[] v5_2 = m10.J(v5_1, "www.");
        if (!m10.G(v4_0)) {
            v7_1 = v4_0;
        } else {
            v7_1 = v5_2;
        }
        android.widget.FrameLayout v0_4;
        v2_2.tileTitle.setText(v7_1);
        v2_2.getRoot().setOnClickListener(new b9(v0_0, v13_2, 2));
        v2_2.getRoot().setOnLongClickListener(new m9(v0_0, v13_2, 1));
        ((bn) p12).u = v3;
        android.widget.FrameLayout v0_3 = jj.a(v3);
        android.graphics.drawable.GradientDrawable v6_4 = 0;
        if (v0_3 == null) {
            v0_4 = 0;
        } else {
            v0_4 = ((android.graphics.Bitmap) v1_1.b.get(v0_3));
        }
        if (v0_4 == null) {
            if (v5_2.length() != 0) {
                v4_0 = v5_2;
            }
            android.widget.FrameLayout v0_7 = v2_2.tileIcon;
            v0_7.getClass();
            v0_7.setVisibility(8);
            android.widget.FrameLayout v0_8 = v2_2.tileLetter;
            v0_8.getClass();
            int v7_7 = 0;
            v0_8.setVisibility(0);
            android.widget.FrameLayout v0_9 = v2_2.tileLetter;
            while (v7_7 < v4_0.length()) {
                char v9_1 = v4_0.charAt(v7_7);
                if (!Character.isLetterOrDigit(v9_1)) {
                    v7_7++;
                } else {
                    v6_4 = Character.valueOf(v9_1);
                    break;
                }
            }
            android.graphics.drawable.GradientDrawable v6_8;
            if (v6_4 == null) {
                v6_8 = "?";
            } else {
                v6_8 = Character.valueOf(Character.toUpperCase(v6_4.charValue())).toString();
                if (v6_8 == null) {
                }
            }
            v0_9.setText(v6_8);
            android.widget.FrameLayout v0_10 = v2_2.tileCircle;
            android.graphics.drawable.GradientDrawable v6_10 = new android.graphics.drawable.GradientDrawable();
            v6_10.setShape(1);
            v6_10.setColor(cn.g[((v4_0.hashCode() & 2147483647) % 8)]);
            v0_10.setBackground(v6_10);
        } else {
            an.e(v2_2, v0_4);
        }
        v1_1.b(v3, new r8(((bn) p12), v13_2, this, v2_2));
        return;
    }
}
