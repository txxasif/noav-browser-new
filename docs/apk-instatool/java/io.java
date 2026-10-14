public abstract class Lio {
    public static final Object a = None;
    public static final Object[] b = None;
    public static final String[] c = None;
    public static final s5 d = None;
    public static s5 e = None;
    public static final byte[] f = None;
    public static final byte[] g = None;
    public static final byte[] h = None;
    public static final byte[] i = None;
    public static final byte[] j = None;
    public static final byte[] k = None;
    public static final byte[] l = None;
    public static final Object m = None;
    public static boolean n = False;
    public static reflect.Method o = None;
    public static boolean p = False;
    public static reflect.Field q;

    static synthetic io()
    {
        io.a = new Object();
        byte[] v1_6 = new Object[0];
        io.b = v1_6;
        Object v0_8 = new String[0];
        io.c = v0_8;
        io.d = new s5(0, 0, 0);
        byte[] v1_0 = new byte[4];
        v1_0 = {48, 49, 53, 0};
        io.f = v1_0;
        byte[] v1_1 = new byte[4];
        v1_1 = {48, 49, 48, 0};
        io.g = v1_1;
        byte[] v1_2 = new byte[4];
        v1_2 = {48, 48, 57, 0};
        io.h = v1_2;
        byte[] v1_3 = new byte[4];
        v1_3 = {48, 48, 53, 0};
        io.i = v1_3;
        byte[] v1_4 = new byte[4];
        v1_4 = {48, 48, 49, 0};
        io.j = v1_4;
        byte[] v1_5 = new byte[4];
        v1_5 = {48, 48, 49, 0};
        io.k = v1_5;
        Object v0_5 = new byte[4];
        v0_5 = {48, 48, 50, 0};
        io.l = v0_5;
        io.m = new Object();
        return;
    }

    public static nk A(android.content.res.XmlResourceParser p26, android.content.res.Resources p27)
    {
        do {
            String v1_1 = p26.next();
            int v3_3 = 2;
        } while((v1_1 == 2) || (v1_1 == 1));
        if (v1_1 != 2) {
            throw new org.xmlpull.v1.XmlPullParserException("No start tag found");
        } else {
            p26.require(2, 0, "font-family");
            if (!p26.getName().equals("font-family")) {
                io.S(p26);
                return 0;
            } else {
                int v4_5 = p27.obtainAttributes(android.util.Xml.asAttributeSet(p26), vv.b);
                int v6_11 = 0;
                int v8_2 = v4_5.getString(0);
                int v9_1 = v4_5.getString(5);
                String v14 = v4_5.getString(6);
                String v15 = v4_5.getString(2);
                int v11_3 = v4_5.getResourceId(1, 0);
                int v12_4 = 3;
                int v13_3 = v4_5.getInteger(3, 1);
                String v1_4 = v4_5.getInteger(4, 500);
                pk v2_3 = v4_5.getString(7);
                v4_5.recycle();
                if ((v8_2 == 0) || (v9_1 == 0)) {
                    String v1_6 = new java.util.ArrayList();
                    while (p26.next() != 3) {
                        if (p26.getEventType() == 2) {
                            if (!p26.getName().equals("font")) {
                                int v9 = 5;
                                io.S(p26);
                            } else {
                                pk v2_10 = p27.obtainAttributes(android.util.Xml.asAttributeSet(p26), vv.c);
                                int v6_16 = 8;
                                if (!v2_10.hasValue(8)) {
                                    v6_16 = 1;
                                }
                                int v6_1;
                                int v20 = v2_10.getInt(v6_16, 400);
                                if (!v2_10.hasValue(6)) {
                                    v6_1 = 2;
                                } else {
                                    v6_1 = 6;
                                }
                                int v21;
                                if (1 != v2_10.getInt(v6_1, 0)) {
                                    v21 = 0;
                                } else {
                                    v21 = 1;
                                }
                                int v12_0 = 9;
                                if (!v2_10.hasValue(9)) {
                                    v12_0 = 3;
                                }
                                int v6_5;
                                if (!v2_10.hasValue(7)) {
                                    v6_5 = 4;
                                } else {
                                    v6_5 = 7;
                                }
                                int v11_1;
                                String v22 = v2_10.getString(v6_5);
                                int v23 = v2_10.getInt(v12_0, 0);
                                if (!v2_10.hasValue(5)) {
                                    v11_1 = 0;
                                } else {
                                    v11_1 = 5;
                                }
                                int v24 = v2_10.getResourceId(v11_1, 0);
                                String v19 = v2_10.getString(v11_1);
                                v2_10.recycle();
                                while (p26.next() != 3) {
                                    io.S(p26);
                                }
                                v1_6.add(new pk(v19, v20, v21, v22, v23, v24));
                            }
                        }
                    }
                    if (!v1_6.isEmpty()) {
                        pk v2_5 = new pk[0];
                        return new ok(((pk[]) v1_6.toArray(v2_5)));
                    } else {
                        return 0;
                    }
                } else {
                    int v11_2 = io.E(p27, v11_3);
                    int v4_2 = new java.util.ArrayList();
                    while (p26.next() != v12_4) {
                        if (p26.getEventType() == v3_3) {
                            int v6_9;
                            int v3_0;
                            if (!p26.getName().equals("fallback")) {
                                v3_0 = v12_4;
                                v6_9 = v13_3;
                                io.S(p26);
                            } else {
                                gk v7_9 = p27.obtainAttributes(android.util.Xml.asAttributeSet(p26), vv.d);
                                try {
                                    int v17_1;
                                    String v10_4 = v7_9.getString(v6_11);
                                    int v17_0 = v7_9.getString(1);
                                    v6_9 = v13_3;
                                    int v13_2 = v7_9.getString(v3_3);
                                    try {
                                        if (v10_4 == null) {
                                            v17_1 = v7_9;
                                            throw new org.xmlpull.v1.XmlPullParserException("query attribute must be set in fallback element");
                                        }
                                        while (p26.next() != v12_4) {
                                            io.S(p26);
                                        }
                                        try {
                                            v17_1 = v7_9;
                                            v3_0 = v12_4;
                                        } catch (Throwable v0_10) {
                                            v17_1 = v3_0;
                                            v17_1.recycle();
                                            throw v0_10;
                                        }
                                        gk v7_11 = new gk(v8_2, v9_1, v10_4, v11_2, v17_0, v13_2);
                                        v17_1.recycle();
                                        v4_2.add(v7_11);
                                    } catch (Throwable v0_10) {
                                    }
                                } catch (Throwable v0_10) {
                                    v17_1 = v7_9;
                                }
                            }
                            v12_4 = v3_0;
                            v13_3 = v6_9;
                            v3_3 = 2;
                            v6_11 = 0;
                        }
                    }
                    int v6_7 = v13_3;
                    if (v4_2.isEmpty()) {
                        if (v14 == null) {
                            e6.g("The provider font XML requires query attribute or fallback children.");
                            return 0;
                        } else {
                            v4_2.add(new gk(v8_2, v9_1, v14, v11_2, 0, 0));
                            if (v15 != null) {
                                v4_2.add(new gk(v8_2, v9_1, v15, v11_2, 0, 0));
                            }
                            return new qk(v4_2, v6_7, v1_4, v2_3);
                        }
                    } else {
                        return new qk(v4_2, v6_7, v1_4, v2_3);
                    }
                }
            }
        }
    }

    public static void B(android.content.Context p5, String p6)
    {
        try {
            if (!p6.equals("")) {
                String v5_2 = p5.openFileOutput("androidx.appcompat.app.AppCompatDelegate.application_locales_record_file", 0);
                String v1_1 = android.util.Xml.newSerializer();
                try {
                    v1_1.setOutput(v5_2, 0);
                    v1_1.startDocument("UTF-8", Boolean.TRUE);
                    v1_1.startTag(0, "locales");
                    v1_1.attribute(0, "application_locales", p6);
                    v1_1.endTag(0, "locales");
                    v1_1.endDocument();
                } catch (Throwable v6_3) {
                    android.util.Log.w("AppLocalesStorageHelper", "Storing App Locales : Failed to persist app-locales in storage ", v6_3);
                    if (v5_2 == null) {
                        return;
                    } else {
                        v5_2.close();
                    }
                } catch (Throwable v6_4) {
                    if (v5_2 != null) {
                        v5_2.close();
                    }
                    throw v6_4;
                }
                if (v5_2 == null) {
                } else {
                }
            } else {
                p5.deleteFile("androidx.appcompat.app.AppCompatDelegate.application_locales_record_file");
                return;
            }
        } catch (String v5_1) {
            throw v5_1;
        }
    }

    public static pt C(java.nio.MappedByteBuffer p13)
    {
        short v13_1 = p13.duplicate();
        v13_1.order(java.nio.ByteOrder.BIG_ENDIAN);
        v13_1.position((v13_1.position() + 4));
        pt v0_0 = (v13_1.getShort() & 65535);
        if (v0_0 > 100) {
            throw new java.io.IOException("Cannot read metadata.");
        } else {
            v13_1.position((v13_1.position() + 6));
            int v1_4 = 0;
            int v3_0 = 0;
            while (v3_0 < v0_0) {
                int v8 = v13_1.getInt();
                v13_1.position((v13_1.position() + 4));
                long v9_0 = (((long) v13_1.getInt()) & 4294967295);
                v13_1.position((v13_1.position() + 4));
                if (1835365473 != v8) {
                    v3_0++;
                }
                if (v9_0 != -1) {
                    v13_1.position((v13_1.position() + ((int) (v9_0 - ((long) v13_1.position())))));
                    v13_1.position((v13_1.position() + 12));
                    long v6_4 = (((long) v13_1.getInt()) & 4294967295);
                    while (((long) v1_4) < v6_4) {
                        pt v0_11 = v13_1.getInt();
                        long v11_5 = (((long) v13_1.getInt()) & 4294967295);
                        v13_1.getInt();
                        if ((1164798569 != v0_11) && (1701669481 != v0_11)) {
                            v1_4++;
                        } else {
                            v13_1.position(((int) (v11_5 + v9_0)));
                            pt v0_14 = new pt();
                            v13_1.order(java.nio.ByteOrder.LITTLE_ENDIAN);
                            int v2_3 = (v13_1.position() + v13_1.getInt(v13_1.position()));
                            v0_14.d = v13_1;
                            v0_14.a = v2_3;
                            int v2_0 = (v2_3 - v13_1.getInt(v2_3));
                            v0_14.b = v2_0;
                            v0_14.c = ((java.nio.ByteBuffer) v0_14.d).getShort(v2_0);
                            return v0_14;
                        }
                    }
                }
                throw new java.io.IOException("Cannot read metadata.");
            }
            v9_0 = -1;
        }
    }

    public static final byte[] D(java.io.InputStream p3)
    {
        java.io.ByteArrayOutputStream v0_1 = new java.io.ByteArrayOutputStream(Math.max(8192, p3.available()));
        io.i(p3, v0_1);
        byte[] v3_1 = v0_1.toByteArray();
        v3_1.getClass();
        return v3_1;
    }

    public static java.util.List E(android.content.res.Resources p8, int p9)
    {
        if (p9 != 0) {
            android.content.res.TypedArray v0 = p8.obtainTypedArray(p9);
            try {
                if (v0.length() != 0) {
                    java.util.ArrayList v1_2 = new java.util.ArrayList();
                    if (v0.getType(0) != 1) {
                        String[] v8_1 = p8.getStringArray(p9);
                        int v9_2 = new java.util.ArrayList();
                        String[] v3_1 = v8_1.length;
                        java.util.ArrayList v4_1 = 0;
                        while (v4_1 < v3_1) {
                            v9_2.add(android.util.Base64.decode(v8_1[v4_1], 0));
                            v4_1++;
                        }
                        v1_2.add(v9_2);
                    } else {
                        int v9_3 = 0;
                        while (v9_3 < v0.length()) {
                            String[] v3_3 = v0.getResourceId(v9_3, 0);
                            if (v3_3 != null) {
                                String[] v3_4 = p8.getStringArray(v3_3);
                                java.util.ArrayList v4_3 = new java.util.ArrayList();
                                int v5_2 = v3_4.length;
                                int v6 = 0;
                                while (v6 < v5_2) {
                                    v4_3.add(android.util.Base64.decode(v3_4[v6], 0));
                                    v6++;
                                }
                                v1_2.add(v4_3);
                            }
                            v9_3++;
                        }
                    }
                    v0.recycle();
                    return v1_2;
                } else {
                    v0.recycle();
                    return java.util.Collections.EMPTY_LIST;
                }
            } catch (String[] v8_2) {
                v0.recycle();
                throw v8_2;
            }
        } else {
            return java.util.Collections.EMPTY_LIST;
        }
    }

    public static String F(android.content.Context p8)
    {
        try {
            String v1 = "";
        } catch (Throwable v8_1) {
            throw v8_1;
        }
        String v2_1 = p8.openFileInput("androidx.appcompat.app.AppCompatDelegate.application_locales_record_file");
        String v3_1 = android.util.Xml.newPullParser();
        v3_1.setInput(v2_1, "UTF-8");
        String v4_0 = v3_1.getDepth();
        do {
            int v5_0 = v3_1.next();
            if (v5_0 != 1) {
                if (v5_0 == 3) {
                    if (v3_1.getDepth() <= v4_0) {
                        if (v2_1 == null) {
                            if (v1.isEmpty()) {
                                p8.deleteFile("androidx.appcompat.app.AppCompatDelegate.application_locales_record_file");
                            } else {
                            }
                            return v1;
                        } else {
                            v2_1.close();
                        }
                    } else {
                    }
                }
                if (v5_0 != 3) {
                    if (v5_0 != 4) {
                    } else {
                    }
                }
            }
        } while(!v3_1.getName().equals("locales"));
        v1 = v3_1.getAttributeValue(0, "application_locales");
    }

    public static void G(com.google.android.material.textfield.TextInputLayout p5, com.google.android.material.internal.CheckableImageButton p6, android.content.res.ColorStateList p7)
    {
        android.graphics.drawable.Drawable v0 = p6.getDrawable();
        if ((p6.getDrawable() != null) && ((p7 != null) && (p7.isStateful()))) {
            android.content.res.ColorStateList v5_1 = p5.getDrawableState();
            int v1_0 = p6.getDrawableState();
            int v2 = v5_1.length;
            android.content.res.ColorStateList v5_2 = java.util.Arrays.copyOf(v5_1, (v5_1.length + v1_0.length));
            System.arraycopy(v1_0, 0, v5_2, v2, v1_0.length);
            android.content.res.ColorStateList v5_3 = p7.getColorForState(v5_2, p7.getDefaultColor());
            android.graphics.drawable.Drawable v7_1 = v0.mutate();
            v7_1.setTintList(android.content.res.ColorStateList.valueOf(v5_3));
            p6.setImageDrawable(v7_1);
        }
        return;
    }

    public static android.util.TypedValue H(android.content.res.Resources$Theme p2, int p3)
    {
        android.util.TypedValue v0_1 = new android.util.TypedValue();
        if (!p2.resolveAttribute(p3, v0_1, 1)) {
            return 0;
        } else {
            return v0_1;
        }
    }

    public static boolean I(android.content.res.Resources$Theme p1, int p2, boolean p3)
    {
        int v1_1 = io.H(p1, p2);
        if ((v1_1 == 0) || (v1_1.type != 18)) {
            return p3;
        } else {
            if (v1_1.data == 0) {
                return 0;
            } else {
                return 1;
            }
        }
    }

    public static int J(android.content.Context p1, int p2, int p3)
    {
        int v1_2 = io.H(p1.getTheme(), p2);
        if ((v1_2 == 0) || (v1_2.type != 16)) {
            return p3;
        } else {
            return v1_2.data;
        }
    }

    public static android.util.TypedValue K(int p1, android.content.Context p2, String p3)
    {
        IllegalArgumentException v0_2 = io.H(p2.getTheme(), p1);
        if (v0_2 == null) {
            throw new IllegalArgumentException(String.format("%1$s requires a value for the %2$s attribute to be set in your app theme. You can either set the attribute in your theme or update your theme to inherit from Theme.MaterialComponents (or a descendant).", new Object[] {p3, p2.getResources().getResourceName(p1)})));
        } else {
            return v0_2;
        }
    }

    public static void L(RuntimeException p5, String p6)
    {
        StackTraceElement[] v0 = p5.getStackTrace();
        int v1 = v0.length;
        int v2_0 = -1;
        int v3 = 0;
        while (v3 < v1) {
            if (p6.equals(v0[v3].getClassName())) {
                v2_0 = v3;
            }
            v3++;
        }
        p5.setStackTrace(((StackTraceElement[]) java.util.Arrays.copyOfRange(v0, (v2_0 + 1), v1)));
        return;
    }

    public static boolean M(android.content.Context p12, k9 p13, String p14, String p15)
    {
        p14.getClass();
        Throwable v0_14 = m10.E(p14, 44, 0, 6);
        if ((p14.startsWith("data:")) && (v0_14 >= null)) {
            String v3_1 = p14.substring(5, v0_14);
            int v4_1 = m10.N(v3_1, 59);
            if (v4_1.length() == 0) {
                v4_1 = "application/octet-stream";
            }
            String[] v14_5;
            String v8 = v4_1;
            String[] v14_3 = p14.substring((v0_14 + 1));
            if (!v3_1.endsWith(";base64")) {
                String[] v14_4 = android.net.Uri.decode(v14_3);
                v14_4.getClass();
                v14_5 = v14_4.getBytes(ka.a);
                v14_5.getClass();
            } else {
                v14_5 = android.util.Base64.decode(v14_3, 0);
            }
            if (android.os.Build$VERSION.SDK_INT < 29) {
                Throwable v13_3 = android.os.Environment.getExternalStoragePublicDirectory(android.os.Environment.DIRECTORY_DOWNLOADS);
                v13_3.mkdirs();
                lx v15_2 = new lx();
                v15_2.a = new java.io.File(v13_3, p15);
                Throwable v0_3 = 1;
                while (((java.io.File) v15_2.a).exists()) {
                    String v6_5;
                    String v6_4 = m10.H(p15, 46);
                    if (v6_4 != -1) {
                        v6_5 = p15.substring(0, v6_4);
                    } else {
                        v6_5 = p15;
                    }
                    int v9_2 = (v0_3 + 1);
                    String v10_1 = "";
                    java.io.File v1_12 = m10.M(p15, 46, "");
                    if (v1_12.length() != 0) {
                        v10_1 = ".".concat(v1_12);
                    }
                    java.io.File v1_1 = new StringBuilder(v6_5);
                    v1_1.append(" (");
                    v1_1.append(v0_3);
                    v1_1.append(")");
                    v1_1.append(v10_1);
                    v15_2.a = new java.io.File(v13_3, v1_1.toString());
                    v0_3 = v9_2;
                }
                Throwable v13_5 = ((java.io.File) v15_2.a);
                v14_5.getClass();
                v13_5.getClass();
                java.io.File v1_10 = new java.io.FileOutputStream(v13_5);
                try {
                    v1_10.write(v14_5);
                    v1_10.close();
                    android.media.MediaScannerConnection.scanFile(p12, new String[] {((java.io.File) v15_2.a).getAbsolutePath()}), new String[] {v8}), new jf(p13, v3_1, v15_2, v8));
                    return 1;
                } catch (Throwable v0_19) {
                    Throwable v12_3 = v0_19;
                    try {
                        throw v12_3;
                    } catch (Throwable v0_20) {
                        Throwable v13_10 = v0_20;
                        c8.i(v1_10, v12_3);
                        throw v13_10;
                    }
                }
            } else {
                Throwable v12_1 = p12.getContentResolver();
                Throwable v0_5 = new android.content.ContentValues();
                v0_5.put("_display_name", p15);
                v0_5.put("mime_type", v8);
                v0_5.put("relative_path", android.os.Environment.DIRECTORY_DOWNLOADS);
                v0_5.put("is_pending", Integer.valueOf(1));
                Throwable v0_6 = v12_1.insert(b0.g(), v0_5);
                if (v0_6 != null) {
                    java.io.File v5_5 = v12_1.openOutputStream(v0_6);
                    if (v5_5 != null) {
                        try {
                            v5_5.write(v14_5);
                            v5_5.close();
                            String[] v14_2 = new android.content.ContentValues();
                            v14_2.put("is_pending", Integer.valueOf(0));
                            v12_1.update(v0_6, v14_2, 0, 0);
                            p13.b("data:".concat(v3_1), p15, v8, v0_6.toString(), -1);
                            return 1;
                        } catch (Throwable v0_7) {
                            Throwable v12_2 = v0_7;
                            try {
                                throw v12_2;
                            } catch (Throwable v0_8) {
                                Throwable v13_1 = v0_8;
                                c8.i(p13, v12_2);
                                throw v13_1;
                            }
                        }
                    }
                }
            }
        }
        return 0;
    }

    public static void P(com.google.android.material.internal.CheckableImageButton p4, android.view.View$OnLongClickListener p5)
    {
        int v5_1;
        int v0_0 = p4.hasOnClickListeners();
        int v1 = 0;
        int v2 = 1;
        if (p5 == 0) {
            v5_1 = 0;
        } else {
            v5_1 = 1;
        }
        if ((v0_0 != 0) || (v5_1 != 0)) {
            v1 = 1;
        }
        p4.setFocusable(v1);
        p4.setClickable(v0_0);
        p4.setPressable(v0_0);
        if ((android.os.Build$VERSION.SDK_INT >= 26) || ((v1 == 0) || (v5_1 != 0))) {
            p4.setLongClickable(v5_1);
        }
        if (v1 == 0) {
            v2 = 2;
        }
        p4.setImportantForAccessibility(v2);
        return;
    }

    public static void Q(android.view.View p2, ms p3)
    {
        float v0_1 = p3.b.b;
        if ((v0_1 != 0) && (v0_1.a)) {
            ks v2_2 = p2.getParent();
            float v0_2 = 0;
            while ((v2_2 instanceof android.view.View)) {
                v0_2 += ((android.view.View) v2_2).getElevation();
                v2_2 = v2_2.getParent();
            }
            ks v2_1 = p3.b;
            if (v2_1.l != v0_2) {
                v2_1.l = v0_2;
                p3.x();
            }
        }
        return;
    }

    public static void R(android.view.inputmethod.EditorInfo p2, CharSequence p3, int p4, int p5)
    {
        if (p2.extras == null) {
            p2.extras = new android.os.Bundle();
        }
        String v0_4;
        if (p3 == null) {
            v0_4 = 0;
        } else {
            v0_4 = new android.text.SpannableStringBuilder(p3);
        }
        p2.extras.putCharSequence("androidx.core.view.inputmethod.EditorInfoCompat.CONTENT_SURROUNDING_TEXT", v0_4);
        p2.extras.putInt("androidx.core.view.inputmethod.EditorInfoCompat.CONTENT_SELECTION_HEAD", p4);
        p2.extras.putInt("androidx.core.view.inputmethod.EditorInfoCompat.CONTENT_SELECTION_END", p5);
        return;
    }

    public static void S(org.xmlpull.v1.XmlPullParser p3)
    {
        int v0 = 1;
        while (v0 > 0) {
            int v1 = p3.next();
            if (v1 == 2) {
                v0++;
            } else {
                if (v1 == 3) {
                    v0--;
                }
            }
        }
        return;
    }

    public static void T(String p2)
    {
        uk v0_2 = new uk(g.e("lateinit property ", p2, " has not been initialized"));
        io.L(v0_2, io.getName());
        throw v0_2;
    }

    public static final Object[] U(java.util.Collection p4)
    {
        Object[] v0_0 = p4.size();
        if (v0_0 != null) {
            OutOfMemoryError v4_5 = p4.iterator();
            if (v4_5.hasNext()) {
                Object[] v0_1 = new Object[v0_0];
                int v1_6 = 0;
                while(true) {
                    int v2 = (v1_6 + 1);
                    v0_1[v1_6] = v4_5.next();
                    if (v2 < v0_1.length) {
                        if (!v4_5.hasNext()) {
                            break;
                        }
                    } else {
                        if (v4_5.hasNext()) {
                            int v1_5 = (((v2 * 3) + 1) >> 1);
                            if (v1_5 <= v2) {
                                v1_5 = 2147483645;
                                if (v2 >= 2147483645) {
                                    throw new OutOfMemoryError();
                                }
                            }
                            v0_1 = java.util.Arrays.copyOf(v0_1, v1_5);
                        } else {
                            return v0_1;
                        }
                    }
                    v1_6 = v2;
                }
                return java.util.Arrays.copyOf(v0_1, v2);
            }
        }
        return io.b;
    }

    public static final Object[] V(java.util.Collection p5, Object[] p6)
    {
        Object[] v0_0 = p5.size();
        int v2_2 = 0;
        if (v0_0 != null) {
            OutOfMemoryError v5_6 = p5.iterator();
            if (v5_6.hasNext()) {
                Object[] v0_2;
                if (v0_0 > p6.length) {
                    Object[] v0_1 = reflect.Array.newInstance(p6.getClass().getComponentType(), v0_0);
                    v0_1.getClass();
                    v0_2 = ((Object[]) v0_1);
                } else {
                    v0_2 = p6;
                }
                while(true) {
                    int v3_3 = (v2_2 + 1);
                    v0_2[v2_2] = v5_6.next();
                    if (v3_3 < v0_2.length) {
                        if (!v5_6.hasNext()) {
                            break;
                        }
                    } else {
                        if (v5_6.hasNext()) {
                            int v2_6 = (((v3_3 * 3) + 1) >> 1);
                            if (v2_6 <= v3_3) {
                                v2_6 = 2147483645;
                                if (v3_3 >= 2147483645) {
                                    throw new OutOfMemoryError();
                                }
                            }
                            v0_2 = java.util.Arrays.copyOf(v0_2, v2_6);
                        } else {
                            return v0_2;
                        }
                    }
                    v2_2 = v3_3;
                }
                if (v0_2 != p6) {
                    return java.util.Arrays.copyOf(v0_2, v3_3);
                } else {
                    p6[v3_3] = 0;
                    return p6;
                }
            } else {
                if (p6.length > 0) {
                    p6[0] = 0;
                }
            }
        } else {
            if (p6.length > 0) {
                p6[0] = 0;
                return p6;
            }
        }
        return p6;
    }

    public static final kj W(java.io.File p6)
    {
        java.io.File v2_2;
        kj v6_1 = p6.getPath();
        v6_1.getClass();
        kj v0_0 = java.io.File.separatorChar;
        char v3_10 = m10.E(v6_1, v0_0, 0, 4);
        if (v3_10 != 0) {
            if ((v3_10 <= 0) || (v6_1.charAt((v3_10 - 1)) != 58)) {
                if ((v3_10 != -1) || ((v6_1.length() <= 0) || (!io.n(v6_1.charAt((v6_1.length() - 1)), 58, 0)))) {
                    v2_2 = 0;
                } else {
                    v2_2 = v6_1.length();
                }
            } else {
                v2_2 = (v3_10 + 1);
            }
        } else {
            if ((v6_1.length() > 1) && (v6_1.charAt(1) == v0_0)) {
                char v3_7 = m10.E(v6_1, v0_0, 2, 4);
                if (v3_7 >= 0) {
                    java.io.File v2_3 = m10.E(v6_1, v0_0, (v3_7 + 1), 4);
                    if (v2_3 < null) {
                        v2_2 = v6_1.length();
                        kj v6_5;
                        char v3_9 = v6_1.substring(0, v2_2);
                        kj v6_2 = v6_1.substring(v2_2);
                        if (v6_2.length() != 0) {
                            java.io.File v2_6 = new char[1];
                            v2_6[0] = v0_0;
                            kj v6_3 = m10.K(v6_2, v2_6);
                            kj v0_2 = new java.util.ArrayList(tb.e0(v6_3));
                            kj v6_4 = v6_3.iterator();
                            while (v6_4.hasNext()) {
                                v0_2.add(new java.io.File(((String) v6_4.next())));
                            }
                            v6_5 = v0_2;
                        } else {
                            v6_5 = qh.a;
                        }
                        return new kj(new java.io.File(v3_9), v6_5);
                    } else {
                        v2_2 = (v2_3 + 1);
                    }
                }
            }
            v2_2 = 1;
        }
    }

    public static void X(com.google.android.material.internal.CheckableImageButton p2, android.view.View$OnLongClickListener p3, CharSequence p4)
    {
        if (!p2.isFocusable()) {
            p4 = 0;
        }
        if (android.os.Build$VERSION.SDK_INT < 26) {
            if (p3 == null) {
                hz.u(p2, p4);
            }
            return;
        } else {
            a0.l(p2, p4);
            return;
        }
    }

    public static String Y(java.util.List p8)
    {
        StringBuilder v0_1 = new StringBuilder();
        v0_1.append("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><worksheet xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\"><sheetData>");
        io.b(v0_1, 1, sb.b0(new String[] {"Row", "Email/Username", "Password", "Status/Cookies", "2FA Key"})));
        int v8_2 = rb.o0(p8, new ed(4)).iterator();
        int v1_5 = 0;
        while (v8_2.hasNext()) {
            java.util.List v2_3 = v8_2.next();
            int v3_0 = (v1_5 + 1);
            if (v1_5 < 0) {
                sb.d0();
                throw 0;
            } else {
                java.util.List v2_4 = ((nm) v2_3);
                io.b(v0_1, (v1_5 + 2), sb.b0(new String[] {String.valueOf(v2_4.a), v2_4.b, v2_4.c, v2_4.d, v2_4.e})));
                v1_5 = v3_0;
            }
        }
        v0_1.append("</sheetData></worksheet>");
        return v0_1.toString();
    }

    public static void a(java.util.zip.ZipOutputStream p1, String p2, String p3)
    {
        p1.putNextEntry(new java.util.zip.ZipEntry(p2));
        byte[] v2_2 = p3.getBytes(ka.a);
        v2_2.getClass();
        p1.write(v2_2);
        p1.closeEntry();
        return;
    }

    public static void a0(java.util.List p2, java.io.OutputStream p3)
    {
        java.util.zip.ZipOutputStream v0_1 = new java.util.zip.ZipOutputStream(p3, ka.a);
        try {
            io.a(v0_1, "[Content_Types].xml", "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\"><Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/><Default Extension=\"xml\" ContentType=\"application/xml\"/><Override PartName=\"/xl/workbook.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml\"/><Override PartName=\"/xl/worksheets/sheet1.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml\"/></Types>");
            io.a(v0_1, "_rels/.rels", "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\"><Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"xl/workbook.xml\"/></Relationships>");
            io.a(v0_1, "xl/workbook.xml", "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><workbook xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\" xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\"><sheets><sheet name=\"Accounts\" sheetId=\"1\" r:id=\"rId1\"/></sheets></workbook>");
            io.a(v0_1, "xl/_rels/workbook.xml.rels", "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\"><Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet\" Target=\"worksheets/sheet1.xml\"/></Relationships>");
            io.a(v0_1, "xl/worksheets/sheet1.xml", io.Y(p2));
            v0_1.close();
            return;
        } catch (Throwable v2_2) {
            try {
                throw v2_2;
            } catch (Throwable v3_3) {
                c8.i(v0_1, v2_2);
                throw v3_3;
            }
        }
    }

    public static void b(StringBuilder p6, int p7, java.util.List p8)
    {
        int v0_2 = new StringBuilder("<row r=\"");
        v0_2.append(p7);
        v0_2.append("\">");
        p6.append(v0_2.toString());
        String v8_1 = p8.iterator();
        int v1_1 = 0;
        while (v8_1.hasNext()) {
            String v2_1 = v8_1.next();
            int v3 = (v1_1 + 1);
            if (v1_1 < 0) {
                sb.d0();
                throw 0;
            } else {
                String v2_2 = ((String) v2_1);
                if ((1 > v3) || (v3 >= 27)) {
                    String v7_3 = new StringBuilder("Unsupported column: ");
                    v7_3.append(v3);
                    throw new IllegalStateException(v7_3.toString().toString());
                } else {
                    int v1_5 = String.valueOf(((char) (v1_1 + 65)));
                    int v4_3 = new StringBuilder("<c r=\"");
                    v4_3.append(v1_5);
                    v4_3.append(p7);
                    v4_3.append("\" t=\"inlineStr\"><is><t xml:space=\"preserve\">");
                    p6.append(v4_3.toString());
                    int v1_8 = 0;
                    while (v1_8 < v2_2.length()) {
                        int v4_5 = Character.codePointAt(v2_2, v1_8);
                        if (v4_5 == 38) {
                            p6.append("&amp;");
                        } else {
                            if (v4_5 == 60) {
                                p6.append("&lt;");
                            } else {
                                if (v4_5 == 62) {
                                    p6.append("&gt;");
                                } else {
                                    if (((v4_5 == 9) || ((v4_5 == 10) || ((v4_5 == 13) || ((32 <= v4_5) && (v4_5 < 55296))))) || (((57344 <= v4_5) && (v4_5 < 65534)) || ((65536 <= v4_5) && (v4_5 < 1114112)))) {
                                        p6.appendCodePoint(v4_5);
                                    }
                                }
                            }
                        }
                        v1_8 += Character.charCount(v4_5);
                    }
                    p6.append("</t></is></c>");
                    v1_1 = v3;
                }
            }
        }
        p6.append("</row>");
        return;
    }

    public static void c(com.google.android.material.textfield.TextInputLayout p5, com.google.android.material.internal.CheckableImageButton p6, android.content.res.ColorStateList p7, android.graphics.PorterDuff$Mode p8)
    {
        android.graphics.drawable.Drawable v0 = p6.getDrawable();
        if (v0 != null) {
            v0 = v0.mutate();
            if ((p7 == null) || (!p7.isStateful())) {
                v0.setTintList(p7);
            } else {
                android.content.res.ColorStateList v5_1 = p5.getDrawableState();
                int v1_0 = p6.getDrawableState();
                int v2 = v5_1.length;
                android.content.res.ColorStateList v5_2 = java.util.Arrays.copyOf(v5_1, (v5_1.length + v1_0.length));
                System.arraycopy(v1_0, 0, v5_2, v2, v1_0.length);
                v0.setTintList(android.content.res.ColorStateList.valueOf(p7.getColorForState(v5_2, p7.getDefaultColor())));
            }
            if (p8 != null) {
                v0.setTintMode(p8);
            }
        }
        if (p6.getDrawable() != v0) {
            p6.setImageDrawable(v0);
        }
        return;
    }

    public static boolean d(Object p0, Object p1)
    {
        if (p0 != 0) {
            return p0.equals(p1);
        } else {
            if (p1 != null) {
                return 0;
            } else {
                return 1;
            }
        }
    }

    public static final void e(android.view.View p3)
    {
        mz v0_1 = new mz();
        int v1_4 = new o60(p3, v0_1);
        v1_4.c = v0_1;
        v0_1.d = v1_4;
        while (v0_1.hasNext()) {
            ClassCastException v3_2 = ((android.view.View) v0_1.next());
            int v2_1 = ((bv) v3_2.getTag(2131231201));
            if (v2_1 == 0) {
                v2_1 = new bv();
                v3_2.setTag(2131231201, v2_1);
            }
            ClassCastException v3_3 = v2_1.a;
            int v1_3 = (v3_3.size() - 1);
            if (-1 < v1_3) {
                throw g.b(v3_3, v1_3);
            }
        }
        return;
    }

    public static void f(int p3, int p4, int p5)
    {
        if ((p3 < null) || (p4 > p5)) {
            StringBuilder v2_1 = new StringBuilder("fromIndex: ");
            v2_1.append(p3);
            v2_1.append(", toIndex: ");
            v2_1.append(p4);
            v2_1.append(", size: ");
            v2_1.append(p5);
            throw new IndexOutOfBoundsException(v2_1.toString());
        } else {
            if (p3 > p4) {
                e6.g(g.d("fromIndex: ", p3, " > toIndex: ", p4));
                return;
            } else {
                return;
            }
        }
    }

    public static int g(android.content.Context p2, String p3)
    {
        if (p3 == null) {
            throw new NullPointerException("permission must be non-null");
        } else {
            if ((android.os.Build$VERSION.SDK_INT >= 33) || (!android.text.TextUtils.equals("android.permission.POST_NOTIFICATIONS", p3))) {
                return p2.checkPermission(p3, android.os.Process.myPid(), android.os.Process.myUid());
            } else {
                if (!new fu(p2).a.areNotificationsEnabled()) {
                    return -1;
                } else {
                    return 0;
                }
            }
        }
    }

    public static android.widget.ImageView$ScaleType h(int p1)
    {
        if (p1 == null) {
            return android.widget.ImageView$ScaleType.FIT_XY;
        } else {
            if (p1 == 1) {
                return android.widget.ImageView$ScaleType.FIT_START;
            } else {
                if (p1 == 2) {
                    return android.widget.ImageView$ScaleType.FIT_CENTER;
                } else {
                    if (p1 == 3) {
                        return android.widget.ImageView$ScaleType.FIT_END;
                    } else {
                        if (p1 == 5) {
                            return android.widget.ImageView$ScaleType.CENTER_CROP;
                        } else {
                            if (p1 == 6) {
                                return android.widget.ImageView$ScaleType.CENTER_INSIDE;
                            } else {
                                return android.widget.ImageView$ScaleType.CENTER;
                            }
                        }
                    }
                }
            }
        }
    }

    public static final long i(java.io.InputStream p6, java.io.OutputStream p7)
    {
        byte[] v0_1 = new byte[8192];
        int v1 = p6.read(v0_1);
        long v2 = 0;
        while (v1 >= 0) {
            p7.write(v0_1, 0, v1);
            v2 += ((long) v1);
            v1 = p6.read(v0_1);
        }
        return v2;
    }

    public static ik j(android.content.Context p13)
    {
        hk v0_3;
        if (android.os.Build$VERSION.SDK_INT < 28) {
            v0_3 = new pg(13);
        } else {
            v0_3 = new qd(13);
        }
        String v1_4 = p13.getPackageManager();
        p40.j(v1_4, "Package manager required to locate emoji font provider");
        int v3_1 = 0;
        int v2_4 = v1_4.queryIntentContentProviders(new android.content.Intent("androidx.content.action.LOAD_EMOJI_FONT"), 0).iterator();
        do {
            byte[] v4_1;
            ik v5_0 = 0;
            if (!v2_4.hasNext()) {
                v4_1 = 0;
                break;
            } else {
                v4_1 = ((android.content.pm.ResolveInfo) v2_4.next()).providerInfo;
                if (v4_1 != null) {
                    gk v6_0 = v4_1.applicationInfo;
                }
            }
        } while((v6_0 == null) || ((v6_0.flags & 1) != 1));
        gk v6_4;
        if (v4_1 != null) {
            try {
                String v7_1 = v4_1.authority;
                String v8 = v4_1.packageName;
                hk v0_2 = v0_3.k(v1_4, v8);
                String v1_2 = new java.util.ArrayList();
                int v2_6 = v0_2.length;
            } catch (hk v0_4) {
                android.util.Log.wtf("emoji2.text.DefaultEmojiConfig", v0_4);
                v6_4 = 0;
            }
            while (v3_1 < v2_6) {
                v1_2.add(v0_2[v3_1].toByteArray());
                v3_1++;
            }
            v6_4 = new gk(v7_1, v8, "emojicompat-emoji-font", java.util.Collections.singletonList(v1_2), 0, 0);
        }
        if (v6_4 != null) {
            v5_0 = new ik(new hk(p13, v6_4));
        }
        return v5_0;
    }

    public static c8 k(int p1)
    {
        if (p1 == null) {
            return new oy();
        } else {
            if (p1 == 1) {
                return new kd();
            } else {
                return new oy();
            }
        }
    }

    public static final bi l(com.example.instatool.browser.BrowserActivity p1, String p2, int p3, int p4, String p5)
    {
        String v1_1 = p1.getString(p4);
        v1_1.getClass();
        return new bi(p3, v1_1, p5, p2);
    }

    public static boolean m(uo p6, android.view.View p7, android.view.Window$Callback p8, android.view.KeyEvent p9)
    {
        boolean v0 = 0;
        if (p6 != null) {
            if (android.os.Build$VERSION.SDK_INT < 28) {
                android.view.KeyEvent$DispatcherState v2_0 = 0;
                boolean v3 = 1;
                if (!(p8 instanceof android.app.Activity)) {
                    if (!(p8 instanceof android.app.Dialog)) {
                        if (((p7) && (g60.c(p7, p9))) || (p6.b(p9))) {
                            return 1;
                        }
                    } else {
                        if (!io.p) {
                            try {
                                android.view.View v6_5 = android.app.Dialog.getDeclaredField("mOnKeyListener");
                                io.q = v6_5;
                                v6_5.setAccessible(1);
                            } catch (NoSuchFieldException) {
                            }
                            io.p = 1;
                        }
                        android.view.View v6_8;
                        android.view.View v6_6 = io.q;
                        try {
                            if (v6_6 == null) {
                                v6_8 = 0;
                            } else {
                                v6_8 = ((android.content.DialogInterface$OnKeyListener) v6_6.get(((android.app.Dialog) p8)));
                            }
                        } catch (IllegalAccessException) {
                        }
                        if ((v6_8 == null) || (!v6_8.onKey(((android.app.Dialog) p8), p9.getKeyCode(), p9))) {
                            android.view.View v6_10 = ((android.app.Dialog) p8).getWindow();
                            if (!v6_10.superDispatchKeyEvent(p9)) {
                                android.view.View v6_11 = v6_10.getDecorView();
                                if (!g60.c(v6_11, p9)) {
                                    if (v6_11 != null) {
                                        v2_0 = v6_11.getKeyDispatcherState();
                                    }
                                    v3 = p9.dispatch(((android.app.Dialog) p8), v2_0, ((android.app.Dialog) p8));
                                }
                            }
                        }
                        return v3;
                    }
                } else {
                    ((android.app.Activity) p8).onUserInteraction();
                    android.view.View v6_12 = ((android.app.Activity) p8).getWindow();
                    if (!v6_12.hasFeature(8)) {
                        if (!v6_12.superDispatchKeyEvent(p9)) {
                            android.view.View v6_13 = v6_12.getDecorView();
                            if (!g60.c(v6_13, p9)) {
                                if (v6_13 != null) {
                                    v2_0 = v6_13.getKeyDispatcherState();
                                }
                                v3 = p9.dispatch(((android.app.Activity) p8), v2_0, ((android.app.Activity) p8));
                            }
                        }
                    } else {
                        boolean v7_9 = ((android.app.Activity) p8).getActionBar();
                        if ((p9.getKeyCode() != 82) || (!v7_9)) {
                        } else {
                            if (!io.n) {
                                try {
                                    io.o = v7_9.getClass().getMethod("onMenuKeyEvent", new Class[] {android.view.KeyEvent}));
                                } catch (NoSuchMethodException) {
                                }
                                io.n = 1;
                            }
                            reflect.Method v1_6 = io.o;
                            try {
                                if (v1_6 != null) {
                                    boolean v7_10 = v1_6.invoke(v7_9, new Object[] {p9}));
                                    if (v7_10) {
                                        v0 = ((Boolean) v7_10).booleanValue();
                                    } else {
                                    }
                                }
                            } catch (reflect.InvocationTargetException) {
                            }
                            if (!v0) {
                            }
                        }
                    }
                    return v3;
                }
            } else {
                return p6.b(p9);
            }
        }
        return 0;
    }

    public static final boolean n(char p2, char p3, boolean p4)
    {
        if (p2 != p3) {
            if (p4) {
                char v2_2 = Character.toUpperCase(p2);
                char v3_2 = Character.toUpperCase(p3);
                if ((v2_2 != v3_2) && (Character.toLowerCase(v2_2) != Character.toLowerCase(v3_2))) {
                    return 0;
                } else {
                    return 1;
                }
            } else {
                return 0;
            }
        } else {
            return 1;
        }
    }

    public static final qr o(java.util.regex.Matcher p0, int p1, CharSequence p2)
    {
        if (p0.find(p1)) {
            return new qr(p0, p2);
        } else {
            return 0;
        }
    }

    public static android.content.res.ColorStateList p(android.content.Context p8, int p9)
    {
        cy v0_0 = p8.getResources();
        Throwable v8_1 = p8.getTheme();
        android.content.res.Configuration v1_1 = new dy(v0_0, v8_1);
        android.util.SparseArray v3_1;
        android.util.SparseArray v3_0 = ((android.util.SparseArray) fy.b.get(v1_1));
        android.content.res.ColorStateList v4 = 0;
        if ((v3_0 == null) || (v3_0.size() <= 0)) {
            v3_1 = 0;
        } else {
            String v5_2 = ((cy) v3_0.get(p9));
            if (v5_2 == null) {
            } else {
                if (v5_2.b.equals(v0_0.getConfiguration())) {
                    if (v8_1 != null) {
                        if ((v8_1 == null) || (v5_2.c != v8_1.hashCode())) {
                            v3_0.remove(p9);
                        }
                    } else {
                        if (v5_2.c != 0) {
                        }
                    }
                    v3_1 = v5_2.a;
                    if (v3_1 == null) {
                        Object v2_0 = fy.a;
                        android.util.SparseArray v3_3 = ((android.util.TypedValue) v2_0.get());
                        if (v3_3 == null) {
                            v3_3 = new android.util.TypedValue();
                            v2_0.set(v3_3);
                        }
                        v0_0.getValue(p9, v3_3, 1);
                        Object v2_2 = v3_3.type;
                        if ((v2_2 < 28) || (v2_2 > 31)) {
                            try {
                                v4 = zb.a(v0_0, v0_0.getXml(p9), v8_1);
                            } catch (Object v2_4) {
                                android.util.Log.w("ResourcesCompat", "Failed to inflate ColorStateList, leaving it to the framework", v2_4);
                            }
                        }
                        if (v4 == null) {
                            v4 = v0_0.getColorStateList(p9, v8_1);
                        } else {
                            cy v0_1 = fy.b;
                            android.util.SparseArray v3_10 = ((android.util.SparseArray) v0_1.get(v1_1));
                            if (v3_10 == null) {
                                v3_10 = new android.util.SparseArray();
                                v0_1.put(v1_1, v3_10);
                            }
                            v3_10.append(p9, new cy(v4, v1_1.a.getConfiguration(), v8_1));
                        }
                        return v4;
                    } else {
                        return v3_1;
                    }
                }
            }
        }
    }

    public static android.content.Intent r(b3 p3)
    {
        String v0_0 = p3.getParentActivityIntent();
        if (v0_0 == null) {
            try {
                String v0_6 = io.t(p3, p3.getComponentName());
            } catch (android.content.Intent v3_9) {
                throw new IllegalArgumentException(v3_9);
            }
            if (v0_6 != null) {
                String v2_1 = new android.content.ComponentName(p3, v0_6);
                try {
                    if (io.t(p3, v2_1) != null) {
                        return new android.content.Intent().setComponent(v2_1);
                    } else {
                        return android.content.Intent.makeMainActivity(v2_1);
                    }
                } catch (android.content.pm.PackageManager$NameNotFoundException) {
                    android.content.Intent v3_7 = new StringBuilder("getParentActivityIntent: bad parentActivityName \'");
                    v3_7.append(v0_6);
                    v3_7.append("\' in manifest");
                    android.util.Log.e("NavUtils", v3_7.toString());
                    return 0;
                }
            } else {
                return 0;
            }
        } else {
            return v0_0;
        }
    }

    public static android.content.Intent s(b3 p2, android.content.ComponentName p3)
    {
        String v0 = io.t(p2, p3);
        if (v0 != null) {
            android.content.ComponentName v1_1 = new android.content.ComponentName(p3.getPackageName(), v0);
            if (io.t(p2, v1_1) != null) {
                return new android.content.Intent().setComponent(v1_1);
            } else {
                return android.content.Intent.makeMainActivity(v1_1);
            }
        } else {
            return 0;
        }
    }

    public static String t(android.content.Context p3, android.content.ComponentName p4)
    {
        int v1_3;
        StringBuilder v0_0 = p3.getPackageManager();
        if (android.os.Build$VERSION.SDK_INT < 29) {
            v1_3 = 787072;
        } else {
            v1_3 = 269222528;
        }
        String v4_3 = v0_0.getActivityInfo(p4, v1_3);
        StringBuilder v0_6 = v4_3.parentActivityName;
        if (v0_6 == null) {
            String v4_1 = v4_3.metaData;
            if (v4_1 != null) {
                String v4_2 = v4_1.getString("android.support.PARENT_ACTIVITY");
                if (v4_2 != null) {
                    if (v4_2.charAt(0) != 46) {
                        return v4_2;
                    } else {
                        StringBuilder v0_5 = new StringBuilder();
                        v0_5.append(p3.getPackageName());
                        v0_5.append(v4_2);
                        return v0_5.toString();
                    }
                } else {
                    return 0;
                }
            } else {
                return 0;
            }
        } else {
            return v0_6;
        }
    }

    public static final int u(d6 p4, Object p5, int p6)
    {
        boolean v0_0 = p4.c;
        if (v0_0) {
            try {
                int v1_2 = p40.c(v0_0, p6, p4.a);
            } catch (IndexOutOfBoundsException) {
                throw new java.util.ConcurrentModificationException();
            }
            if ((v1_2 >= 0) && (!io.d(p5, p4.b[v1_2]))) {
                int v2_2 = (v1_2 + 1);
                while ((v2_2 < v0_0) && (p4.a[v2_2] == p6)) {
                    if (!io.d(p5, p4.b[v2_2])) {
                        v2_2++;
                    } else {
                        return v2_2;
                    }
                }
                int v1_0 = (v1_2 - 1);
                while ((v1_0 >= 0) && (p4.a[v1_0] == p6)) {
                    if (!io.d(p5, p4.b[v1_0])) {
                        v1_0--;
                    } else {
                        return v1_0;
                    }
                }
                return (~ v2_2);
            } else {
                return v1_2;
            }
        } else {
            return -1;
        }
    }

    public static boolean v(android.widget.EditText p0)
    {
        if (p0.getInputType() == 0) {
            return 0;
        } else {
            return 1;
        }
    }

    public static boolean x(char p1)
    {
        if ((!Character.isWhitespace(p1)) && (!Character.isSpaceChar(p1))) {
            return 0;
        } else {
            return 1;
        }
    }

    public static java.util.List y(Object p0)
    {
        java.util.List v0_1 = java.util.Collections.singletonList(p0);
        v0_1.getClass();
        return v0_1;
    }

    public static void z(android.view.inputmethod.EditorInfo p0, android.view.inputmethod.InputConnection p1, android.widget.TextView p2)
    {
        if ((p1) && (p0.hintText == null)) {
            android.view.ViewParent v0_2 = p2.getParent();
            while ((v0_2 instanceof android.view.View)) {
                v0_2 = v0_2.getParent();
            }
        }
        return;
    }

    public abstract void N(boolean p0);

    public abstract void O(boolean p0);

    public abstract android.text.method.TransformationMethod Z(android.text.method.TransformationMethod p0);

    public abstract android.text.InputFilter[] q(android.text.InputFilter[] p0);

    public abstract boolean w();
}
