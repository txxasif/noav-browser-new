public final synthetic class Ly8 implements wl {
    public final synthetic byte a;
    public final synthetic boolean b;
    public final synthetic Object c;
    public final synthetic Object d;

    public synthetic y8(String p2, String p3, boolean p4)
    {
        this.a = 1;
        this.b = p4;
        this.c = p2;
        this.d = p3;
        return;
    }

    public synthetic y8(p9 p2, boolean p3, com.example.instatool.browser.BrowserActivity p4)
    {
        this.a = 0;
        this.c = p2;
        this.b = p3;
        this.d = p4;
        return;
    }

    public final Object d(Object p10)
    {
        a50 v1 = a50.a;
        com.example.instatool.databinding.SheetMenuBinding v2_2 = this.d;
        android.widget.LinearLayout v3_7 = this.c;
        androidx.core.widget.NestedScrollView v9_12 = this.b;
        switch (this.a) {
            case 0:
                android.content.res.ColorStateList v5_0;
                android.widget.LinearLayout v3_8 = ((p9) v3_7);
                com.example.instatool.databinding.SheetMenuBinding v2_5 = ((com.example.instatool.browser.BrowserActivity) v2_2);
                jt v10_1 = ((Boolean) p10).booleanValue();
                if (v3_8 == null) {
                    v5_0 = 0;
                } else {
                    v5_0 = 1;
                    if (v3_8.p != 1) {
                    }
                }
                int v8_0;
                android.widget.LinearLayout v3_6 = v2_5.A().c().C();
                o70 v6_1 = new o70(v2_5, new kt(v10_1, v5_0, v9_12, v3_6), new a9(v2_5, v10_1, 0));
                z7 v0_5 = new z7(v2_5);
                com.example.instatool.databinding.SheetMenuBinding v2_4 = com.example.instatool.databinding.SheetMenuBinding.inflate(android.view.LayoutInflater.from(v2_5));
                v2_4.getClass();
                int v4_3 = p40.x(v2_4.getRoot(), 2130903329);
                if (v10_1 == null) {
                    v8_0 = 2131165374;
                } else {
                    v8_0 = 2131165373;
                }
                int v8_1;
                v2_4.quickBookmarkIcon.setImageResource(v8_0);
                if (v10_1 == null) {
                    v8_1 = 2131689573;
                } else {
                    v8_1 = 2131689576;
                }
                v2_4.quickBookmarkLabel.setText(v8_1);
                if (v10_1 != null) {
                    v2_4.quickBookmarkIcon.setImageTintList(android.content.res.ColorStateList.valueOf(v4_3));
                }
                if (v5_0 != null) {
                    v2_4.quickDesktopIcon.setImageTintList(android.content.res.ColorStateList.valueOf(v4_3));
                    v2_4.quickDesktopLabel.setTextColor(v4_3);
                }
                v2_4.menuAutoInstagramSwitch.setChecked(v3_6);
                if (v3_6 != null) {
                    v2_4.menuAutoInstagramIcon.setImageTintList(android.content.res.ColorStateList.valueOf(v4_3));
                }
                jt v10_22 = sb.b0(new android.widget.LinearLayout[] {v2_4.quickBookmark, v2_4.quickFind, v2_4.quickShare})).iterator();
                while (v10_22.hasNext()) {
                    int v4_1;
                    android.widget.LinearLayout v3_1 = ((android.widget.LinearLayout) v10_22.next());
                    v3_1.setEnabled(v9_12);
                    if (v9_12 == null) {
                        v4_1 = 1052938076;
                    } else {
                        v4_1 = 1065353216;
                    }
                    v3_1.setAlpha(v4_1);
                }
                androidx.core.widget.NestedScrollView v9_13 = v2_4.quickBookmark;
                v9_13.getClass();
                o70.J(v0_5, v6_1, v9_13, jt.BOOKMARK);
                androidx.core.widget.NestedScrollView v9_14 = v2_4.quickFind;
                v9_14.getClass();
                o70.J(v0_5, v6_1, v9_14, jt.FIND);
                androidx.core.widget.NestedScrollView v9_15 = v2_4.quickShare;
                v9_15.getClass();
                o70.J(v0_5, v6_1, v9_15, jt.SHARE);
                androidx.core.widget.NestedScrollView v9_16 = v2_4.quickDesktop;
                v9_16.getClass();
                o70.J(v0_5, v6_1, v9_16, jt.DESKTOP);
                androidx.core.widget.NestedScrollView v9_17 = v2_4.menuAutoInstagram;
                v9_17.getClass();
                o70.J(v0_5, v6_1, v9_17, jt.AUTO_INSTAGRAM);
                androidx.core.widget.NestedScrollView v9_1 = v2_4.menuManageAccounts;
                v9_1.getClass();
                o70.J(v0_5, v6_1, v9_1, jt.MANAGE_ACCOUNTS);
                androidx.core.widget.NestedScrollView v9_2 = v2_4.menuNewTab;
                v9_2.getClass();
                o70.J(v0_5, v6_1, v9_2, jt.NEW_TAB);
                androidx.core.widget.NestedScrollView v9_3 = v2_4.menuNewIncognito;
                v9_3.getClass();
                o70.J(v0_5, v6_1, v9_3, jt.NEW_INCOGNITO_TAB);
                androidx.core.widget.NestedScrollView v9_4 = v2_4.menuBookmarks;
                v9_4.getClass();
                o70.J(v0_5, v6_1, v9_4, jt.BOOKMARKS);
                androidx.core.widget.NestedScrollView v9_5 = v2_4.menuHistory;
                v9_5.getClass();
                o70.J(v0_5, v6_1, v9_5, jt.HISTORY);
                androidx.core.widget.NestedScrollView v9_6 = v2_4.menuDownloads;
                v9_6.getClass();
                o70.J(v0_5, v6_1, v9_6, jt.DOWNLOADS);
                androidx.core.widget.NestedScrollView v9_7 = v2_4.menuClearData;
                v9_7.getClass();
                o70.J(v0_5, v6_1, v9_7, jt.CLEAR_DATA);
                androidx.core.widget.NestedScrollView v9_8 = v2_4.menuExtensions;
                v9_8.getClass();
                o70.J(v0_5, v6_1, v9_8, jt.EXTENSIONS);
                androidx.core.widget.NestedScrollView v9_9 = v2_4.menuSettings;
                v9_9.getClass();
                o70.J(v0_5, v6_1, v9_9, jt.SETTINGS);
                v0_5.setContentView(v2_4.getRoot());
                v0_5.show();
                return v1;
            default:
                android.widget.LinearLayout v3_3 = ((String) v3_7);
                com.example.instatool.databinding.SheetMenuBinding v2_0 = ((String) v2_2);
                Class vtmp1 = ((k9) p10).getClass();
                if (v9_12 == null) {
                    ((k9) p10).a(v3_3, v2_0);
                } else {
                    v3_3.getClass();
                    ((k9) p10).getWritableDatabase().delete("bookmarks", "url = ?", new String[] {v3_3}));
                }
                return v1;
        }
    }
}
