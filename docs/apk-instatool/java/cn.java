public final class Lcn {
    public static final int[] g;
    public static final fp h;
    public final Object a;
    public final Object b;
    public final Object c;
    public final Object d;
    public final Object e;
    public final Object f;

    static cn()
    {
        fp v0_1 = new int[8];
        v0_1 = {-10788921, -2741898, -15753896, -765666, -14776091, -7461718, -16742021, -9614271};
        cn.g = v0_1;
        cn.h = new fp(1);
        return;
    }

    public cn()
    {
        this.a = new int[] {2131165302, 2131165300, 2131165226});
        int v1_4 = new int[7];
        v1_4 = {2131165250, 2131165285, 2131165257, 2131165252, 2131165253, 2131165256, 2131165255};
        this.b = v1_4;
        int[] v0_1 = new int[7];
        v0_1 = {2131165299, 2131165301, 2131165243, 2131165295, 2131165296, 2131165297, 2131165298};
        this.c = v0_1;
        this.d = new int[] {2131165275, 2131165241, 2131165274});
        this.e = new int[] {2131165293, 2131165303});
        this.f = new int[] {2131165229, 2131165235, 2131165230, 2131165236});
        return;
    }

    public cn(android.app.Activity p1, ri p2, m8 p3, g9 p4)
    {
        this.a = p1;
        this.b = p2;
        this.c = p3;
        this.d = p4;
        this.e = new z7(p1);
        com.example.instatool.databinding.SheetExtensionsBinding v1_1 = com.example.instatool.databinding.SheetExtensionsBinding.inflate(android.view.LayoutInflater.from(p1));
        v1_1.getClass();
        this.f = v1_1;
        return;
    }

    public cn(com.example.instatool.databinding.ViewHomeBinding p4, k9 p5, jj p6, com.example.instatool.browser.BrowserActivity p7)
    {
        p4.getClass();
        this.a = p4;
        this.b = p5;
        this.c = p6;
        this.d = p7;
        wm v5_11 = p4.getRoot().getContext();
        this.e = v5_11;
        int v6_2 = new an(this);
        this.f = v6_2;
        p4.homeBookmarks.setLayoutManager(new androidx.recyclerview.widget.GridLayoutManager(c8.k((v5_11.getResources().getConfiguration().screenWidthDp / 88), 4, 8)));
        p4.homeBookmarks.setAdapter(v6_2);
        p4.homeSearch.setOnClickListener(new wm(this, 0));
        p4.homeSeeAll.setOnClickListener(new wm(this, 1));
        return;
    }

    public static boolean a(int[] p4, int p5)
    {
        int v2 = 0;
        while (v2 < p4.length) {
            if (p4[v2] != p5) {
                v2++;
            } else {
                return 1;
            }
        }
        return 0;
    }

    public static android.content.res.ColorStateList b(android.content.Context p6, int p7)
    {
        int v0_2 = j30.c(p6, 2130903301);
        return new android.content.res.ColorStateList(new int[][] {j30.b, j30.d, j30.c, j30.f}), new int[] {j30.b(p6, 2130903296), ac.c(v0_2, p7), ac.c(v0_2, p7), p7}));
    }

    public static android.graphics.drawable.LayerDrawable c(ay p4, android.content.Context p5, int p6)
    {
        int v0_2;
        int v5_6;
        android.graphics.drawable.LayerDrawable v6_1 = p5.getResources().getDimensionPixelSize(p6);
        int v0_4 = p4.d(p5, 2131165289);
        android.graphics.drawable.BitmapDrawable v4_4 = p4.d(p5, 2131165290);
        if ((!(v0_4 instanceof android.graphics.drawable.BitmapDrawable)) || ((v0_4.getIntrinsicWidth() != v6_1) || (v0_4.getIntrinsicHeight() != v6_1))) {
            int v5_5 = android.graphics.Bitmap.createBitmap(v6_1, v6_1, android.graphics.Bitmap$Config.ARGB_8888);
            android.graphics.drawable.Drawable[] v2_1 = new android.graphics.Canvas(v5_5);
            v0_4.setBounds(0, 0, v6_1, v6_1);
            v0_4.draw(v2_1);
            v0_2 = new android.graphics.drawable.BitmapDrawable(v5_5);
            v5_6 = new android.graphics.drawable.BitmapDrawable(v5_5);
        } else {
            v0_2 = ((android.graphics.drawable.BitmapDrawable) v0_4);
            v5_6 = new android.graphics.drawable.BitmapDrawable(v0_2.getBitmap());
        }
        android.graphics.drawable.BitmapDrawable v4_2;
        v5_6.setTileModeX(android.graphics.Shader$TileMode.REPEAT);
        if ((!(v4_4 instanceof android.graphics.drawable.BitmapDrawable)) || ((v4_4.getIntrinsicWidth() != v6_1) || (v4_4.getIntrinsicHeight() != v6_1))) {
            android.graphics.drawable.Drawable[] v2_10 = android.graphics.Bitmap.createBitmap(v6_1, v6_1, android.graphics.Bitmap$Config.ARGB_8888);
            android.graphics.Canvas v3_1 = new android.graphics.Canvas(v2_10);
            v4_4.setBounds(0, 0, v6_1, v6_1);
            v4_4.draw(v3_1);
            v4_2 = new android.graphics.drawable.BitmapDrawable(v2_10);
        } else {
            v4_2 = ((android.graphics.drawable.BitmapDrawable) v4_4);
        }
        android.graphics.drawable.Drawable[] v2_12 = new android.graphics.drawable.Drawable[3];
        v2_12[0] = v0_2;
        v2_12[1] = v4_2;
        v2_12[2] = v5_6;
        android.graphics.drawable.LayerDrawable v6_3 = new android.graphics.drawable.LayerDrawable(v2_12);
        v6_3.setId(0, 16908288);
        v6_3.setId(1, 16908303);
        v6_3.setId(2, 16908301);
        return v6_3;
    }

    public static void h(android.graphics.drawable.Drawable p0, int p1, android.graphics.PorterDuff$Mode p2)
    {
        android.graphics.drawable.Drawable v0_1 = p0.mutate();
        if (p2 == null) {
            p2 = b4.b;
        }
        v0_1.setColorFilter(b4.c(p1, p2));
        return;
    }

    public android.content.res.ColorStateList d(android.content.Context p8, int p9)
    {
        if (p9 != 2131165246) {
            if (p9 != 2131165292) {
                if (p9 != 2131165291) {
                    if (p9 != 2131165234) {
                        if (p9 != 2131165228) {
                            if (p9 != 2131165233) {
                                if ((p9 != 2131165287) && (p9 != 2131165288)) {
                                    if (!cn.a(((int[]) this.b), p9)) {
                                        if (!cn.a(((int[]) this.e), p9)) {
                                            if (!cn.a(((int[]) this.f), p9)) {
                                                if (p9 != 2131165284) {
                                                    return 0;
                                                } else {
                                                    return io.p(p8, 2131034134);
                                                }
                                            } else {
                                                return io.p(p8, 2131034131);
                                            }
                                        } else {
                                            return io.p(p8, 2131034132);
                                        }
                                    } else {
                                        return j30.d(p8, 2130903302);
                                    }
                                } else {
                                    return io.p(p8, 2131034135);
                                }
                            } else {
                                return cn.b(p8, j30.c(p8, 2130903294));
                            }
                        } else {
                            return cn.b(p8, 0);
                        }
                    } else {
                        return cn.b(p8, j30.c(p8, 2130903296));
                    }
                } else {
                    int[][] v9_1 = new int[][3];
                    int v7_28 = new int[3];
                    int v2_0 = j30.d(p8, 2130903352);
                    if ((v2_0 == 0) || (!v2_0.isStateful())) {
                        v9_1[0] = j30.b;
                        v7_28[0] = j30.b(p8, 2130903352);
                        v9_1[1] = j30.e;
                        v7_28[1] = j30.c(p8, 2130903300);
                        v9_1[2] = j30.f;
                        v7_28[2] = j30.c(p8, 2130903352);
                    } else {
                        boolean v0_17 = j30.b;
                        v9_1[0] = v0_17;
                        v7_28[0] = v2_0.getColorForState(v0_17, 0);
                        v9_1[1] = j30.e;
                        v7_28[1] = j30.c(p8, 2130903300);
                        v9_1[2] = j30.f;
                        v7_28[2] = v2_0.getDefaultColor();
                    }
                    return new android.content.res.ColorStateList(v9_1, v7_28);
                }
            } else {
                return io.p(p8, 2131034136);
            }
        } else {
            return io.p(p8, 2131034133);
        }
    }

    public boolean e()
    {
        int v0_4 = ((com.example.instatool.databinding.ViewHomeBinding) this.a).getRoot();
        v0_4.getClass();
        if (v0_4.getVisibility() != 0) {
            return 0;
        } else {
            return 1;
        }
    }

    public void f()
    {
        ((k9) this.b).c(new e6(10), new xm(this, 2));
        return;
    }

    public void g()
    {
        ((com.example.instatool.databinding.SheetExtensionsBinding) this.f).list.removeAllViews();
        Throwable v1_15 = ((ri) this.b).l.values();
        int v2_5 = new e6(8);
        java.util.ArrayList v4_1 = new e6(6);
        int v5_3 = new wl[2];
        v5_3[0] = v2_5;
        v5_3[1] = v4_1;
        Throwable v1_3 = rb.o0(v1_15, new bc(v5_3));
        java.util.ArrayList v4_5 = new java.util.ArrayList();
        Throwable v1_4 = v1_3.iterator();
        while (v1_4.hasNext()) {
            int v5_2 = v1_4.next();
            if (!((ei) v5_2).d) {
                v4_5.add(v5_2);
            }
        }
        int v5_6;
        if (!v4_5.isEmpty()) {
            v5_6 = 8;
        } else {
            v5_6 = 0;
        }
        ((com.example.instatool.databinding.SheetExtensionsBinding) this.f).empty.setVisibility(v5_6);
        Throwable v1_11 = android.view.LayoutInflater.from(((android.app.Activity) this.a));
        int v5_7 = v4_5.size();
        int v7_3 = 0;
        while (v7_3 < v5_7) {
            int v2_16;
            ei v8_0 = v4_5.get(v7_3);
            v7_3++;
            ei v8_1 = ((ei) v8_0);
            com.example.instatool.databinding.ItemExtensionBinding v9_3 = com.example.instatool.databinding.ItemExtensionBinding.inflate(v1_11, ((com.example.instatool.databinding.SheetExtensionsBinding) this.f).list, 0);
            v9_3.getClass();
            int v10_7 = ((ri) this.b);
            String v13 = v8_1.h;
            v9_3.name.setText(v8_1.f);
            String v11_3 = v9_3.summary;
            android.app.Activity v12_2 = ((android.app.Activity) this.a);
            String v14 = v8_1.g;
            String v15_1 = v12_2.getString(2131689679);
            int v3_16 = Integer.valueOf(v8_1.j.size());
            if (v8_1.k == null) {
                v2_16 = "";
            } else {
                v2_16 = v12_2.getString(2131689684);
            }
            int v3_19;
            v11_3.setText(v12_2.getString(2131689683, new Object[] {v14, v15_1, v3_16, v2_16})));
            v9_3.description.setText(v13);
            if (!m10.G(v13)) {
                v3_19 = 0;
            } else {
                v3_19 = 8;
            }
            v9_3.description.setVisibility(v3_19);
            int v2_1 = v8_1.n;
            int v3_0 = 0;
            if (v2_1 != 0) {
                int v2_2 = v8_1.b.d(v2_1);
                if (v2_2 != 0) {
                    try {
                        v3_0 = android.graphics.BitmapFactory.decodeStream(v2_2);
                        v2_2.close();
                    } catch (Throwable v0_1) {
                        Throwable v1_1 = v0_1;
                        try {
                            throw v1_1;
                        } catch (Throwable v0_2) {
                            c8.i(v2_2, v1_1);
                            throw v0_2;
                        }
                    }
                }
            }
            if (v3_0 != 0) {
                v9_3.icon.setImageBitmap(v3_0);
            }
            v9_3.enabled.setChecked(v10_7.n(v8_1));
            v9_3.enabled.setOnCheckedChangeListener(new xi(this, v8_1, v9_3));
            v9_3.incognito.setChecked(v10_7.e.getBoolean("incognito:".concat(v8_1.a), 0));
            v9_3.incognito.setOnCheckedChangeListener(new yi(this, v8_1, 0));
            int v2_9 = v8_1.l;
            if (v2_9 == 0) {
                v2_9 = v8_1.m;
            }
            int v10_2;
            if (v2_9 == 0) {
                v10_2 = 8;
            } else {
                v10_2 = 0;
            }
            v9_3.options.setVisibility(v10_2);
            v9_3.options.setOnClickListener(new zi(v2_9, this, v8_1, 0));
            v9_3.remove.setOnClickListener(new b9(this, v8_1, 1));
            this.i(v9_3, v8_1);
            ((com.example.instatool.databinding.SheetExtensionsBinding) this.f).list.addView(v9_3.getRoot());
            int v3 = 8;
        }
        return;
    }

    public void i(com.example.instatool.databinding.ItemExtensionBinding p1, ei p2)
    {
        int v0_3;
        int v0_4 = ((ri) this.b).n(p2);
        p1.incognito.setEnabled(v0_4);
        p1.options.setEnabled(v0_4);
        if (v0_4 == 0) {
            v0_3 = 1053609165;
        } else {
            v0_3 = 1065353216;
        }
        p1.icon.setAlpha(v0_3);
        return;
    }
}
