public abstract class Lhz implements y60 {

    public static int d(bx p0, su p1, android.view.View p2, android.view.View p3, ow p4, boolean p5)
    {
        if ((p4.v() != 0) && ((p0.b() != 0) && ((p2 != 0) && (p3 != null)))) {
            if (p5) {
                return Math.min(p1.k(), (p1.b(p3) - p1.e(p2)));
            } else {
                return (Math.abs((ow.G(p2) - ow.G(p3))) + 1);
            }
        } else {
            return 0;
        }
    }

    public static int e(bx p3, su p4, android.view.View p5, android.view.View p6, ow p7, boolean p8, boolean p9)
    {
        if ((p7.v() != 0) && ((p3.b() != 0) && ((p5 != null) && (p6 != 0)))) {
            int v3_1;
            float v7_3 = Math.min(ow.G(p5), ow.G(p6));
            int v1_2 = Math.max(ow.G(p5), ow.G(p6));
            if (!p9) {
                v3_1 = Math.max(0, v7_3);
            } else {
                v3_1 = Math.max(0, ((p3.b() - v1_2) - 1));
            }
            if (p8 != 0) {
                return Math.round(((((float) v3_1) * (((float) Math.abs((p4.b(p6) - p4.e(p5)))) / ((float) (Math.abs((ow.G(p5) - ow.G(p6))) + 1)))) + ((float) (p4.j() - p4.e(p5)))));
            } else {
                return v3_1;
            }
        } else {
            return 0;
        }
    }

    public static int f(bx p0, su p1, android.view.View p2, android.view.View p3, ow p4, boolean p5)
    {
        if ((p4.v() != 0) && ((p0.b() != 0) && ((p2 != 0) && (p3 != null)))) {
            if (p5) {
                return ((int) ((((float) (p1.b(p3) - p1.e(p2))) / ((float) (Math.abs((ow.G(p2) - ow.G(p3))) + 1))) * ((float) p0.b())));
            } else {
                return p0.b();
            }
        } else {
            return 0;
        }
    }

    public static boolean g(java.io.File p0, android.content.res.Resources p1, int p2)
    {
        try {
            int v1_1 = p1.openRawResource(p2);
            try {
                Throwable v0_2 = hz.h(p0, v1_1);
                try {
                    if (v1_1 != 0) {
                        v1_1.close();
                    }
                } catch (java.io.IOException) {
                }
                return v0_2;
            } catch (Throwable v0_1) {
                try {
                    if (v1_1 != 0) {
                        v1_1.close();
                    }
                } catch (java.io.IOException) {
                }
                throw v0_1;
            }
        } catch (Throwable v0_1) {
            v1_1 = 0;
        }
    }

    public static boolean h(java.io.File p5, java.io.InputStream p6)
    {
        android.os.StrictMode$ThreadPolicy v0 = android.os.StrictMode.allowThreadDiskWrites();
        int v2_1 = 0;
        try {
            StringBuilder v3_3 = new java.io.FileOutputStream(p5, 0);
            try {
                int v5_7 = new byte[1024];
            } catch (int v5_2) {
                v2_1 = v3_3;
                StringBuilder v3_1 = new StringBuilder();
                v3_1.append("Error copying resource contents to temp file: ");
                v3_1.append(v5_2.getMessage());
                android.util.Log.e("TypefaceCompatUtil", v3_1.toString());
                try {
                    if (v2_1 != 0) {
                        v2_1.close();
                    }
                } catch (java.io.IOException) {
                }
                android.os.StrictMode.setThreadPolicy(v0);
                return 0;
            } catch (int v5_1) {
                v2_1 = v3_3;
                try {
                    if (v2_1 != 0) {
                        v2_1.close();
                    }
                } catch (java.io.IOException) {
                }
                android.os.StrictMode.setThreadPolicy(v0);
                throw v5_1;
            }
            while(true) {
                int v2_0 = p6.read(v5_7);
                if (v2_0 == -1) {
                    break;
                }
                v3_3.write(v5_7, 0, v2_0);
            }
            try {
                v3_3.close();
            } catch (java.io.IOException) {
            }
            android.os.StrictMode.setThreadPolicy(v0);
            return 1;
        } catch (int v5_2) {
        } catch (int v5_1) {
        }
    }

