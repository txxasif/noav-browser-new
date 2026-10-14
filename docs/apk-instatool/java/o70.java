public class Lo70 implements org.chromium.support_lib_boundary.WebMessageListenerBoundaryInterface, gt, rs, i5, hu, vs, gs, pc, rc, ui, wg, gh, te {
    public final synthetic byte a;
    public Object b;

    public o70(byte p4)
    {
        this.a = p4;
        switch (p4) {
            case 8:
                return;
            case 25:
                this.b = new java.util.LinkedHashMap(0, 1061158912, 1);
                return;
            default:
                if (android.os.Build$VERSION.SDK_INT < 26) {
                    this.b = new n0(this);
                } else {
                    this.b = new o0(this);
                }
                return;
        }
    }

    public o70(android.content.ClipData p2, int p3)
    {
        this.a = 15;
        this.b = f5.j(p2, p3);
        return;
    }

    public o70(android.content.Context p2)
    {
        this.a = 19;
        this.b = p2.getApplicationContext();
        return;
    }

    public o70(android.content.Context p1, kt p2, a9 p3)
    {
        this.a = 27;
        this.b = p3;
        return;
    }

    public o70(android.net.Uri p3, android.content.ClipDescription p4, android.net.Uri p5)
    {
        this.a = 24;
        if (android.os.Build$VERSION.SDK_INT < 25) {
            this.b = new s5(p3, p4, p5);
        } else {
            this.b = new ln(p3, p4, p5);
        }
        return;
    }

    public o70(android.view.ContentInfo p2)
    {
        this.a = 16;
        p2.getClass();
        this.b = f5.l(p2);
        return;
    }

    public o70(android.widget.EditText p3)
    {
        this.a = 20;
        this.b = new k4(p3, 10);
        return;
    }

    public o70(android.widget.TextView p2)
    {
        this.a = 22;
        this.b = new jh(p2);
        return;
    }

    public o70(com.example.instatool.InstaToolApp p3)
    {
        this.a = 11;
        this.b = p3.getSharedPreferences("browser_settings", 0);
        return;
    }

    public synthetic o70(Object p1, byte p2)
    {
        this.a = p2;
        this.b = p1;
        return;
    }

    public static final void J(z7 p2, o70 p3, android.view.View p4, jt p5)
    {
        p4.setOnClickListener(new zi(p2, p3, p5, 1));
        return;
    }

    public m0 A(int p1)
    {
        return 0;
    }

    public m0 B(int p1)
    {
        return 0;
    }

    public boolean C()
    {
        return ((android.content.SharedPreferences) this.b).getBoolean("auto_instagram", 0);
    }

    public void D(int p2, int p3)
    {
        k4 v1_2 = ((g6) this.b);
        Object v2_1 = v1_2.a.get(p2);
        Object vtmp2 = v1_2.b.get(p3);
        if ((v2_1 == null) || (vtmp2 == null)) {
            k4 v1_3 = new AssertionError;
            v1_3();
            throw v1_3;
        } else {
            return;
        }
    }

    public jz E()
    {
        jz v5_3 = ((android.content.SharedPreferences) this.b);
        Object v1_0 = 0;
        jz v0_2 = v5_3.getString("search_engine", 0);
        if (v0_2 == null) {
            v0_2 = ((jz) rb.g0(jz.d)).a;
        }
        jz v5_2 = v5_3.getString("custom_search_template", 0);
        Object v2_1 = "";
        if (v5_2 == null) {
            v5_2 = "";
        }
        if ((!v0_2.equals("custom")) || (!gy.u(v5_2))) {
            jz v5_5 = jz.d.iterator();
            while (v5_5.hasNext()) {
                Object v2_3 = v5_5.next();
                if (((jz) v2_3).a.equals(v0_2)) {
                    v1_0 = v2_3;
                    break;
                }
            }
            Object v1_1 = ((jz) v1_0);
            if (v1_1 != null) {
                return v1_1;
            } else {
                return ((jz) rb.g0(jz.d));
            }
        } else {
            jz v0_7 = android.net.Uri.parse(u10.y(v5_2, "%s", "")).getHost();
            if (v0_7 != null) {
                v2_1 = v0_7;
            }
            return new jz("custom", m10.J(v2_1, "www."), m10.P(v5_2).toString());
        }
    }

    public String F()
    {
        String v2_3 = ((android.content.SharedPreferences) this.b).getString("sheet_url", 0);
        if (v2_3 == null) {
            v2_3 = "";
        }
        return v2_3;
    }

    public void G()
    {
        java.util.Iterator v1_6 = ((xk) this.b).c;
        if (v1_6.r != null) {
            v1_6.y = 0;
            v1_6.z = 0;
            v1_6.E.getClass();
            java.util.Iterator v1_5 = v1_6.c.f().iterator();
            while (v1_5.hasNext()) {
                if (v1_5.next() != null) {
                    e6.a();
                    break;
                }
            }
        }
        return;
    }

    public void H(int p1, int p2)
    {
        ((jq) this.b).a.c(p1, p2);
        return;
    }

    public boolean I(int p1, int p2, android.os.Bundle p3)
    {
        return 0;
    }

    public void a(ts p3, boolean p4)
    {
        if ((p3 instanceof v10)) {
            ((v10) p3).z.k().c(0);
        }
        gt v2_2 = ((l1) this.b).e;
        if (v2_2 != null) {
            v2_2.a(p3, p4);
        }
        return;
    }

    public Object b()
    {
        return this;
    }

    public sc build()
    {
        return new sc(new o70(f5.k(((android.view.ContentInfo$Builder) this.b))));
    }

    public android.content.ClipData c()
    {
        return f5.e(((android.view.ContentInfo) this.b));
    }

    public java.io.InputStream d(String p2)
    {
        p2.getClass();
        String v2_1 = pg.l(p2);
        if (v2_1 != null) {
            java.io.File v0_1 = new java.io.File(((java.io.File) this.b), v2_1);
            if (v0_1.isFile()) {
                java.io.FileInputStream v1_1 = new java.io.FileInputStream;
                v1_1(v0_1);
                return v1_1;
            }
        }
        return 0;
    }

    public void e(int p1)
    {
        return;
    }

    public boolean f(ts p4, android.view.MenuItem p5)
    {
        int v3_6 = ((androidx.appcompat.widget.ActionMenuView) this.b).z;
        if (v3_6 != 0) {
            int v3_10 = ((n30) v3_6).a;
            v3_10.G.r();
            int v3_11 = v3_10.I;
            if (v3_11 != 0) {
                int v3_5 = ((ap) v3_11).b;
                if (p5.getItemId() == 1) {
                    rr v4_2 = new rr(v3_5);
                    int v0_1 = ((f2) v4_2.b);
                    v0_1.f = v0_1.a.getText(2131689623);
                    v4_2.k(2131689612, new l8(v3_5, 2));
                    v4_2.j(2131689596, 0);
                    v4_2.i();
                }
                return 1;
            }
        }
        return 0;
    }

    public void g(ts p1, android.view.MenuItem p2)
    {
        ((ea) this.b).f.removeCallbacksAndMessages(p1);
        return;
    }

    public String[] getSupportedFeatures()
    {
        return new String[] {"WEB_MESSAGE_LISTENER", "WEB_MESSAGE_ARRAY_BUFFER"});
    }

    public boolean i(float p2)
    {
        if (p2 != 0) {
            this.w();
            ((androidx.core.widget.NestedScrollView) this.b).j(((int) p2));
            return 1;
        } else {
            return 0;
        }
    }

    public void j(ts p8, ws p9)
    {
        ca v0_1 = ((ea) this.b);
        android.os.Handler v1 = v0_1.f;
        long v2_1 = 0;
        v1.removeCallbacksAndMessages(0);
        ca v0_5 = v0_1.h;
        int v3_1 = v0_5.size();
        long v4_0 = 0;
        while (v4_0 < v3_1) {
            if (p8 != ((da) v0_5.get(v4_0)).b) {
                v4_0++;
            }
            if (v4_0 != -1) {
                long v4_1 = (v4_0 + 1);
                if (v4_1 < v0_5.size()) {
                    v2_1 = ((da) v0_5.get(v4_1));
                }
                v1.postAtTime(new ca(this, v2_1, p9, p8), p8, (android.os.SystemClock.uptimeMillis() + 200));
                return;
            } else {
                return;
            }
        }
        v4_0 = -1;
    }

    public c90 k(android.view.View p5, c90 p6)
    {
        switch (this.a) {
            case 9:
                y7 v4_5 = ((z7) this.b);
                java.util.ArrayList v5_5 = v4_5.m;
                if (v5_5 != null) {
                    v4_5.f.c0.remove(v5_5);
                }
                java.util.ArrayList v5_1 = new y7(v4_5.i, p6);
                v4_5.m = v5_1;
                v5_1.e(v4_5.getWindow());
                y7 v4_1 = v4_5.m;
                java.util.ArrayList v5_3 = v4_5.f.c0;
                if (!v5_3.contains(v4_1)) {
                    v5_3.add(v4_1);
                }
                return p6;
            default:
                java.util.ArrayList v5_4 = p6.a;
                y7 v4_4 = ((androidx.coordinatorlayout.widget.CoordinatorLayout) this.b);
                if (!java.util.Objects.equals(v4_4.n, p6)) {
                    int v0_6;
                    v4_4.n = p6;
                    int v1 = 0;
                    boolean v2_0 = 1;
                    if (p6.d() <= 0) {
                        v0_6 = 0;
                    } else {
                        v0_6 = 1;
                    }
                    v4_4.o = v0_6;
                    if ((v0_6 != 0) || (v4_4.getBackground() != null)) {
                        v2_0 = 0;
                    }
                    v4_4.setWillNotDraw(v2_0);
                    if (!v5_4.r()) {
                        int v0_9 = v4_4.getChildCount();
                        while (v1 < v0_9) {
                            boolean v2_1 = v4_4.getChildAt(v1);
                            if ((v2_1.getFitsSystemWindows()) && ((((bd) v2_1.getLayoutParams()).a != null) && (v5_4.r()))) {
                                break;
                            }
                            v1++;
                        }
                    }
                    v4_4.requestLayout();
                }
                return p6;
        }
    }

    public int l()
    {
        return f5.c(((android.view.ContentInfo) this.b));
    }

    public android.view.ContentInfo m()
    {
        return ((android.view.ContentInfo) this.b);
    }

    public void n(ts p1)
    {
        n30 v0_3 = ((androidx.appcompat.widget.ActionMenuView) this.b).u;
        if (v0_3 != null) {
            v0_3.n(p1);
        }
        return;
    }

    public boolean o(CharSequence p1, int p2, int p3, y40 p4)
    {
        if (!android.text.TextUtils.equals(p1.subSequence(p2, p3), ((String) this.b))) {
            return 1;
        } else {
            p4.c = ((p4.c & 3) | 4);
            return 0;
        }
    }

    public void onPostMessage(android.webkit.WebView p18, reflect.InvocationHandler p19, android.net.Uri p20, boolean p21, reflect.InvocationHandler p22)
    {
        Class v0_33 = ((org.chromium.support_lib_boundary.WebMessageBoundaryInterface) c8.e(org.chromium.support_lib_boundary.WebMessageBoundaryInterface, p19));
        String v1_16 = v0_33.getPorts();
        String v2_10 = new hv[v1_16.length];
        StringBuilder v4_5 = 0;
        while (v4_5 < v1_16.length) {
            int v6_2 = v1_16[v4_5];
            boolean v5_13 = new hv();
            v5_13.a = ((org.chromium.support_lib_boundary.WebMessagePortBoundaryInterface) c8.e(org.chromium.support_lib_boundary.WebMessagePortBoundaryInterface, v6_2));
            v2_10[v4_5] = v5_13;
            v4_5++;
        }
        String v1_4;
        String v2_0 = 0;
        if (!s70.a.b()) {
            v1_4 = new r7(v0_33.getData());
        } else {
            Class v0_23 = ((org.chromium.support_lib_boundary.WebMessagePayloadBoundaryInterface) c8.e(org.chromium.support_lib_boundary.WebMessagePayloadBoundaryInterface, v0_33.getMessagePayload()));
            String v1_6 = v0_23.getType();
            if (v1_6 == null) {
                v1_4 = new r7(v0_23.getAsString());
            } else {
                if (v1_6 == 1) {
                    v1_4 = new r7(v0_23.getAsArrayBuffer());
                } else {
                    v1_4 = 0;
                }
            }
        }
        if (v1_4 != null) {
            Class v0_36 = ((org.chromium.support_lib_boundary.JsReplyProxyBoundaryInterface) c8.e(org.chromium.support_lib_boundary.JsReplyProxyBoundaryInterface, p22));
            ro v8_1 = ((ro) v0_36.getOrCreatePeer(new qo(v0_36)));
            ri v14_1 = ((ri) ((f) this.b).b);
            p18.getClass();
            p20.getClass();
            v8_1.getClass();
            try {
                String v1_17 = v1_4.b();
            } catch (Class v0_44) {
                Class v0_43 = new hy(v0_44);
                if (!(v0_43 instanceof hy)) {
                    v2_0 = v0_43;
                }
                String v2_9 = ((org.json.JSONObject) v2_0);
                if (v2_9 != null) {
                    Class v0_47 = ((gi) v14_1.n.get(p18));
                    if (v0_47 != null) {
                        String v1_7 = ((ei) v14_1.l.get(v2_9.optString("ext")));
                        if (v1_7 != null) {
                            boolean v3_1;
                            ni v10 = v0_47.b;
                            if (!(v10 instanceof mi)) {
                                if (!(v10 instanceof ki)) {
                                    if (!(v10 instanceof li)) {
                                        throw new uk();
                                    } else {
                                        v3_1 = ((li) v10).a.equals(v1_7.a);
                                    }
                                } else {
                                    v3_1 = ((ki) v10).a.equals(v1_7.a);
                                }
                            } else {
                                if (v14_1.k(v1_7, ((mi) v10).b)) {
                                    if (!io.d(p20.getHost(), "appassets.androidplatform.net")) {
                                        Class v0_13 = v1_7.j;
                                        if ((v0_13 == null) || (!v0_13.isEmpty())) {
                                            boolean v5_3 = v0_13.size();
                                            int v6_0 = 0;
                                            while (v6_0 < v5_3) {
                                                String v7_0 = v0_13.get(v6_0);
                                                v6_0++;
                                                String v7_2 = ((tc) v7_0).b;
                                                if (!v7_2.isEmpty()) {
                                                    String v7_3 = v7_2.iterator();
                                                    while (v7_3.hasNext()) {
                                                        boolean v3_10;
                                                        String v11_3 = ((String) v7_3.next());
                                                        Class vtmp47 = v11_3.getClass();
                                                        if (!v11_3.equals("<all_urls>")) {
                                                            String v11_4 = or.a.b(v11_3);
                                                            if (v11_4 != null) {
                                                                String v12_6 = ((String) ((pr) v11_4.a()).get(1));
                                                                String v11_8 = ((String) ((pr) v11_4.a()).get(2));
                                                                boolean v13_1 = p20.getScheme();
                                                                if (v13_1) {
                                                                    boolean v3_3;
                                                                    if (!io.d(v12_6, "*")) {
                                                                        v3_3 = io.d(v12_6, v13_1);
                                                                    } else {
                                                                        if ((!v13_1.equals("http")) && (!v13_1.equals("https"))) {
                                                                            v3_3 = 0;
                                                                        } else {
                                                                            v3_3 = 1;
                                                                        }
                                                                    }
                                                                    if (v3_3) {
                                                                        boolean v3_9 = m10.N(v11_8, 58);
                                                                        String v11_9 = p20.getHost();
                                                                        if (v11_9 != null) {
                                                                            if (!v3_9.equals("*")) {
                                                                                if (!v3_9.startsWith("*.")) {
                                                                                    v3_10 = v11_9.equals(v3_9);
                                                                                    if (v3_10) {
                                                                                    }
                                                                                    v3_1 = 1;
                                                                                    if (v3_1) {
                                                                                        int v6_1 = v2_9.optString("iid");
                                                                                        boolean v3_15 = v2_9.optString("type");
                                                                                        Class v0_17 = v1_7.a;
                                                                                        v6_1.getClass();
                                                                                        boolean v5_5 = v2_9.optInt("id");
                                                                                        StringBuilder v4_2 = new ji();
                                                                                        v4_2.b = v8_1;
                                                                                        v4_2.c = v0_17;
                                                                                        v4_2.d = v6_1;
                                                                                        v4_2.a = v5_5;
                                                                                        Class v0_20 = v2_9.optJSONObject("payload");
                                                                                        if (v0_20 == null) {
                                                                                            v0_20 = new org.json.JSONObject();
                                                                                        }
                                                                                        String v11_10 = v2_9.optString("url");
                                                                                        boolean v5_7 = v14_1.o;
                                                                                        if (!io.d(v3_15, "bye")) {
                                                                                            String v2_4 = ((hi) v5_7.get(v6_1));
                                                                                            if (v2_4 == null) {
                                                                                                String v7_4 = v1_7.a;
                                                                                                v11_10.getClass();
                                                                                                String v12_11 = p20.toString();
                                                                                                v12_11.getClass();
                                                                                                boolean v5_9 = new hi(v6_1, v7_4, v8_1, p18, v10, v11_10, v12_11, p21);
                                                                                                v14_1.o.put(v6_1, v5_9);
                                                                                                v2_4 = v5_9;
                                                                                            } else {
                                                                                                v11_10.getClass();
                                                                                                v2_4.e = v11_10;
                                                                                            }
                                                                                            if (!io.d(v3_15, "hello")) {
                                                                                                try {
                                                                                                    v3_15.getClass();
                                                                                                    ei v18_1 = v1_7;
                                                                                                    String v20_1 = v3_15;
                                                                                                    ji v22_1 = v4_2;
                                                                                                    try {
                                                                                                        v14_1.j(v18_1, v2_4, v20_1, v0_20, v22_1);
                                                                                                    } catch (Class v0_24) {
                                                                                                        v1_7 = v18_1;
                                                                                                        String v2_6 = v20_1;
                                                                                                        boolean v3_16 = v22_1;
                                                                                                        StringBuilder v4_4 = new StringBuilder(v1_7.a);
                                                                                                        v4_4.append(": ");
                                                                                                        v4_4.append(v2_6);
                                                                                                        v4_4.append(" failed");
                                                                                                        android.util.Log.w("ExtensionManager", v4_4.toString(), v0_24);
                                                                                                        String v1_12 = v0_24.getMessage();
                                                                                                        if (v1_12 == null) {
                                                                                                            v1_12 = v0_24.getClass().getSimpleName();
                                                                                                        }
                                                                                                        v3_16.a(v1_12);
                                                                                                    }
                                                                                                } catch (Class v0_24) {
                                                                                                    v2_6 = v3_15;
                                                                                                    v3_16 = v4_2;
                                                                                                }
                                                                                            } else {
                                                                                                if ((v10 instanceof ki)) {
                                                                                                    Class v0_30 = ((u6) v14_1.m.get(v1_7.a));
                                                                                                    if (v0_30 != null) {
                                                                                                        v0_30.f = v8_1;
                                                                                                        v0_30.a();
                                                                                                    }
                                                                                                }
                                                                                            }
                                                                                        } else {
                                                                                            v5_7.remove(v6_1);
                                                                                        }
                                                                                    }
                                                                                    return;
                                                                                } else {
                                                                                    boolean v3_11 = m10.J(v3_9, "*.");
                                                                                    if ((v11_9.equals(v3_11)) || (v11_9.endsWith(".".concat(v3_11)))) {
                                                                                        v3_10 = 1;
                                                                                    }
                                                                                }
                                                                            }
                                                                        } else {
                                                                            v3_10 = io.d(v12_6, "file");
                                                                        }
                                                                    }
                                                                }
                                                            }
                                                            v3_10 = 0;
                                                        }
                                                    }
                                                }
                                            }
                                            v3_1 = 0;
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
            if (v1_17 != null) {
                v0_43 = new org.json.JSONObject(v1_17);
            } else {
            }
        }
        return;
    }

    public void p(int p1)
    {
        return;
    }

    public void q(android.net.Uri p1)
    {
        f5.p(((android.view.ContentInfo$Builder) this.b), p1);
        return;
    }

    public int r()
    {
        return f5.r(((android.view.ContentInfo) this.b));
    }

    public void s(p40 p9)
    {
        java.util.concurrent.ThreadPoolExecutor v0_1 = new java.util.concurrent.ThreadPoolExecutor(0, 1, 15, java.util.concurrent.TimeUnit.SECONDS, new java.util.concurrent.LinkedBlockingDeque(), new kc("EmojiCompatInitializer"));
        v0_1.allowCoreThreadTimeOut(1);
        v0_1.execute(new x8(this, p9, v0_1, 2));
        return;
    }

    public void setExtras(android.os.Bundle p1)
    {
        f5.q(((android.view.ContentInfo$Builder) this.b), p1);
        return;
    }

    public float t()
    {
        return (- ((androidx.core.widget.NestedScrollView) this.b).getVerticalScrollFactorCompat());
    }

    public String toString()
    {
        switch (this.a) {
            case 16:
                StringBuilder v0_2 = new StringBuilder("ContentInfoCompat{");
                v0_2.append(((android.view.ContentInfo) this.b));
                v0_2.append("}");
                return v0_2.toString();
            default:
                return super.toString();
        }
    }

    public void u(int p1, float p2)
    {
        return;
    }

    public boolean v(ts p2)
    {
        boolean v1_2 = ((l1) this.b);
        if (p2 != v1_2.c) {
            boolean v1_5 = v1_2.e;
            if (v1_5) {
                return v1_5.v(p2);
            }
        }
        return 0;
    }

    public void w()
    {
        ((androidx.core.widget.NestedScrollView) this.b).d.abortAnimation();
        return;
    }

    public void x(int p1)
    {
        f5.o(((android.view.ContentInfo$Builder) this.b), p1);
        return;
    }

    public boolean y(int p2, int p3)
    {
        int v1_2 = ((g6) this.b);
        Object v2_1 = v1_2.a.get(p2);
        Object v3_1 = v1_2.b.get(p3);
        if ((v2_1 == null) || (v3_1 == null)) {
            if ((v2_1 != null) || (v3_1 != null)) {
                int v1_3 = new AssertionError;
                v1_3();
                throw v1_3;
            } else {
                return 1;
            }
        } else {
            return ((p40) v1_2.d.b.c).a(v2_1, v3_1);
        }
    }

    public boolean z(int p2, int p3)
    {
        int v1_2 = ((g6) this.b);
        Object v2_1 = v1_2.a.get(p2);
        Object v3_1 = v1_2.b.get(p3);
        if ((v2_1 == null) || (v3_1 == null)) {
            if ((v2_1 != null) || (v3_1 != null)) {
                return 0;
            } else {
                return 1;
            }
        } else {
            return ((p40) v1_2.d.b.c).b(v2_1, v3_1);
        }
    }
}
