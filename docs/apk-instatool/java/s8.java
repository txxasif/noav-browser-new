public final synthetic class Ls8 implements ll {
    public final synthetic byte a;
    public final synthetic com.example.instatool.browser.BrowserActivity b;
    public final synthetic String c;
    public final synthetic p9 d;

    public synthetic s8(com.example.instatool.browser.BrowserActivity p1, String p2, p9 p3, byte p4)
    {
        this.a = p4;
        this.b = p1;
        this.c = p2;
        this.d = p3;
        return;
    }

    public synthetic s8(com.example.instatool.browser.BrowserActivity p1, p9 p2, String p3, byte p4)
    {
        this.a = p4;
        this.b = p1;
        this.d = p2;
        this.c = p3;
        return;
    }

    public final Object a()
    {
        int v4_3 = "";
        int v6_2 = 10;
        int v7_1 = 1;
        String v9_0 = this.c;
        a50 v10 = a50.a;
        int v11_28 = this.d;
        com.example.instatool.browser.BrowserActivity v12 = this.b;
        switch (this.a) {
            case 0:
                int v0_4 = v11_28.i.getCertificate();
                xc v1_6 = android.net.Uri.parse(v9_0);
                v1_6.getClass();
                xc v1_7 = v1_6.getHost();
                if (v1_7 == null) {
                    v1_7 = v9_0;
                }
                String v2_11 = new rr(v12);
                android.text.SpannableStringBuilder v5_7 = ((f2) v2_11.b);
                v5_7.d = v12.getString(2131689603, new Object[] {v1_7}));
                xc v1_10 = 0;
                v2_11.k(2131689625, 0);
                if (v0_4 != 0) {
                    int v6_6 = new android.text.SpannableStringBuilder();
                    int v7_3 = v12.getString(2131689600);
                    v7_3.getClass();
                    if (v6_6.length() > 0) {
                        v6_6.append("\n\n");
                    }
                    int v8_3 = new android.text.style.StyleSpan(1);
                    int v11_7 = v6_6.length();
                    v6_6.append(v7_3);
                    v6_6.setSpan(v8_3, v11_7, v6_6.length(), 17);
                    v6_6.append(10);
                    int v8_4 = v12.getString(2131689597);
                    v8_4.getClass();
                    c8.p(v6_6, v8_4, v0_4.getIssuedTo().getCName());
                    int v11_10 = v12.getString(2131689602);
                    v11_10.getClass();
                    c8.p(v6_6, v11_10, v0_4.getIssuedTo().getOName());
                    int v11_12 = v12.getString(2131689599);
                    v11_12.getClass();
                    if (v6_6.length() > 0) {
                        v6_6.append("\n\n");
                    }
                    String v13_6 = new android.text.style.StyleSpan(1);
                    int v14_5 = v6_6.length();
                    v6_6.append(v11_12);
                    v6_6.setSpan(v13_6, v14_5, v6_6.length(), 17);
                    v6_6.append(10);
                    int v7_8 = v12.getString(2131689597);
                    v7_8.getClass();
                    c8.p(v6_6, v7_8, v0_4.getIssuedBy().getCName());
                    int v7_9 = v12.getString(2131689602);
                    v7_9.getClass();
                    c8.p(v6_6, v7_9, v0_4.getIssuedBy().getOName());
                    int v7_11 = v12.getString(2131689607);
                    v7_11.getClass();
                    if (v6_6.length() > 0) {
                        v6_6.append("\n\n");
                    }
                    int v8_12;
                    int v8_10 = new android.text.style.StyleSpan(1);
                    int v11_18 = v6_6.length();
                    v6_6.append(v7_11);
                    v6_6.setSpan(v8_10, v11_18, v6_6.length(), 17);
                    v6_6.append(10);
                    int v7_15 = v12.getString(2131689605);
                    v7_15.getClass();
                    int v8_11 = v0_4.getValidNotBeforeDate();
                    if (v8_11 == 0) {
                        v8_12 = 0;
                    } else {
                        v8_12 = android.text.format.DateFormat.getMediumDateFormat(v12).format(v8_11);
                    }
                    int v8_14;
                    c8.p(v6_6, v7_15, v8_12);
                    int v7_17 = v12.getString(2131689606);
                    v7_17.getClass();
                    int v8_13 = v0_4.getValidNotAfterDate();
                    if (v8_13 == 0) {
                        v8_14 = 0;
                    } else {
                        v8_14 = android.text.format.DateFormat.getMediumDateFormat(v12).format(v8_13);
                    }
                    c8.p(v6_6, v7_17, v8_14);
                    if (android.os.Build$VERSION.SDK_INT >= 29) {
                        int v0_6 = b0.j(v0_4);
                        if (v0_6 != 0) {
                            int v0_7 = v0_6.getEncoded();
                            if (v0_7 != 0) {
                                int v0_8 = java.security.MessageDigest.getInstance("SHA-256").digest(v0_7);
                                v0_8.getClass();
                                xc v1_14 = new StringBuilder();
                                v1_14.append("");
                                int v7_19 = v0_8.length;
                                int v8_16 = 0;
                                int v11_21 = 0;
                                while (v8_16 < v7_19) {
                                    String v13_7 = v0_8[v8_16];
                                    v11_21++;
                                    if (v11_21 > 1) {
                                        v1_14.append(":");
                                    }
                                    v1_14.append(String.format("%02X", java.util.Arrays.copyOf(new Object[] {Byte.valueOf(v13_7)}), 1)));
                                    v8_16++;
                                }
                                v1_14.append("");
                                v1_10 = v1_14.toString();
                            }
                        }
                    }
                    if (v1_10 != null) {
                        int v0_13 = v12.getString(2131689598);
                        v0_13.getClass();
                        if (v6_6.length() > 0) {
                            v6_6.append("\n\n");
                        }
                        int v4_6 = new android.text.style.StyleSpan(1);
                        int v7_20 = v6_6.length();
                        v6_6.append(v0_13);
                        v6_6.setSpan(v4_6, v7_20, v6_6.length(), 17);
                        v6_6.append(10);
                        v6_6.append(v1_10);
                    }
                    int v0_17 = new android.text.SpannedString(v6_6);
                    xc v1_18 = ((int) (1101004800 * v12.getResources().getDisplayMetrics().density));
                    int v3_9 = new android.widget.TextView(v12);
                    v3_9.setText(v0_17);
                    v3_9.setTextIsSelectable(1);
                    v3_9.setPadding(v1_18, (v1_18 / 2), v1_18, 0);
                    v3_9.setLineSpacing(0, 1067030938);
                    v5_7.p = v3_9;
                    v2_11.i();
                } else {
                    int v0_22;
                    if (!v9_0.startsWith("https://")) {
                        v0_22 = 2131689601;
                    } else {
                        v0_22 = 2131689604;
                    }
                    v5_7.f = v5_7.a.getText(v0_22);
                    v2_11.i();
                }
                return v10;
            case 1:
                int v0_14 = en.a(v11_28.c).getCookie(v9_0);
                if (v0_14 != 0) {
                    v4_3 = v0_14;
                }
                int v0_25 = m10.P(v4_3).toString();
                xc v1_23 = new char[1];
                v1_23[0] = 59;
                xc v1_24 = m10.K(v0_25, v1_23);
                int v4_11 = new java.util.ArrayList(tb.e0(v1_24));
                xc v1_25 = v1_24.iterator();
                while (v1_25.hasNext()) {
                    v4_11.add(m10.P(((String) v1_25.next())).toString());
                }
                xc v1_27 = new java.util.ArrayList();
                int v11_26 = v4_11.size();
                String v13_1 = 0;
                while (v13_1 < v11_26) {
                    int v14_3 = v4_11.get(v13_1);
                    v13_1++;
                    if (((String) v14_3).length() > 0) {
                        v1_27.add(v14_3);
                    }
                }
                String v13_14;
                int v4_13 = com.example.instatool.databinding.DialogCookiesBinding.inflate(android.view.LayoutInflater.from(v12));
                v4_13.getClass();
                int v11_27 = v4_13.cookiesSummary;
                if (!v1_27.isEmpty()) {
                    v13_14 = v12.getResources().getQuantityString(2131623937, v1_27.size(), new Object[] {Integer.valueOf(v1_27.size())}));
                } else {
                    v13_14 = v12.getString(2131689628);
                }
                int v11_30;
                v11_27.setText(v13_14);
                int v8_19 = v4_13.cookiesBox;
                v8_19.getClass();
                if (v1_27.isEmpty()) {
                    v11_30 = 8;
                } else {
                    v11_30 = 0;
                }
                v8_19.setVisibility(v11_30);
                int v8_0 = v4_13.cookiesText;
                int v11_1 = new android.text.SpannableStringBuilder();
                String v13_0 = v1_27.size();
                int v14_0 = 0;
                String v15_0 = 0;
                while (v15_0 < v13_0) {
                    Object v16 = v1_27.get(v15_0);
                    v15_0++;
                    int v17 = (v14_0 + 1);
                    if (v14_0 < 0) {
                        sb.d0();
                        throw 0;
                    } else {
                        String v2_7 = ((String) v16);
                        if (v14_0 > 0) {
                            v11_1.append(v6_2);
                        }
                        int v14_2 = new android.text.style.StyleSpan(v7_1);
                        int v6_1 = v11_1.length();
                        v11_1.append(m10.N(v2_7, 61));
                        v11_1.setSpan(v14_2, v6_1, v11_1.length(), 17);
                        if (m10.B(v2_7, 61)) {
                            v11_1.append(61).append(m10.L(v2_7, 61));
                        }
                        v14_0 = v17;
                        v6_2 = 10;
                        v7_1 = 1;
                    }
                }
                v8_0.setText(new android.text.SpannedString(v11_1));
                String v2_2 = android.net.Uri.parse(v9_0);
                v2_2.getClass();
                String v2_3 = v2_2.getHost();
                if (v2_3 != null) {
                    v9_0 = v2_3;
                }
                String v2_5 = new rr(v12);
                int v3_1 = ((f2) v2_5.b);
                v3_1.d = v12.getString(2131689629, new Object[] {v9_0}));
                v3_1.p = v4_13.getRoot();
                v2_5.j(2131689625, 0);
                if (!v1_27.isEmpty()) {
                    v2_5.k(2131689631, new xc(v12, v0_25, 0));
                }
                v2_5.i();
                return v10;
            case 2:
                v12.M(v11_28, v9_0, v11_28.c);
                return v10;
            case 3:
                v12.H(v11_28, new gf(this.c, v11_28.i.getSettings().getUserAgentString(), 0, 0, -1, v11_28.j));
                return v10;
            case 4:
                v12.M(v11_28, v9_0, v11_28.c);
                return v10;
            default:
                v12.H(v11_28, new gf(this.c, v11_28.i.getSettings().getUserAgentString(), 0, 0, -1, v11_28.j));
                return v10;
        }
    }
}
