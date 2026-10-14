public final synthetic class Lj00 implements android.view.View$OnClickListener {
    public final synthetic byte a;
    public final synthetic j2 b;
    public final synthetic Object c;
    public final synthetic Object d;
    public final synthetic Object e;
    public final synthetic Object f;

    public synthetic j00(com.example.instatool.databinding.DialogSheetConfigBinding p2, o70 p3, j2 p4, d8 p5, com.example.instatool.browser.BrowserActivity p6)
    {
        this.a = 0;
        this.c = p2;
        this.d = p3;
        this.b = p4;
        this.e = p5;
        this.f = p6;
        return;
    }

    public synthetic j00(com.example.instatool.databinding.DialogTextInputBinding p2, am p3, c30 p4, am p5, j2 p6)
    {
        this.a = 1;
        this.c = p2;
        this.d = p3;
        this.e = p4;
        this.f = p5;
        this.b = p6;
        return;
    }

    public final void onClick(android.view.View p20)
    {
        int v3_0 = "";
        String v4_0 = this.b;
        boolean v5_6 = this.f;
        d8 v6_4 = this.e;
        String v7_5 = this.d;
        com.google.android.material.textfield.TextInputLayout v0_16 = this.c;
        switch (this.a) {
            case 0:
                com.google.android.material.textfield.TextInputLayout v0_17 = ((com.example.instatool.databinding.DialogSheetConfigBinding) v0_16);
                String v7_0 = ((o70) v7_5);
                int v1_2 = ((android.content.SharedPreferences) v7_0.b);
                d8 v6_1 = ((d8) v6_4);
                boolean v5_4 = hz.x(v0_17, ((com.example.instatool.browser.BrowserActivity) v5_6));
                if (v5_4) {
                    String v8_4 = v0_17.modeCookies.isChecked();
                    boolean v9_1 = v0_17.modeTwoFactor.isChecked();
                    if ((v8_4 != null) || (v9_1)) {
                        boolean v10_1 = v0_17.modePhotoBoy.isChecked();
                        boolean v11_1 = v0_17.modePhotoGirl.isChecked();
                        boolean v12_1 = v0_17.modeCustomUsername.isChecked();
                        boolean v13_1 = v0_17.modeFollow.isChecked();
                        String v7_4 = m10.P(v7_0.F()).toString();
                        if (v7_4.length() != 0) {
                            boolean v14_2 = java.util.regex.Pattern.compile("/spreadsheets/d/([a-zA-Z0-9-_]+)");
                            v14_2.getClass();
                            boolean v14_3 = v14_2.matcher(v7_4);
                            v14_3.getClass();
                            boolean v14_4 = io.o(v14_3, 0, v7_4);
                            if (!v14_4) {
                                boolean v14_6 = java.util.regex.Pattern.compile("[a-zA-Z0-9-_]{20,}");
                                v14_6.getClass();
                                if (!v14_6.matcher(v7_4).matches()) {
                                    v7_4 = 0;
                                }
                            } else {
                                v7_4 = ((String) ((pr) v14_4.a()).get(1));
                            }
                        }
                        d8 v6_0;
                        j2 v18 = v4_0;
                        d8 v16 = v6_1;
                        if ((!v5_4.equals(v7_4)) || (v8_4 != v1_2.getBoolean("auto_cookies", 1))) {
                            v6_0 = 1;
                        } else {
                            v6_0 = 0;
                            if ((v9_1 != v1_2.getBoolean("auto_two_factor", 0)) || ((v10_1 != v1_2.getBoolean("auto_photo_boy", 0)) || ((v11_1 != v1_2.getBoolean("auto_photo_girl", 0)) || ((v12_1 != v1_2.getBoolean("auto_custom_username", 0)) || (v13_1 != v1_2.getBoolean("auto_follow", 0)))))) {
                            }
                        }
                        com.google.android.material.textfield.TextInputLayout v0_4;
                        com.google.android.material.textfield.TextInputLayout v0_2 = v0_17.sheetUrl.getText();
                        if (v0_2 == null) {
                            v0_4 = 0;
                        } else {
                            com.google.android.material.textfield.TextInputLayout v0_3 = v0_2.toString();
                            if (v0_3 == null) {
                            } else {
                                v0_4 = m10.P(v0_3).toString();
                            }
                        }
                        if (v0_4 == null) {
                            v0_4 = "";
                        }
                        v1_2.getClass();
                        boolean v5_2 = v1_2.edit();
                        v5_2.getClass();
                        int v19_1 = v1_2;
                        v5_2.putString("sheet_url", v0_4);
                        v5_2.apply();
                        com.google.android.material.textfield.TextInputLayout v0_6 = v19_1.edit();
                        v0_6.getClass();
                        v0_6.putBoolean("auto_cookies", v8_4);
                        v0_6.apply();
                        com.google.android.material.textfield.TextInputLayout v0_7 = v19_1.edit();
                        v0_7.getClass();
                        v0_7.putBoolean("auto_two_factor", v9_1);
                        v0_7.apply();
                        com.google.android.material.textfield.TextInputLayout v0_8 = v19_1.edit();
                        v0_8.getClass();
                        v0_8.putBoolean("auto_photo_boy", v10_1);
                        v0_8.apply();
                        com.google.android.material.textfield.TextInputLayout v0_9 = v19_1.edit();
                        v0_9.getClass();
                        v0_9.putBoolean("auto_photo_girl", v11_1);
                        v0_9.apply();
                        com.google.android.material.textfield.TextInputLayout v0_10 = v19_1.edit();
                        v0_10.getClass();
                        v0_10.putBoolean("auto_custom_username", v12_1);
                        v0_10.apply();
                        com.google.android.material.textfield.TextInputLayout v0_11 = v19_1.edit();
                        v0_11.getClass();
                        v0_11.putBoolean("auto_follow", v13_1);
                        v0_11.apply();
                        v18.dismiss();
                        v16.d(Boolean.valueOf(v6_0));
                    } else {
                        v0_17.sheetColumns.setText(2131689517);
                    }
                }
                return;
            default:
                int v1_8;
                com.google.android.material.textfield.TextInputLayout v0_14 = ((com.example.instatool.databinding.DialogTextInputBinding) v0_16);
                String v7_1 = ((am) v7_5);
                d8 v6_3 = ((c30) v6_4);
                boolean v5_5 = ((am) v5_6);
                int v1_6 = v0_14.firstInput.getText();
                if (v1_6 == 0) {
                    v1_8 = 0;
                } else {
                    int v1_7 = v1_6.toString();
                    if (v1_7 == 0) {
                    } else {
                        v1_8 = m10.P(v1_7).toString();
                    }
                }
                if (v1_8 == 0) {
                    v1_8 = "";
                }
                String v2_0;
                String v8_2 = v0_14.secondInput.getText();
                if (v8_2 == null) {
                    v2_0 = 0;
                } else {
                    String v8_3 = v8_2.toString();
                    if (v8_3 == null) {
                    } else {
                        v2_0 = m10.P(v8_3).toString();
                    }
                }
                if (v2_0 != null) {
                    v3_0 = v2_0;
                }
                String v2_3 = ((String) v7_1.c(v1_8, v3_0));
                if (v2_3 == null) {
                    v5_5.c(v1_8, v3_0);
                    v4_0.dismiss();
                } else {
                    com.google.android.material.textfield.TextInputLayout v0_15;
                    if (v6_3 == null) {
                        v0_15 = v0_14.firstLayout;
                    } else {
                        int v3_1 = v0_14.secondLayout;
                        v3_1.getClass();
                        if ((v3_1.getVisibility() != 0) || (v1_8.length() <= 0)) {
                        } else {
                            v0_15 = v0_14.secondLayout;
                        }
                    }
                    v0_15.setError(v2_3);
                }
                return;
        }
    }
}