    public static reflect.InvocationHandler i()
    {
        NoSuchMethodException v0_3;
        if (android.os.Build$VERSION.SDK_INT < 28) {
            try {
                NoSuchMethodException v0_10 = android.webkit.WebView.getDeclaredMethod("getFactory", 0);
                v0_10.setAccessible(1);
                v0_3 = v0_10.invoke(0, 0).getClass().getClassLoader();
            } catch (NoSuchMethodException v0_4) {
                throw new RuntimeException(v0_4);
            }
        } else {
            v0_3 = z.n();
        }
        return ((reflect.InvocationHandler) Class.forName("org.chromium.support_lib_glue.SupportLibReflectionUtil", 0, v0_3).getDeclaredMethod("createWebViewProviderFactory", 0).invoke(0, 0));
    }

    public static android.view.View j(android.view.View p4, int p5)
    {
        if ((p4 instanceof android.view.ViewGroup)) {
            int v0_1 = ((android.view.ViewGroup) p4).getChildCount();
            int v2 = 0;
            while (v2 < v0_1) {
                android.view.View v3_1 = ((android.view.ViewGroup) p4).getChildAt(v2).findViewById(p5);
                if (v3_1 == null) {
                    v2++;
                } else {
                    return v3_1;
                }
            }
            return 0;
        } else {
            return 0;
        }
    }

    public static java.io.File k(android.content.Context p5)
    {
        java.io.File v5_1 = p5.getCacheDir();
        if (v5_1 != null) {
            String v1_2 = new StringBuilder(".font");
            v1_2.append(android.os.Process.myPid());
            v1_2.append("-");
            v1_2.append(android.os.Process.myTid());
            v1_2.append("-");
            String v1_0 = v1_2.toString();
            int v2_1 = 0;
            while (v2_1 < 100) {
                java.io.File v3_3 = new java.io.File(v5_1, g.c(v2_1, v1_0));
                try {
                    if (!v3_3.createNewFile()) {
                        v2_1++;
                    } else {
                        return v3_3;
                    }
                } catch (java.io.IOException) {
                }
            }
            return 0;
        } else {
            return 0;
        }
    }

    public static java.nio.MappedByteBuffer n(android.content.Context p8, android.net.Uri p9)
    {
        try {
            Throwable v8_3 = p8.getContentResolver().openFileDescriptor(p9, "r", 0);
        } catch (java.io.IOException) {
            return 0;
        }
        if (v8_3 != null) {
            try {
                Throwable v9_1 = new java.io.FileInputStream(v8_3.getFileDescriptor());
                try {
                    Throwable v2_0 = v9_1.getChannel();
                    Throwable v0_0 = v2_0.map(java.nio.channels.FileChannel$MapMode.READ_ONLY, 0, v2_0.size());
                } catch (Throwable v0_1) {
                    Throwable v2_1 = v0_1;
                    try {
                        v9_1.close();
                    } catch (Throwable v0_2) {
                        v2_1.addSuppressed(v0_2);
                    }
                    throw v2_1;
                }
                v9_1.close();
                v8_3.close();
                return v0_0;
            } catch (Throwable v0_3) {
                Throwable v9_3 = v0_3;
                try {
                    v8_3.close();
                } catch (Throwable v0_5) {
                    v9_3.addSuppressed(v0_5);
                }
                throw v9_3;
            }
        } else {
            if (v8_3 == null) {
                return 0;
            } else {
                v8_3.close();
                return 0;
            }
        }
    }

    public static final void s(android.view.View p3, int p4)
    {
        float v0_3;
        p3.getClass();
        float v0_2 = p3.getBackground();
        android.graphics.drawable.GradientDrawable v1_1 = 0;
        if (v0_2 == 0) {
            v0_3 = 0;
        } else {
            v0_3 = v0_2.mutate();
        }
        if ((v0_3 instanceof android.graphics.drawable.GradientDrawable)) {
            v1_1 = ((android.graphics.drawable.GradientDrawable) v0_3);
        }
        if (v1_1 != null) {
            float v0_1 = (1073741824 * p3.getResources().getDisplayMetrics().density);
            if (Float.isNaN(v0_1)) {
                e6.g("Cannot round NaN value.");
                return;
            } else {
                v1_1.setStroke(Math.round(v0_1), p4);
                return;
            }
        } else {
            return;
        }
    }

    public static void u(android.view.View p2, CharSequence p3)
    {
        if (android.os.Build$VERSION.SDK_INT < 26) {
            android.view.View v0_4 = w30.k;
            if ((v0_4 != null) && (v0_4.a == p2)) {
                w30.b(0);
            }
            if (!android.text.TextUtils.isEmpty(p3)) {
                new w30(p2, p3);
                return;
            } else {
                int v3_1 = w30.l;
                if ((v3_1 != 0) && (v3_1.a == p2)) {
                    v3_1.a();
                }
                p2.setOnLongClickListener(0);
                p2.setLongClickable(0);
                p2.setOnHoverListener(0);
                return;
            }
        } else {
            z4.k(p2, p3);
            return;
        }
    }

    public static final void w(com.example.instatool.databinding.DialogSheetConfigBinding p3, com.example.instatool.browser.BrowserActivity p4)
    {
        int v0_2;
        int v0_1 = p3.modeCookies.isChecked();
        boolean v1_1 = p3.modeTwoFactor.isChecked();
        boolean v2_1 = p3.modeCustomUsername.isChecked();
        if ((v0_1 == 0) || ((!v1_1) || (!v2_1))) {
            if ((v0_1 == 0) || (!v1_1)) {
                if ((!v1_1) || (!v2_1)) {
                    if (!v1_1) {
                        if ((v0_1 == 0) || (!v2_1)) {
                            if (v0_1 == 0) {
                                v0_2 = 2131689517;
                            } else {
                                v0_2 = 2131689913;
                            }
                        } else {
                            v0_2 = 2131689914;
                        }
                    } else {
                        v0_2 = 2131689915;
                    }
                } else {
                    v0_2 = 2131689916;
                }
            } else {
                v0_2 = 2131689911;
            }
        } else {
            v0_2 = 2131689912;
        }
        p3.sheetColumns.setText(p4.getString(v0_2));
        return;
    }

    public static final String x(com.example.instatool.databinding.DialogSheetConfigBinding p4, com.example.instatool.browser.BrowserActivity p5)
    {
        String v0_7;
        String v0_3 = p4.sheetUrl.getText();
        String v1_0 = 0;
        if (v0_3 == null) {
            v0_7 = 0;
        } else {
            v0_7 = v0_3.toString();
        }
        if (v0_7 == null) {
            v0_7 = "";
        }
        String v0_2 = m10.P(v0_7).toString();
        if (v0_2.length() != 0) {
            boolean v2_2 = java.util.regex.Pattern.compile("/spreadsheets/d/([a-zA-Z0-9-_]+)");
            v2_2.getClass();
            boolean v2_3 = v2_2.matcher(v0_2);
            v2_3.getClass();
            boolean v2_4 = io.o(v2_3, 0, v0_2);
            if (!v2_4) {
                boolean v2_6 = java.util.regex.Pattern.compile("[a-zA-Z0-9-_]{20,}");
                v2_6.getClass();
                if (!v2_6.matcher(v0_2).matches()) {
                    v0_2 = 0;
                }
            } else {
                v0_2 = ((String) ((pr) v2_4.a()).get(1));
            }
        }
        com.google.android.material.textfield.TextInputLayout v4_1 = p4.sheetUrlLayout;
        if (v0_2 == null) {
            v1_0 = p5.getString(2131689922);
        }
        v4_1.setError(v1_0);
        return v0_2;
    }

    public void b()
    {
        return;
    }

    public void c()
    {
        return;
    }

    public abstract void l(int p0);

    public abstract boolean m();

    public abstract void o(int p0);

    public abstract void p(android.graphics.Typeface p0, boolean p1);

    public void q(boolean p1)
    {
        return;
    }

    public abstract void r(boolean p0);

    public abstract void t();

    public abstract void v(int p0);
}
