public final class Lri {
    public m8 a;
    public final android.content.Context b;
    public final android.os.Handler c;
    public final java.util.concurrent.ExecutorService d;
    public final android.content.SharedPreferences e;
    public final java.io.File f;
    public final java.io.File g;
    public final wi h;
    public final df i;
    public final boolean j;
    public final boolean k;
    public volatile java.util.Map l;
    public final java.util.HashMap m;
    public final java.util.HashMap n;
    public final pi o;
    public final java.util.HashMap p;
    public final java.util.HashSet q;
    public final java.util.concurrent.ConcurrentHashMap r;
    public final java.util.HashMap s;
    public final java.util.HashMap t;
    public final pi u;
    public int v;
    public boolean w;
    public final h20 x;
    public com.example.instatool.browser.BrowserActivity y;

    public ri(com.example.instatool.InstaToolApp p5)
    {
        cc v5_1 = p5.getApplicationContext();
        this.b = v5_1;
        this.c = new android.os.Handler(android.os.Looper.getMainLooper());
        this.d = java.util.concurrent.Executors.newSingleThreadExecutor();
        this.e = v5_1.getSharedPreferences("extensions", 0);
        this.f = new java.io.File(v5_1.getFilesDir(), "extensions");
        this.g = new java.io.File(v5_1.getFilesDir(), "extension_dnr");
        this.h = new wi(new java.io.File(v5_1.getFilesDir(), "extension_storage"));
        cc v5_4 = new df();
        v5_4.a = qh.a;
        this.i = v5_4;
        this.j = s70.b("DOCUMENT_START_SCRIPT");
        this.k = s70.b("WEB_MESSAGE_LISTENER");
        this.l = rh.a;
        this.m = new java.util.HashMap();
        this.n = new java.util.HashMap();
        this.o = new pi(64, 1061158912, 1, 0);
        this.p = new java.util.HashMap();
        this.q = new java.util.HashSet();
        this.r = new java.util.concurrent.ConcurrentHashMap();
        this.s = new java.util.HashMap();
        this.t = new java.util.HashMap();
        this.u = new pi(16, 1061158912, 1, 1);
        this.v = 1;
        this.x = new h20(new cc(this, 1));
        return;
    }

    public static org.json.JSONObject b(ei p3, String p4, boolean p5)
    {
        org.json.JSONObject v4_4 = new org.json.JSONObject().put("id", p3.a).put("bridge", "__instaToolExt").put("context", p4).put("incognito", p5).put("baseUrl", p3.i).put("manifest", p3.c);
        org.json.JSONObject v3_1 = p3.e;
        if (v3_1 == null) {
            v3_1 = new org.json.JSONObject();
        }
        org.json.JSONObject v3_3 = v4_4.put("messages", v3_1);
        v3_3.getClass();
        return v3_3;
    }

    public static java.util.LinkedHashMap e()
    {
        java.util.LinkedHashMap v1_2 = new java.util.LinkedHashMap(nr.i0(3));
        int v3_1 = 0;
        while (v3_1 < 3) {
            Object v4_1 = new vu[] {new vu("Access-Control-Allow-Origin", "*"), new vu("Cross-Origin-Resource-Policy", "cross-origin"), new vu("Cache-Control", "no-cache")})[v3_1];
            v1_2.put(v4_1.a, v4_1.b);
            v3_1++;
        }
        return v1_2;
    }

    public static android.webkit.WebResourceResponse q()
    {
        String v1_1 = new byte[0];
        return new android.webkit.WebResourceResponse("text/plain", "utf-8", 404, "Not Found", ri.e(), new java.io.ByteArrayInputStream(v1_1));
    }

    public static String t(ei p1, String p2)
    {
        if (p2.length() != 0) {
            if (android.net.Uri.parse(p2).getScheme() == null) {
                String v1_3 = p1.i;
                String v2_1 = m10.J(p2, "/");
                StringBuilder v0_2 = new StringBuilder();
                v0_2.append(v1_3);
                v0_2.append(v2_1);
                return v0_2.toString();
            } else {
                return p2;
            }
        } else {
            return 0;
        }
    }

    public static android.webkit.WebResourceResponse u(String p7, byte[] p8)
    {
        return new android.webkit.WebResourceResponse(p7, "utf-8", 200, "OK", ri.e(), new java.io.ByteArrayInputStream(p8));
    }

    public final String A(ei p8, tc p9, boolean p10)
    {
        String v0_0 = p8.a;
        String v1_0 = p9.a;
        java.util.concurrent.ConcurrentHashMap v2_2 = new StringBuilder(v0_0);
        v2_2.append("#");
        v2_2.append(v1_0);
        v2_2.append("#");
        v2_2.append(p10);
        String v1_1 = v2_2.toString();
        java.util.concurrent.ConcurrentHashMap v2_0 = this.r;
        Object v3_0 = v2_0.get(v1_1);
        if (v3_0 == null) {
            String v10_4 = new org.json.JSONObject().put("api", ri.b(p8, "content", p10));
            Object v3_4 = p9.b;
            String v4_3 = new java.util.ArrayList();
            Object v3_5 = v3_4.iterator();
            while (v3_5.hasNext()) {
                int v5_5 = or.c(((String) v3_5.next()));
                if (v5_5 != 0) {
                    v4_3.add(v5_5);
                }
            }
            String v10_5 = v10_4.put("matches", new org.json.JSONArray(v4_3));
            Object v3_8 = p9.c;
            String v4_6 = new java.util.ArrayList();
            Object v3_10 = v3_8.iterator();
            while (v3_10.hasNext()) {
                int v5_2 = or.c(((String) v3_10.next()));
                if (v5_2 != 0) {
                    v4_6.add(v5_2);
                }
            }
            String v10_8 = v10_5.put("exclude", new org.json.JSONArray(v4_6)).put("allFrames", p9.g).put("runAt", p9.f);
            Object v3_16 = java.util.regex.Pattern.compile("\\W");
            v3_16.getClass();
            String v0_2 = v3_16.matcher(v0_0).replaceAll("_");
            v0_2.getClass();
            String v4_10 = p9.a;
            int v5_9 = new StringBuilder("__instatool_cs_");
            v5_9.append(v0_2);
            v5_9.append("_");
            v5_9.append(v4_10);
            String v10_10 = v10_8.put("guard", v5_9.toString()).put("css", rb.l0(p9.e, "\n", new di(p8, 1), 30));
            Object v8_3 = rb.l0(p9.d, "\n;\n", new di(p8, this), 30);
            StringBuilder v9_1 = new StringBuilder("(function(){\nvar __it=");
            v9_1.append(v10_10.toString());
            v9_1.append(";\n\nif(!__it.allFrames&&window.top!==window)return;\nvar __u=location.href;\nfunction __m(l){for(var i=0;i<l.length;i++){try{if(new RegExp(l[i]).test(__u))return true;}catch(e){}}return false;}\nif(!__m(__it.matches)||__m(__it.exclude))return;\nif(window[__it.guard])return;\ntry{Object.defineProperty(window,__it.guard,{value:true});}catch(e){return;}\nvar chrome=(");
            v9_1.append(((String) this.x.a()));
            v9_1.append(")(__it.api);\nvar browser=chrome;\n\nif(__it.css){var __css=function(){var s=document.createElement(\'style\');s.textContent=__it.css;(document.head||document.documentElement).appendChild(s);};\nif(document.documentElement)__css();else document.addEventListener(\'readystatechange\',__css,{once:true});}\nfunction __main(){\nif(document.documentElement&&document.documentElement.hasAttribute(\'data-instatool-redirect\'))return;\n");
            v9_1.append(v8_3);
            v9_1.append("\n}\n\nfunction __run(){try{__main();}catch(e){console.error(\'[InstaTool extension]\',e);}}\nvar __ra=__it.runAt;\nif(__ra===\'document_start\'){__run();}\nelse if(document.readyState===\'loading\'){document.addEventListener(\'DOMContentLoaded\',__ra===\'document_idle\'?function(){setTimeout(__run,0);}:__run,{once:true});}\nelse if(__ra===\'document_idle\'){setTimeout(__run,0);}\nelse{__run();}\n})();");
            String v7_6 = v9_1.toString();
            Object v8_1 = v2_0.putIfAbsent(v1_1, v7_6);
            if (v8_1 != null) {
                v3_0 = v8_1;
            } else {
                v3_0 = v7_6;
            }
        }
        return ((String) v3_0);
    }

    public final java.util.List a()
    {
        qh v10_1 = this.y;
        java.util.ArrayList v0 = 0;
        if (v10_1 != null) {
            qh v10_3 = v10_1.C;
            java.util.ArrayList v1_1 = ((java.util.ArrayList) v10_3.b);
            java.util.ArrayList v2_1 = new java.util.ArrayList(tb.e0(v1_1));
            int v3_0 = v1_1.size();
            int v5_0 = 0;
            int v6 = 0;
            while (v6 < v3_0) {
                p9 v7_0 = v1_1.get(v6);
                v6++;
                int v8 = (v5_0 + 1);
                if (v5_0 < 0) {
                    sb.d0();
                    throw 0;
                } else {
                    int v9_2;
                    p9 v7_1 = ((p9) v7_0);
                    if (v7_1 != ((p9) v10_3.c)) {
                        v9_2 = 0;
                    } else {
                        v9_2 = 1;
                    }
                    v2_1.add(v7_1.h(v5_0, v9_2));
                    v5_0 = v8;
                }
            }
            v0 = v2_1;
        }
        if (v0 != null) {
            return v0;
        } else {
            return qh.a;
        }
    }

    public final void c(gi p4)
    {
        b8 v0_0 = p4.a;
        this.f(v0_0);
        this.n.put(v0_0, p4);
        if (this.k) {
            String[] v4_6 = jy.o("*");
            String v1_0 = new f(this, 3);
            if (!s70.c.b()) {
                throw s70.a();
            } else {
                o70 v2_1 = new String[0];
                p70.c(v0_0).a.addWebMessageListener("__instaToolExt", ((String[]) v4_6.toArray(v2_1)), new b8(new o70(v1_0, 0)));
                return;
            }
        } else {
            android.util.Log.w("ExtensionManager", "WebView lacks WEB_MESSAGE_LISTENER; extension APIs are unavailable");
            return;
        }
    }

    public final void d(String p6, org.json.JSONObject p7)
    {
        String v7_1 = p7.toString();
        v7_1.getClass();
        java.util.Iterator v0_6 = this.o.values();
        v0_6.getClass();
        ro v1_6 = new java.util.ArrayList();
        java.util.Iterator v0_0 = v0_6.iterator();
        while (v0_0.hasNext()) {
            int v2_3 = v0_0.next();
            int v3_2 = ((hi) v2_3);
            if ((v3_2.a.equals(p6)) && (!(v3_2.d instanceof ki))) {
                v1_6.add(v2_3);
            }
        }
        java.util.Iterator v0_2 = new java.util.ArrayList(tb.e0(v1_6));
        int v2_2 = v1_6.size();
        int v3_0 = 0;
        while (v3_0 < v2_2) {
            ro v4_0 = v1_6.get(v3_0);
            v3_0++;
            v0_2.add(((hi) v4_0).b);
        }
        java.util.Iterator v0_4 = rb.r0(new java.util.LinkedHashSet(v0_2)).iterator();
        while (v0_4.hasNext()) {
            ((ro) v0_4.next()).a(v7_1);
        }
        u6 v5_3 = ((u6) this.m.get(p6));
        if (v5_3 != null) {
            v5_3.c(v7_1);
        }
        return;
    }

    public final void f(android.webkit.WebView p6)
    {
        p6.getClass();
        int v0_8 = ((gi) this.n.remove(p6));
        if (v0_8 != 0) {
            int v0_11 = v0_8.c;
            int v1_5 = v0_11.size();
            int v3 = 0;
            while (v3 < v1_5) {
                org.chromium.support_lib_boundary.ScriptHandlerBoundaryInterface v4_0 = v0_11.get(v3);
                v3++;
                ((dz) v4_0).a.remove();
            }
            v0_11.clear();
            try {
                if (this.k) {
                    if (!s70.c.b()) {
                        throw s70.a();
                    } else {
                        p70.c(p6).a.removeWebMessageListener("__instaToolExt");
                    }
                }
            } catch (Throwable) {
            }
            java.util.Iterator v5_2 = this.o.values();
            v5_2.getClass();
            java.util.Iterator v5_3 = v5_2.iterator();
            while (v5_3.hasNext()) {
                int v0_10;
                int v0_7 = ((hi) v5_3.next());
                v0_7.getClass();
                if (v0_7.c != p6) {
                    v0_10 = 0;
                } else {
                    v0_10 = 1;
                }
                if (v0_10 == 1) {
                    v5_3.remove();
                }
            }
        }
        return;
    }

    public final void g(ei p9, hi p10, Object p11, ji p12, java.util.LinkedHashMap p13, u6 p14, int p15)
    {
        java.util.Iterator v9_1 = p9.a;
        oi v0_3 = p13.values();
        v0_3.getClass();
        oi v0_7 = v0_3.iterator();
        int v1_1 = 0;
        while (v0_7.hasNext()) {
            v1_1 += ((Number) v0_7.next()).intValue();
        }
        int v1_0 = (v1_1 + p15);
        if (v1_0 != 0) {
            int v15_1 = this.v;
            this.v = (v15_1 + 1);
            oi v0_2 = new fi(this, v15_1);
            this.p.put(Integer.valueOf(v15_1), new ii(p12, v1_0, v0_2));
            this.c.postDelayed(v0_2, 120000);
            mi v12_7 = new org.json.JSONObject().put("ext", v9_1).put("event", "runtime.message").put("msgId", v15_1);
            if (p11 == null) {
                p11 = org.json.JSONObject.NULL;
            }
            org.json.JSONObject v11_1 = v12_7.put("message", p11);
            java.util.Iterator v9_6 = new org.json.JSONObject().put("id", v9_1).put("url", p10.e).put("origin", p10.f);
            mi v12_12 = p10.d;
            if ((v12_12 instanceof mi)) {
                v9_6.put("frameId", (p10.g ^ 1));
                String v8_6 = this.a().iterator();
                while (v8_6.hasNext()) {
                    org.json.JSONObject v10_7 = v8_6.next();
                    if (((oi) v10_7).a == ((mi) v12_12).a) {
                    }
                    org.json.JSONObject v10_8 = ((oi) v10_7);
                    if ((v10_8 == null) || (v9_6.put("tab", v10_8.a()) == null)) {
                        mi v12_13 = ((mi) v12_12);
                        v9_6.put("tab", new oi(v12_13.a, -1, "", "", 0, v12_13.b, 0).a());
                    }
                }
                v10_7 = 0;
            }
            v9_6.getClass();
            String v8_3 = v11_1.put("sender", v9_6).toString();
            v8_3.getClass();
            java.util.Iterator v9_3 = p13.keySet().iterator();
            while (v9_3.hasNext()) {
                ((ro) v9_3.next()).a(v8_3);
            }
            if (p14 != null) {
                p14.c(v8_3);
            }
            return;
        } else {
            p12.a("Could not establish connection. Receiving end does not exist.");
            return;
        }
    }

    public final java.util.Set h(ei p6)
    {
        org.json.JSONArray v1_1 = 0;
        java.util.Set v5_11 = this.e.getString("rulesets:".concat(p6.a), 0);
        String v0_2 = 0;
        if (v5_11 != null) {
            try {
                boolean v2_1 = new org.json.JSONArray(v5_11);
            } catch (java.util.Set v5_1) {
                v2_1 = new hy(v5_1);
            }
            if (!(v2_1 instanceof hy)) {
                v1_1 = v2_1;
            }
            org.json.JSONArray v1_2 = ((org.json.JSONArray) v1_1);
            if (v1_2 != null) {
                java.util.Set v5_8 = c8.Z(0, v1_2.length());
                java.util.ArrayList v6_4 = new java.util.ArrayList(tb.e0(v5_8));
                java.util.Set v5_9 = v5_8.iterator();
                while(true) {
                    String v0_5 = ((fo) v5_9);
                    if (!v0_5.c) {
                        break;
                    }
                    v6_4.add(v1_2.optString(v0_5.nextInt()));
                }
                return rb.s0(v6_4);
            }
        }
        java.util.Set v5_3 = p6.o;
        java.util.ArrayList v6_2 = new java.util.ArrayList();
        org.json.JSONArray v1_3 = v5_3.size();
        boolean v2_3 = 0;
        while (v2_3 < v1_3) {
            Object v3 = v5_3.get(v2_3);
            v2_3++;
            if (((qy) v3).c) {
                v6_2.add(v3);
            }
        }
        java.util.Set v5_4 = new java.util.ArrayList;
        v5_4(tb.e0(v6_2));
        org.json.JSONArray v1_5 = v6_2.size();
        while (v0_2 < v1_5) {
            boolean v2_4 = v6_2.get(v0_2);
            v0_2++;
            v5_4.add(((qy) v2_4).a);
        }
        return rb.s0(v5_4);
    }

    public final void i(int p2)
    {
        ji v2_4 = ((ii) this.p.remove(Integer.valueOf(p2)));
        if (v2_4 != null) {
            this.c.removeCallbacks(v2_4.c);
            ji v2_1 = v2_4.a;
            if (!v2_4.d) {
                v2_1.a("Could not establish connection. Receiving end does not exist.");
                return;
            } else {
                v2_1.b(0);
                return;
            }
        } else {
            return;
        }
    }

    public final void j(ei p24, hi p25, String p26, org.json.JSONObject p27, ji p28)
    {
        int v9_8 = 0;
        oi v11_0 = 0;
        switch (p26.hashCode()) {
            case -1430541481:
                if (p26.equals("storage.remove")) {
                    String v2_43 = p27.optString("area");
                    v2_43.getClass();
                    p9 v3_23 = this.h;
                    java.util.Iterator v6_31 = p24.a;
                    x8 v4_20 = p27.opt("keys");
                    x8 v4_21;
                    wi.d(v2_43);
                    boolean v7_29 = v3_23.a(v6_31, v2_43);
                    if (!(v4_20 instanceof String)) {
                        if (!(v4_20 instanceof org.json.JSONArray)) {
                            v4_21 = qh.a;
                        } else {
                            String v8_36 = c8.Z(0, ((org.json.JSONArray) v4_20).length());
                            int v9_15 = new java.util.ArrayList(tb.e0(v8_36));
                            String v8_37 = v8_36.iterator();
                            while (((fo) v8_37).c) {
                                v9_15.add(((org.json.JSONArray) v4_20).optString(((fo) v8_37).nextInt()));
                            }
                            v4_21 = v9_15;
                        }
                    } else {
                        v4_21 = io.y(v4_20);
                    }
                    String v8_39 = new org.json.JSONObject();
                    x8 v4_22 = v4_21.iterator();
                    while (v4_22.hasNext()) {
                        int v9_19 = ((String) v4_22.next());
                        int v10_27 = v7_29.remove(v9_19);
                        if (v10_27 != 0) {
                            v8_39.put(v9_19, new org.json.JSONObject().put("oldValue", v10_27));
                        } else {
                        }
                    }
                    x8 v4_23 = v3_23.b(v6_31, v2_43, v7_29, v8_39);
                    p28.b(0);
                    if (v4_23 == null) {
                        return;
                    } else {
                        p9 v3_24 = p24.a;
                        int v1_25 = new org.json.JSONObject().put("ext", p24.a).put("event", "storage.changed").put("area", v2_43).put("changes", v4_23);
                        v1_25.getClass();
                        this.d(v3_24, v1_25);
                        return;
                    }
                } else {
                }
            case -1227913089:
                if (p26.equals("runtime.respond")) {
                    String v2_37 = p27.optInt("msgId");
                    p9 v3_22 = this.p;
                    java.util.LinkedHashMap v5_7 = ((ii) v3_22.get(Integer.valueOf(v2_37)));
                    if (v5_7 != null) {
                        v5_7.b = (v5_7.b + -1);
                        if (p27.optBoolean("handled")) {
                            v5_7.d = 1;
                        }
                        if (!p27.has("response")) {
                            if (v5_7.b > 0) {
                                return;
                            } else {
                                this.i(v2_37);
                                return;
                            }
                        } else {
                            v3_22.remove(Integer.valueOf(v2_37));
                            this.c.removeCallbacks(v5_7.c);
                            v5_7.a.b(p27.get("response"));
                            return;
                        }
                    } else {
                        return;
                    }
                } else {
                }
            case -893097075:
                if (p26.equals("runtime.openOptionsPage")) {
                    String v2_33 = p24.m;
                    if (v2_33 == null) {
                        v2_33 = p24.l;
                        if (v2_33 == null) {
                            p28.a("No options page");
                            return;
                        }
                    }
                    org.json.JSONObject v0_22 = this.y;
                    if (v0_22 != null) {
                        v0_22.L(p24, v2_33);
                        p28.b(0);
                        return;
                    } else {
                        p28.a("No browser window");
                        return;
                    }
                } else {
                }
            case -526711453:
                if (p26.equals("storage.get")) {
                    org.json.JSONObject v0_20 = this.h;
                    int v1_17 = p24.a;
                    String v2_30 = p27.optString("area");
                    v2_30.getClass();
                    p28.b(v0_20.c(v1_17, v2_30, p27.opt("keys")));
                    return;
                } else {
                }
            case -526699921:
                if (p26.equals("storage.set")) {
                    String v2_25 = p27.optString("area");
                    v2_25.getClass();
                    boolean v7_27 = this.h;
                    p9 v3_17 = p24.a;
                    x8 v4_15 = p27.optJSONObject("items");
                    if (v4_15 == null) {
                        v4_15 = new org.json.JSONObject();
                    }
                    wi.d(v2_25);
                    java.util.Iterator v6_21 = v7_27.a(v3_17, v2_25);
                    String v8_26 = new org.json.JSONObject();
                    int v9_9 = v4_15.keys();
                    v9_9.getClass();
                    while (v9_9.hasNext()) {
                        int v10_15 = ((String) v9_9.next());
                        org.json.JSONObject v12_9 = v4_15.get(v10_15);
                        boolean v13_9 = v6_21.opt(v10_15);
                        if (v13_9) {
                            if (!io.d(v13_9.toString(), v12_9.toString())) {
                            }
                        }
                        v6_21.put(v10_15, v12_9);
                        boolean v14_7 = new org.json.JSONObject();
                        if (v13_9) {
                            v14_7.put("oldValue", v13_9);
                        }
                        v14_7.put("newValue", v12_9);
                        v8_26.put(v10_15, v14_7);
                    }
                    p9 v3_18 = v7_27.b(v3_17, v2_25, v6_21, v8_26);
                    p28.b(0);
                    if (v3_18 == null) {
                        return;
                    } else {
                        x8 v4_18 = p24.a;
                        int v1_16 = new org.json.JSONObject().put("ext", p24.a).put("event", "storage.changed").put("area", v2_25).put("changes", v3_18);
                        v1_16.getClass();
                        this.d(v4_18, v1_16);
                        return;
                    }
                } else {
                }
            case -278622662:
                if (p26.equals("storage.getBytesInUse")) {
                    String v2_20 = this.h;
                    org.json.JSONObject v0_15 = p24.a;
                    int v1_10 = p27.optString("area");
                    v1_10.getClass();
                    p9 v3_9 = p27.opt("keys");
                    if (!(v3_9 instanceof org.json.JSONObject)) {
                        v11_0 = v3_9;
                    }
                    org.json.JSONObject v0_16 = v2_20.c(v0_15, v1_10, v11_0);
                    int v1_11 = v0_16.keys();
                    v1_11.getClass();
                    while (v1_11.hasNext()) {
                        p9 v3_12 = ((String) v1_11.next());
                        v9_8 += (v3_12.length() + v0_16.get(v3_12).toString().length());
                    }
                    p28.b(Integer.valueOf(v9_8));
                    return;
                } else {
                }
            case -178367377:
                if (p26.equals("runtime.reload")) {
                    this.x(p24.a);
                    if (this.n(p24)) {
                        this.w(p24);
                    }
                    this.s();
                    return;
                } else {
                }
            case -152878519:
                if (p26.equals("runtime.sendMessage")) {
                    p9 v3_2 = p27.opt("message");
                    x8 v4_3 = this.o;
                    java.util.Iterator v6_6 = v4_3.values();
                    v6_6.getClass();
                    boolean v7_13 = new java.util.ArrayList();
                    java.util.Iterator v6_12 = v6_6.iterator();
                    while (v6_12.hasNext()) {
                        String v8_24 = v6_12.next();
                        org.json.JSONObject v12_7 = ((hi) v8_24);
                        if ((v12_7.a.equals(p24.a)) && (((v12_7.d instanceof li)) && (v12_7.b != p25.b))) {
                            v7_13.add(v8_24);
                        }
                    }
                    java.util.Iterator v6_18 = p40.u(new qi(v7_13, 0));
                    boolean v7_16 = ((u6) this.m.get(p24.a));
                    if ((v7_16) && (!(p25.d instanceof ki))) {
                        v11_0 = v7_16;
                    }
                    if (v11_0 != null) {
                        x8 v4_9 = v4_3.values();
                        v4_9.getClass();
                        if (!v4_9.isEmpty()) {
                            x8 v4_10 = v4_9.iterator();
                            while (v4_10.hasNext()) {
                                boolean v7_20 = ((hi) v4_10.next());
                                if ((v7_20.a.equals(p24.a)) && ((v7_20.d instanceof ki))) {
                                    v9_8++;
                                    if (v9_8 < 0) {
                                        throw new ArithmeticException("Count overflow has happened.");
                                    }
                                }
                            }
                        }
                        if (v9_8 < 1) {
                            v9_8 = 1;
                        }
                    }
                    this.g(p24, p25, v3_2, p28, v6_18, v11_0, v9_8);
                    return;
                } else {
                }
            case 632937754:
                if (p26.equals("storage.clear")) {
                    String v2_21 = p27.optString("area");
                    v2_21.getClass();
                    boolean v7_26 = this.h;
                    p9 v3_16 = p24.a;
                    String v8_40;
                    wi.d(v2_21);
                    x8 v4_17 = v7_26.a(v3_16, v2_21);
                    java.util.Iterator v6_25 = new org.json.JSONObject();
                    String v8_27 = v4_17.keys();
                    v8_27.getClass();
                    String v8_30 = new mc(new nz(v8_27)).iterator();
                    if (v8_30.hasNext()) {
                        int v9_16 = v8_30.next();
                        if (v8_30.hasNext()) {
                            int v10_26 = new java.util.ArrayList();
                            v10_26.add(v9_16);
                            while (v8_30.hasNext()) {
                                v10_26.add(v8_30.next());
                            }
                            v8_40 = v10_26;
                        } else {
                            v8_40 = io.y(v9_16);
                        }
                    } else {
                        v8_40 = qh.a;
                    }
                    String v8_43 = v8_40.iterator();
                    while (v8_43.hasNext()) {
                        int v9_32 = ((String) v8_43.next());
                        v6_25.put(v9_32, new org.json.JSONObject().put("oldValue", v4_17.remove(v9_32)));
                    }
                    p9 v3_37 = v7_26.b(v3_16, v2_21, v4_17, v6_25);
                    p28.b(0);
                    if (v3_37 == null) {
                        return;
                    } else {
                        x8 v4_29 = p24.a;
                        int v1_60 = new org.json.JSONObject().put("ext", p24.a).put("event", "storage.changed").put("area", v2_21).put("changes", v3_37);
                        v1_60.getClass();
                        this.d(v4_29, v1_60);
                        return;
                    }
                } else {
                }
            default:
        }
        if (!(p25.d instanceof mi)) {
            switch (p26.hashCode()) {
                case -1671301656:
                    if (p26.equals("dnr.updateRules")) {
                        p9 v3_5;
                        String v2_8 = p27.optString("kind");
                        v2_8.getClass();
                        if (!v2_8.equals("session")) {
                            v3_5 = this.s;
                        } else {
                            v3_5 = this.t;
                        }
                        java.util.Iterator v6_8 = new java.util.HashSet();
                        boolean v7_8 = p27.optJSONArray("removeRuleIds");
                        if (v7_8) {
                            String v8_9 = v7_8.length();
                            int v10_2 = 0;
                            while (v10_2 < v8_9) {
                                v6_8.add(Integer.valueOf(v7_8.optInt(v10_2)));
                                v10_2++;
                            }
                        }
                        x8 v4_4 = p27.optJSONArray("addRules");
                        if (v4_4 == null) {
                            v4_4 = new org.json.JSONArray();
                        }
                        boolean v7_12 = new org.json.JSONArray();
                        String v8_12 = ((org.json.JSONArray) v3_5.get(p24.a));
                        if (v8_12 == null) {
                            v8_12 = new org.json.JSONArray();
                        }
                        int v10_3 = v8_12.length();
                        org.json.JSONObject v12_0 = 0;
                        while (v12_0 < v10_3) {
                            boolean v13_3 = v8_12.optJSONObject(v12_0);
                            if ((v13_3) && (!v6_8.contains(Integer.valueOf(v13_3.optInt("id"))))) {
                                v7_12.put(v13_3);
                            }
                            v12_0++;
                        }
                        java.util.Iterator v6_10 = c8.Z(0, v7_12.length());
                        String v8_16 = new java.util.ArrayList(tb.e0(v6_10));
                        java.util.Iterator v6_11 = v6_10.iterator();
                        while(true) {
                            int v10_6 = ((fo) v6_11);
                            if (!v10_6.c) {
                                break;
                            }
                            v8_16.add(Integer.valueOf(v7_12.getJSONObject(v10_6.nextInt()).optInt("id")));
                        }
                        java.util.Iterator v6_14 = new java.util.LinkedHashSet(v8_16);
                        String v8_17 = v4_4.length();
                        int v10_7 = 0;
                        while (v10_7 < v8_17) {
                            org.json.JSONObject v12_2 = v4_4.optJSONObject(v10_7);
                            if (v12_2 != null) {
                                if (v6_14.add(Integer.valueOf(v12_2.optInt("id")))) {
                                    v7_12.put(v12_2);
                                } else {
                                    org.json.JSONObject v0_6 = v12_2.optInt("id");
                                    int v1_7 = new StringBuilder("Rule with id ");
                                    v1_7.append(v0_6);
                                    v1_7.append(" already exists");
                                    p28.a(v1_7.toString());
                                    return;
                                }
                            }
                            v10_7++;
                        }
                        v3_5.put(p24.a, v7_12);
                        if (v2_8.equals("dynamic")) {
                            String v2_10 = v7_12.toString();
                            v2_10.getClass();
                            this.d.execute(new x8(this, p24, v2_10, 4));
                        }
                        this.r();
                        p28.b(0);
                        return;
                    } else {
                    }
                case -1533884052:
                    if (p26.equals("tabs.create")) {
                        org.json.JSONObject v0_2 = this.y;
                        if (v0_2 != null) {
                            String v2_2 = p27.optString("url");
                            v2_2.getClass();
                            int v1_1 = ri.t(p24, v2_2);
                            if (v1_1 == 0) {
                                v1_1 = "about:blank";
                            }
                            int v9_7;
                            Integer v17_0 = v0_2;
                            org.json.JSONObject v0_3 = com.example.instatool.browser.BrowserActivity.O(v17_0, v1_1, 0, 0, p27.optBoolean("active", 1), 4);
                            int v1_3 = v17_0.C;
                            String v2_5 = ((java.util.ArrayList) v1_3.b).indexOf(v0_3);
                            if (v0_3 != ((p9) v1_3.c)) {
                                v9_7 = 0;
                            } else {
                                v9_7 = 1;
                            }
                            p28.b(v0_3.h(v2_5, v9_7).a());
                            return;
                        } else {
                            p28.a("No browser window");
                            return;
                        }
                    } else {
                    }
                case -1144839592:
                    if (p26.equals("tabs.query")) {
                        int v1_58 = p27.optJSONObject("query");
                        if (v1_58 == 0) {
                            v1_58 = new org.json.JSONObject();
                        }
                        org.json.JSONObject v0_52 = this.a();
                        if (v1_58.has("active")) {
                            boolean v7_38 = new java.util.ArrayList();
                            org.json.JSONObject v0_53 = v0_52.iterator();
                            while (v0_53.hasNext()) {
                                String v8_8 = v0_53.next();
                                if (((oi) v8_8).e == v1_58.optBoolean("active")) {
                                    v7_38.add(v8_8);
                                }
                            }
                            v0_52 = v7_38;
                        }
                        if (v1_58.has("highlighted")) {
                            boolean v7_41 = new java.util.ArrayList();
                            org.json.JSONObject v0_54 = v0_52.iterator();
                            while (v0_54.hasNext()) {
                                String v8_7 = v0_54.next();
                                if (((oi) v8_7).e == v1_58.optBoolean("highlighted")) {
                                    v7_41.add(v8_7);
                                }
                            }
                            v0_52 = v7_41;
                        }
                        if (v1_58.has("status")) {
                            java.util.Iterator v6_49 = new java.util.ArrayList();
                            org.json.JSONObject v0_55 = v0_52.iterator();
                            while (v0_55.hasNext()) {
                                String v8_5;
                                boolean v7_5 = v0_55.next();
                                if (!((oi) v7_5).g) {
                                    v8_5 = "complete";
                                } else {
                                    v8_5 = "loading";
                                }
                                if (v8_5.equals(v1_58.optString("status"))) {
                                    v6_49.add(v7_5);
                                }
                            }
                            v0_52 = v6_49;
                        }
                        if (v1_58.has("index")) {
                            x8 v4_37 = new java.util.ArrayList();
                            org.json.JSONObject v0_56 = v0_52.iterator();
                            while (v0_56.hasNext()) {
                                java.util.Iterator v6_5 = v0_56.next();
                                if (((oi) v6_5).b == v1_58.optInt("index")) {
                                    v4_37.add(v6_5);
                                }
                            }
                            v0_52 = v4_37;
                        }
                        if (v1_58.has("title")) {
                            String v2_77 = v1_58.optString("title");
                            v2_77.getClass();
                            p9 v3_49 = new char[1];
                            v3_49[0] = 42;
                            String v2_80 = java.util.regex.Pattern.compile(rb.l0(m10.K(v2_77, v3_49), ".*", new e6(7), 30));
                            v2_80.getClass();
                            p9 v3_52 = new java.util.ArrayList();
                            org.json.JSONObject v0_57 = v0_52.iterator();
                            while (v0_57.hasNext()) {
                                x8 v4_2 = v0_57.next();
                                if (v2_80.matcher(((oi) v4_2).d).matches()) {
                                    v3_52.add(v4_2);
                                }
                            }
                            v0_52 = v3_52;
                        }
                        if (v1_58.has("url")) {
                            p9 v3_53;
                            int v1_61 = v1_58.get("url");
                            if (!(v1_61 instanceof org.json.JSONArray)) {
                                v3_53 = io.y(v1_61.toString());
                            } else {
                                int v1_63 = ((org.json.JSONArray) v1_61);
                                String v2_84 = c8.Z(0, v1_63.length());
                                v3_53 = new java.util.ArrayList(tb.e0(v2_84));
                                String v2_85 = v2_84.iterator();
                                while(true) {
                                    x8 v4_45 = ((fo) v2_85);
                                    if (!v4_45.c) {
                                        break;
                                    }
                                    v3_53.add(v1_63.optString(v4_45.nextInt()));
                                }
                            }
                            int v1_65 = new java.util.ArrayList();
                            org.json.JSONObject v0_58 = v0_52.iterator();
                            while (v0_58.hasNext()) {
                                String v2_92 = v0_58.next();
                                x8 v4_47 = ((oi) v2_92);
                                if (!v3_53.isEmpty()) {
                                    java.util.Iterator v6_55 = v3_53.iterator();
                                    while (v6_55.hasNext()) {
                                        if (or.b(((String) v6_55.next()), v4_47.c)) {
                                            v1_65.add(v2_92);
                                            break;
                                        }
                                    }
                                }
                            }
                            v0_52 = v1_65;
                        }
                        int v1_67 = new java.util.ArrayList(tb.e0(v0_52));
                        org.json.JSONObject v0_59 = v0_52.iterator();
                        while (v0_59.hasNext()) {
                            v1_67.add(((oi) v0_59.next()).a());
                        }
                        p28.b(new org.json.JSONArray(v1_67));
                        return;
                    } else {
                    }
                case -1116231159:
                    if (p26.equals("tabs.reload")) {
                        int v1_50 = this.y;
                        if (v1_50 != 0) {
                            org.json.JSONObject v0_49 = this.y(p27);
                            if (v0_49 == null) {
                                p28.a("No active tab");
                                return;
                            } else {
                                org.json.JSONObject v0_50 = v1_50.C.d(v0_49);
                                if (v0_50 != null) {
                                    int v1_53 = v0_50.r;
                                    if (v1_53 == 0) {
                                        if (v0_50.o == null) {
                                            v0_50.i.reload();
                                        } else {
                                            v0_50.g();
                                        }
                                    } else {
                                        v0_50.e(v1_53);
                                    }
                                }
                                p28.b(0);
                                return;
                            }
                        } else {
                            p28.a("No browser window");
                            return;
                        }
                    } else {
                    }
                case -1116200716:
                    if (p26.equals("tabs.remove")) {
                        org.json.JSONObject v0_48 = this.y;
                        if (v0_48 != null) {
                            int v1_46 = p27.optJSONArray("tabIds");
                            if (v1_46 == 0) {
                                v1_46 = new org.json.JSONArray();
                            }
                            String v2_74 = v1_46.length();
                            int v9_30 = 0;
                            while (v9_30 < v2_74) {
                                p9 v3_45 = v0_48.C.d(Integer.valueOf(v1_46.optInt(v9_30)));
                                if (v3_45 != null) {
                                    v0_48.t(v3_45);
                                }
                                v9_30++;
                            }
                            p28.b(0);
                            return;
                        } else {
                            p28.a("No browser window");
                            return;
                        }
                    } else {
                    }
                case -1020436167:
                    if (p26.equals("tabs.update")) {
                        p9 v3_40 = this.y;
                        if (v3_40 != null) {
                            String v8_50 = p27.optJSONObject("props");
                            if (v8_50 == null) {
                                v8_50 = new org.json.JSONObject();
                            }
                            org.json.JSONObject v0_42 = this.y(p27);
                            if (v0_42 == null) {
                                p28.a("No active tab");
                                return;
                            } else {
                                String v2_73 = v0_42.intValue();
                                x8 v4_30 = v8_50.optString("url");
                                v4_30.getClass();
                                if (v4_30.length() <= 0) {
                                    v4_30 = 0;
                                }
                                int v1_37;
                                if (v4_30 == null) {
                                    v1_37 = 0;
                                } else {
                                    v1_37 = ri.t(p24, v4_30);
                                }
                                if ((!v8_50.optBoolean("active", 0)) && (!v8_50.optBoolean("highlighted", 0))) {
                                    x8 v4_32 = 0;
                                } else {
                                    v4_32 = 1;
                                }
                                java.util.Iterator v6_45 = v3_40.C;
                                org.json.JSONObject v0_43 = v6_45.d(v0_42);
                                if (v0_43 != null) {
                                    if (v1_37 != 0) {
                                        v0_43.e(v1_37);
                                    }
                                    if (v4_32 != null) {
                                        v3_40.a0(v0_43);
                                    }
                                    int v9_29;
                                    int v1_41 = ((java.util.ArrayList) v6_45.b).indexOf(v0_43);
                                    if (v0_43 != ((p9) v6_45.c)) {
                                        v9_29 = 0;
                                    } else {
                                        v9_29 = 1;
                                    }
                                    v11_0 = v0_43.h(v1_41, v9_29);
                                }
                                if (v11_0 != null) {
                                    p28.b(v11_0.a());
                                    return;
                                } else {
                                    org.json.JSONObject v0_46 = new StringBuilder("No tab with id: ");
                                    v0_46.append(v2_73);
                                    p28.a(v0_46.toString());
                                    return;
                                }
                            }
                        } else {
                            p28.a("No browser window");
                            return;
                        }
                    } else {
                    }
                case -890585882:
                    if (p26.equals("tabs.get")) {
                        org.json.JSONObject v0_38 = this.a().iterator();
                        while (v0_38.hasNext()) {
                            int v1_33 = v0_38.next();
                            if (((oi) v1_33).a == p27.optInt("tabId", -1)) {
                                v11_0 = v1_33;
                                break;
                            }
                        }
                        oi v11_4 = ((oi) v11_0);
                        if (v11_4 != null) {
                            p28.b(v11_4.a());
                            return;
                        } else {
                            org.json.JSONObject v0_40 = p27.opt("tabId");
                            int v1_35 = new StringBuilder("No tab with id: ");
                            v1_35.append(v0_40);
                            p28.a(v1_35.toString());
                            return;
                        }
                    } else {
                    }
                case -574314169:
                    if (p26.equals("dnr.getRules")) {
                        org.json.JSONObject v0_33;
                        String v2_68 = p27.optString("kind");
                        v2_68.getClass();
                        if (!v2_68.equals("session")) {
                            v0_33 = this.s;
                        } else {
                            v0_33 = this.t;
                        }
                        org.json.JSONObject v0_35 = ((org.json.JSONArray) v0_33.get(p24.a));
                        if (v0_35 == null) {
                            v0_35 = new org.json.JSONArray();
                        }
                        p28.b(v0_35);
                        return;
                    } else {
                    }
                case 354804734:
                    if (p26.equals("dnr.getEnabledRulesets")) {
                        p28.b(new org.json.JSONArray(rb.r0(this.h(p24))));
                        return;
                    } else {
                    }
                case 1763794159:
                    if (p26.equals("tabs.sendMessage")) {
                        int v9_25;
                        String v2_57 = p27.optInt("tabId", -1);
                        if ((!p27.has("frameId")) || (p27.optInt("frameId") != 0)) {
                            v9_25 = 0;
                        } else {
                            v9_25 = 1;
                        }
                        p9 v3_32 = this.o.values();
                        v3_32.getClass();
                        java.util.Iterator v6_40 = new java.util.ArrayList();
                        p9 v3_33 = v3_32.iterator();
                        while (v3_33.hasNext()) {
                            boolean v7_35 = v3_33.next();
                            String v8_45 = ((hi) v7_35);
                            int v10_31 = v8_45.d;
                            if ((v8_45.a.equals(p24.a)) && (((v10_31 instanceof mi)) && ((((mi) v10_31).a == v2_57) && ((v9_25 == 0) || (v8_45.g))))) {
                                v6_40.add(v7_35);
                            }
                        }
                        this.g(p24, p25, p27.opt("message"), p28, p40.u(new qi(v6_40, 1)), 0, 0);
                        return;
                    } else {
                    }
                case 2087230303:
                    if (p26.equals("dnr.updateEnabledRulesets")) {
                        p9 v3_26 = new java.util.LinkedHashSet(this.h(p24));
                        String v2_50 = p27.optJSONArray("disableRulesetIds");
                        if (v2_50 != null) {
                            java.util.Iterator v6_35 = v2_50.length();
                            boolean v7_31 = 0;
                            while (v7_31 < v6_35) {
                                v3_26.remove(v2_50.optString(v7_31));
                                v7_31++;
                            }
                        }
                        String v2_52 = p27.optJSONArray("enableRulesetIds");
                        if (v2_52 != null) {
                            x8 v4_24 = v2_52.length();
                            java.util.Iterator v6_36 = 0;
                            while (v6_36 < v4_24) {
                                boolean v7_32 = v2_52.optString(v6_36);
                                String v8_41 = p24.o;
                                if ((v8_41 == null) || (!v8_41.isEmpty())) {
                                    int v9_24 = v8_41.size();
                                    int v10_30 = 0;
                                    while (v10_30 < v9_24) {
                                        org.json.JSONObject v12_15 = v8_41.get(v10_30);
                                        v10_30++;
                                        if (((qy) v12_15).a.equals(v7_32)) {
                                            v3_26.add(v7_32);
                                            v6_36++;
                                        }
                                    }
                                }
                                org.json.JSONObject v0_29 = new StringBuilder("Invalid ruleset id: ");
                                v0_29.append(v7_32);
                                p28.a(v0_29.toString());
                                return;
                            }
                        }
                        String v2_53 = this.e;
                        v2_53.getClass();
                        String v2_54 = v2_53.edit();
                        v2_54.getClass();
                        v2_54.putString("rulesets:".concat(p24.a), new org.json.JSONArray(rb.r0(v3_26)).toString());
                        v2_54.apply();
                        this.r();
                        p28.b(0);
                        return;
                    } else {
                    }
                default:
            }
            p28.a("Unsupported API: ".concat(p26));
            return;
        } else {
            p28.a(p26.concat(" is not available in content scripts"));
            return;
        }
    }

    public final boolean k(ei p3, boolean p4)
    {
        if ((!this.n(p3)) || ((p4 != null) && (!this.e.getBoolean("incognito:".concat(p3.a), 0)))) {
            return 0;
        } else {
            return 1;
        }
    }

    public final void l(gi p20)
    {
        ri v1_0 = this;
        Throwable v0_3 = p20.c;
        String v3_11 = v0_3.size();
        java.util.Set v5_1 = 0;
        while (v5_1 < v3_11) {
            java.util.Iterator v6_1 = v0_3.get(v5_1);
            v5_1++;
            ((dz) v6_1).a.remove();
        }
        p20.c.clear();
        if (this.j) {
            String v3_2;
            Throwable v0_0 = p20.b;
            if (!(v0_0 instanceof mi)) {
                v3_2 = 0;
            } else {
                v3_2 = ((mi) v0_0);
            }
            if (v3_2 != null) {
                java.util.Iterator v6_0 = this.l.values().iterator();
                while (v6_0.hasNext()) {
                    ei v7_1 = ((ei) v6_0.next());
                    if (v1_0.k(v7_1, v3_2.b)) {
                        java.util.ArrayList v8 = v7_1.j;
                        int v9 = v8.size();
                        Throwable v0_8 = 0;
                        while (v0_8 < v9) {
                            int v11 = (v0_8 + 1);
                            String v10_7 = ((tc) v8.get(v0_8));
                            try {
                                Throwable v0_14 = v1_0.A(v7_1, v10_7, v3_2.b);
                            } catch (Throwable v0_15) {
                                v0_14 = new hy(v0_15);
                            }
                            StringBuilder v12_8 = iy.a(v0_14);
                            if (v12_8 != null) {
                                StringBuilder v14_7 = v7_1.a;
                                String v15_9 = v10_7.a;
                                java.util.Iterator v4_4 = new StringBuilder("Content script ");
                                v4_4.append(v14_7);
                                v4_4.append("#");
                                v4_4.append(v15_9);
                                v4_4.append(" failed to build");
                                android.util.Log.e("ExtensionManager", v4_4.toString(), v12_8);
                            }
                            if ((v0_14 instanceof hy)) {
                                v0_14 = 0;
                            }
                            Throwable v0_17 = ((String) v0_14);
                            if (v0_17 != null) {
                                java.util.Iterator v4_7 = v10_7.b;
                                java.util.Set v5_0 = new java.util.LinkedHashSet();
                                java.util.Iterator v4_1 = v4_7.iterator();
                                while (v4_1.hasNext()) {
                                    String v10_10 = ((String) v4_1.next());
                                    if (!io.d(v10_10, "<all_urls>")) {
                                        String v10_11 = or.a.b(v10_10);
                                        if (v10_11 != null) {
                                            StringBuilder v12_1 = ((String) ((pr) v10_11.a()).get(1));
                                            String v10_3 = ((String) ((pr) v10_11.a()).get(2));
                                            int v16 = v3_2;
                                            if ((io.d(v12_1, "*")) || ((io.d(v12_1, "http")) || (io.d(v12_1, "https")))) {
                                                String v10_4;
                                                java.util.Iterator v17 = v4_1;
                                                java.util.Iterator v4_0 = m10.N(v10_3, 58);
                                                if (!m10.B(v10_3, 58)) {
                                                    v10_4 = 0;
                                                } else {
                                                    v10_4 = m10.L(v10_3, 58);
                                                }
                                                if ((!v4_0.equals("*")) && (!io.d(v10_4, "*"))) {
                                                    String v10_5;
                                                    if (v10_4 == null) {
                                                        v10_5 = 0;
                                                    } else {
                                                        v10_5 = ":".concat(v10_4);
                                                    }
                                                    if (v10_5 == null) {
                                                        v10_5 = "";
                                                    }
                                                    ri v1_2;
                                                    if (!io.d(v12_1, "*")) {
                                                        v1_2 = io.y(v12_1);
                                                    } else {
                                                        v1_2 = sb.b0(new String[] {"http", "https"}));
                                                    }
                                                    ri v1_4 = v1_2.iterator();
                                                    while (v1_4.hasNext()) {
                                                        String v3_5 = ((String) v1_4.next());
                                                        if (!v4_0.startsWith("*.")) {
                                                            StringBuilder v12_4 = new StringBuilder();
                                                            v12_4.append(v3_5);
                                                            v12_4.append("://");
                                                            v12_4.append(v4_0);
                                                            v12_4.append(v10_5);
                                                            v5_0.add(v12_4.toString());
                                                        } else {
                                                            StringBuilder v14_3 = new StringBuilder();
                                                            v14_3.append(v3_5);
                                                            v14_3.append("://");
                                                            v14_3.append(v4_0);
                                                            v14_3.append(v10_5);
                                                            v5_0.add(v14_3.toString());
                                                            StringBuilder v12_5 = m10.J(v4_0, "*.");
                                                            StringBuilder v14_6 = new StringBuilder();
                                                            v14_6.append(v3_5);
                                                            v14_6.append("://");
                                                            v14_6.append(v12_5);
                                                            v14_6.append(v10_5);
                                                            v5_0.add(v14_6.toString());
                                                        }
                                                    }
                                                    v3_2 = v16;
                                                    v4_1 = v17;
                                                } else {
                                                    v5_0 = jy.o("*");
                                                }
                                            } else {
                                                v5_0 = jy.o("*");
                                            }
                                        }
                                    } else {
                                        v5_0 = jy.o("*");
                                        break;
                                    }
                                    if (!v5_0.isEmpty()) {
                                        try {
                                            Throwable v0_5 = p70.a(p20.a, v0_17, v5_0);
                                        } catch (Throwable v0_6) {
                                            v0_5 = new hy(v0_6);
                                        }
                                        if (!(v0_5 instanceof hy)) {
                                            p20.c.add(((dz) p20));
                                        }
                                        Throwable v0_7 = iy.a(v0_5);
                                        if (v0_7 != null) {
                                            ri v1_12 = v7_1.a;
                                            String v3_10 = new StringBuilder("addDocumentStartJavaScript failed for ");
                                            v3_10.append(v1_12);
                                            v3_10.append(" (");
                                            v3_10.append(v5_0);
                                            v3_10.append(")");
                                            android.util.Log.e("ExtensionManager", v3_10.toString(), v0_7);
                                        }
                                    }
                                    v1_0 = this;
                                    v0_8 = v11;
                                    v3_2 = v16;
                                }
                                v16 = v3_2;
                            } else {
                                v0_8 = v11;
                            }
                            return;
                        }
                    }
                    v1_0 = this;
                }
            }
        }
        return;
    }

    public final android.webkit.WebResourceResponse m(android.webkit.WebResourceRequest p21, boolean p22)
    {
        boolean v1_2 = p21.getUrl();
        if (io.d(v1_2.getHost(), "appassets.androidplatform.net")) {
            int v2_0 = v1_2.getPath();
            if (v2_0 == 0) {
                v2_0 = "";
            }
            if (v2_0.startsWith("/extensions/")) {
                return this.v(v1_2);
            }
        }
        boolean v16;
        int v2_8 = 0;
        if (p22 != 0) {
            String v3_2 = v1_2.getScheme();
            if ((io.d(v3_2, "http")) || (io.d(v3_2, "https"))) {
                String v5_0 = v1_2.toString();
                v5_0.getClass();
                try {
                    String v3_14 = ((Long) this.u.get(v5_0));
                } catch (Throwable v0_1) {
                    throw v0_1;
                }
                if ((v3_14 == null) || ((System.currentTimeMillis() - v3_14.longValue()) >= 5000)) {
                    boolean v1_27 = this.i;
                    String v3_19 = p21.getMethod();
                    if (v3_19 == null) {
                        v3_19 = "GET";
                    }
                    java.util.ArrayList v6_10 = v3_19;
                    int v7_10 = p21.isForMainFrame();
                    String v3_20 = p21.getRequestHeaders();
                    if (v3_20 == null) {
                        v3_20 = rh.a;
                    }
                    int v9_28;
                    vu v8_15 = v3_20;
                    String v3_21 = p21.getRequestHeaders();
                    if (v3_21 == null) {
                        v9_28 = 0;
                    } else {
                        String v3_22 = v3_21.entrySet();
                        if (v3_22 == null) {
                        } else {
                            String v3_26 = v3_22.iterator();
                            while (v3_26.hasNext()) {
                                int v4_33 = v3_26.next();
                                int v9_23 = ((java.util.Map$Entry) v4_33);
                                if ((u10.x(((String) v9_23.getKey()), "Origin")) || (u10.x(((String) v9_23.getKey()), "Referer"))) {
                                }
                                int v4_49 = ((java.util.Map$Entry) v4_33);
                                if (v4_49 == 0) {
                                } else {
                                    v9_28 = ((String) v4_49.getValue());
                                }
                            }
                            v4_33 = 0;
                        }
                    }
                    boolean v1_41;
                    int v4_51 = new af(v5_0, v6_10, v7_10, v8_15, v9_28);
                    v1_27.getClass();
                    int v7_0 = "";
                    boolean v1_0 = v1_27.a;
                    if (!v1_0.isEmpty()) {
                        vu v8_1 = pg.p(v4_51);
                        boolean v1_1 = v1_0.iterator();
                        while (v1_1.hasNext()) {
                            String v19;
                            String v10_1 = v1_1.next();
                            String v12_1 = ((bf) v10_1);
                            int v13_0 = v12_1.e;
                            int v14_2 = pg.r(v13_0.optJSONArray("resourceTypes"), 1);
                            boolean v15_2 = pg.r(v13_0.optJSONArray("excludedResourceTypes"), 1);
                            if (v14_2 == 0) {
                                if (!v15_2) {
                                    if (!v8_1.equals("main_frame")) {
                                        int v14_9 = pg.r(v13_0.optJSONArray("requestMethods"), 1);
                                        if (v14_9 == 0) {
                                            v16 = v2_8;
                                            int v2_7 = pg.r(v13_0.optJSONArray("excludedRequestMethods"), 1);
                                            if (v2_7 != 0) {
                                                int v14_10 = v4_51.b;
                                                boolean v15_4 = java.util.Locale.ROOT;
                                                v15_4.getClass();
                                                int v14_11 = v14_10.toLowerCase(v15_4);
                                                v14_11.getClass();
                                                if (v2_7.contains(v14_11)) {
                                                    v19 = v1_1;
                                                    v2_8 = v16;
                                                    v1_1 = v19;
                                                }
                                            }
                                            int v2_10 = v4_51.a;
                                            int v14_13 = android.net.Uri.parse(v2_10).getHost();
                                            if (v14_13 == 0) {
                                                v14_13 = "";
                                            }
                                            int v22_1;
                                            boolean v15_5 = java.util.Locale.ROOT;
                                            v15_5.getClass();
                                            int v14_14 = v14_13.toLowerCase(v15_5);
                                            v14_14.getClass();
                                            boolean v15_8 = pg.r(v13_0.optJSONArray("requestDomains"), 1);
                                            if (!v15_8) {
                                                v19 = v1_1;
                                                v22_1 = 0;
                                            } else {
                                                if (!v15_8.isEmpty()) {
                                                    v22_1 = 0;
                                                    int v9_0 = v15_8.size();
                                                    android.net.Uri$Builder v11_1 = 0;
                                                    while (v11_1 < v9_0) {
                                                        Object v18 = v15_8.get(v11_1);
                                                        v11_1++;
                                                        v19 = v1_1;
                                                        if (!pg.i(v14_14, ((String) v18))) {
                                                            v1_1 = v19;
                                                        } else {
                                                            boolean v1_8 = pg.r(v13_0.optJSONArray("excludedRequestDomains"), 1);
                                                            if ((v1_8) && (!v1_8.isEmpty())) {
                                                                int v9_3 = v1_8.size();
                                                                android.net.Uri$Builder v11_2 = v22_1;
                                                                while (v11_2 < v9_3) {
                                                                    boolean v15_9 = v1_8.get(v11_2);
                                                                    v11_2++;
                                                                    if (pg.i(v14_14, ((String) v15_9))) {
                                                                    }
                                                                }
                                                            }
                                                            boolean v1_12;
                                                            boolean v1_9 = v4_51.e;
                                                            if (!v1_9) {
                                                                v1_12 = v16;
                                                            } else {
                                                                boolean v1_11 = android.net.Uri.parse(v1_9).getHost();
                                                                if (!v1_11) {
                                                                } else {
                                                                    int v9_4 = java.util.Locale.ROOT;
                                                                    v9_4.getClass();
                                                                    v1_12 = v1_11.toLowerCase(v9_4);
                                                                    v1_12.getClass();
                                                                }
                                                            }
                                                            int v9_7 = pg.r(v13_0.optJSONArray("initiatorDomains"), 1);
                                                            if (v9_7 != 0) {
                                                                if ((v1_12) && (!v9_7.isEmpty())) {
                                                                    android.net.Uri$Builder v11_5 = v9_7.size();
                                                                    int v14_15 = v22_1;
                                                                    while (v14_15 < v11_5) {
                                                                        boolean v15_12 = v9_7.get(v14_15);
                                                                        v14_15++;
                                                                        if (pg.i(v1_12, ((String) v15_12))) {
                                                                        }
                                                                    }
                                                                }
                                                            }
                                                            int v9_10 = pg.r(v13_0.optJSONArray("excludedInitiatorDomains"), 1);
                                                            if ((v9_10 != 0) && ((v1_12) && (!v9_10.isEmpty()))) {
                                                                android.net.Uri$Builder v11_8 = v9_10.size();
                                                                int v13_1 = v22_1;
                                                                while (v13_1 < v11_8) {
                                                                    int v14_16 = v9_10.get(v13_1);
                                                                    v13_1++;
                                                                    if (pg.i(v1_12, ((String) v14_16))) {
                                                                    }
                                                                }
                                                            }
                                                            boolean v1_13 = v12_1.g;
                                                            if ((!v1_13) || (v1_13.a.matcher(v2_10).find())) {
                                                                boolean v1_17 = v12_1.h;
                                                                if ((!v1_17) || (v1_17.a.matcher(v2_10).find())) {
                                                                    String v10_2 = ((bf) v10_1);
                                                                    if (v10_2 != null) {
                                                                        boolean v1_21 = v10_2.d;
                                                                        int v2_11 = v1_21.hashCode();
                                                                        if (v2_11 == -776144932) {
                                                                            if (v1_21.equals("redirect")) {
                                                                                String v3_5;
                                                                                boolean v1_23 = "/";
                                                                                int v2_13 = v10_2.c.optJSONObject("redirect");
                                                                                if (v2_13 != 0) {
                                                                                    v3_5 = v2_13.optString("url");
                                                                                    v3_5.getClass();
                                                                                    if (v3_5.length() <= 0) {
                                                                                        v3_5 = v16;
                                                                                    }
                                                                                    if (v3_5 == null) {
                                                                                        String v3_8 = v2_13.optString("extensionPath");
                                                                                        v3_8.getClass();
                                                                                        if (v3_8.length() <= 0) {
                                                                                            v3_8 = v16;
                                                                                        }
                                                                                        if (v3_8 == null) {
                                                                                            String v3_10 = v2_13.optString("regexSubstitution");
                                                                                            v3_10.getClass();
                                                                                            if (v3_10.length() <= 0) {
                                                                                                v3_10 = v16;
                                                                                            }
                                                                                            if (v3_10 == null) {
                                                                                                int v2_14 = v2_13.optJSONObject("transform");
                                                                                                if (v2_14 == 0) {
                                                                                                    v3_5 = v16;
                                                                                                } else {
                                                                                                    String v10_3 = android.net.Uri.parse(v5_0);
                                                                                                    android.net.Uri$Builder v11_9 = v10_3.buildUpon();
                                                                                                    String v12_3 = v2_14.optString("scheme");
                                                                                                    v12_3.getClass();
                                                                                                    if (v12_3.length() <= 0) {
                                                                                                        v12_3 = v16;
                                                                                                    }
                                                                                                    if (v12_3 != null) {
                                                                                                        v11_9.scheme(v12_3);
                                                                                                    }
                                                                                                    if ((v2_14.has("host")) || (v2_14.has("port"))) {
                                                                                                        vu v8_3 = v2_14.optString("host");
                                                                                                        if (v8_3.length() == 0) {
                                                                                                            v8_3 = v10_3.getHost();
                                                                                                            if (v8_3 == null) {
                                                                                                                v8_3 = "";
                                                                                                            }
                                                                                                        }
                                                                                                        int v9_13;
                                                                                                        if (!v2_14.has("port")) {
                                                                                                            int v9_12 = v10_3.getPort();
                                                                                                            String v12_8 = Integer.valueOf(v9_12);
                                                                                                            if (v9_12 <= 0) {
                                                                                                                v12_8 = v16;
                                                                                                            }
                                                                                                            if (v12_8 == null) {
                                                                                                                v9_13 = v16;
                                                                                                            } else {
                                                                                                                v9_13 = v12_8.toString();
                                                                                                            }
                                                                                                            if (v9_13 == 0) {
                                                                                                                v9_13 = "";
                                                                                                            }
                                                                                                        } else {
                                                                                                            v9_13 = v2_14.optString("port");
                                                                                                        }
                                                                                                        String v12_10;
                                                                                                        String v12_9 = v10_3.getEncodedUserInfo();
                                                                                                        if (v12_9 == null) {
                                                                                                            v12_10 = v16;
                                                                                                        } else {
                                                                                                            v12_10 = v12_9.concat("@");
                                                                                                        }
                                                                                                        if (v12_10 == null) {
                                                                                                            v12_10 = "";
                                                                                                        }
                                                                                                        int v9_14;
                                                                                                        v9_13.getClass();
                                                                                                        if (v9_13.length() <= 0) {
                                                                                                            v9_14 = "";
                                                                                                        } else {
                                                                                                            v9_14 = ":".concat(v9_13);
                                                                                                        }
                                                                                                        int v13_7 = new StringBuilder(v12_10);
                                                                                                        v13_7.append(v8_3);
                                                                                                        v13_7.append(v9_14);
                                                                                                        v11_9.encodedAuthority(v13_7.toString());
                                                                                                    }
                                                                                                    if (v2_14.has("path")) {
                                                                                                        java.util.ArrayList v6_3 = v2_14.optString("path");
                                                                                                        if (v6_3.length() != 0) {
                                                                                                            v1_23 = v6_3;
                                                                                                        }
                                                                                                        v11_9.encodedPath(v1_23);
                                                                                                    }
                                                                                                    if (!v2_14.has("query")) {
                                                                                                        boolean v1_26 = v2_14.optJSONObject("queryTransform");
                                                                                                        if (v1_26) {
                                                                                                            int v4_8 = v10_3.getEncodedQuery();
                                                                                                            if (v4_8 != 0) {
                                                                                                                v7_0 = v4_8;
                                                                                                            }
                                                                                                            int v4_9 = new char[1];
                                                                                                            v4_9[v22_1] = 38;
                                                                                                            int v4_10 = m10.K(v7_0, v4_9);
                                                                                                            java.util.ArrayList v6_7 = new java.util.ArrayList();
                                                                                                            int v4_11 = v4_10.iterator();
                                                                                                            while (v4_11.hasNext()) {
                                                                                                                int v7_11 = v4_11.next();
                                                                                                                if (((String) v7_11).length() > 0) {
                                                                                                                    v6_7.add(v7_11);
                                                                                                                }
                                                                                                            }
                                                                                                            int v4_13 = new java.util.ArrayList(tb.e0(v6_7));
                                                                                                            int v7_3 = v6_7.size();
                                                                                                            vu v8_7 = v22_1;
                                                                                                            while (v8_7 < v7_3) {
                                                                                                                int v9_19 = v6_7.get(v8_7);
                                                                                                                v8_7++;
                                                                                                                int v9_20 = ((String) v9_19);
                                                                                                                v4_13.add(new vu(m10.N(v9_20, 61), v9_20));
                                                                                                            }
                                                                                                            java.util.ArrayList v6_9 = new java.util.ArrayList(v4_13);
                                                                                                            int v4_16 = pg.r(v1_26.optJSONArray("removeParams"), v22_1);
                                                                                                            if (v4_16 != 0) {
                                                                                                                String v10_4;
                                                                                                                int v9_16 = 1;
                                                                                                                int v7_6 = (v6_9.size() - 1);
                                                                                                                if (v7_6 < 0) {
                                                                                                                    v10_4 = 0;
                                                                                                                } else {
                                                                                                                    vu v8_8 = 0;
                                                                                                                    v10_4 = 0;
                                                                                                                    while(true) {
                                                                                                                        String v12_11 = v6_9.get(v8_8);
                                                                                                                        int v13_9 = ((vu) v12_11);
                                                                                                                        v13_9.getClass();
                                                                                                                        if (v4_16.contains(android.net.Uri.decode(((String) v13_9.a))) != v9_16) {
                                                                                                                            if (v10_4 != v8_8) {
                                                                                                                                v6_9.set(v10_4, v12_11);
                                                                                                                            }
                                                                                                                            v10_4++;
                                                                                                                        }
                                                                                                                        if (v8_8 == v7_6) {
                                                                                                                            break;
                                                                                                                        }
                                                                                                                        v8_8++;
                                                                                                                        v9_16 = 1;
                                                                                                                    }
                                                                                                                }
                                                                                                                if (v10_4 < v6_9.size()) {
                                                                                                                    int v4_19 = (v6_9.size() - 1);
                                                                                                                    if (v10_4 > v4_19) {
                                                                                                                        boolean v1_28 = v1_26.optJSONArray("addOrReplaceParams");
                                                                                                                        if (v1_28) {
                                                                                                                            int v4_21 = v1_28.length();
                                                                                                                            int v7_7 = 0;
                                                                                                                            while (v7_7 < v4_21) {
                                                                                                                                vu v8_9 = v1_28.optJSONObject(v7_7);
                                                                                                                                if (v8_9 != null) {
                                                                                                                                    int v9_18 = v8_9.optString("key");
                                                                                                                                    String v10_5 = android.net.Uri.encode(v9_18);
                                                                                                                                    String v12_14 = android.net.Uri.encode(v8_9.optString("value"));
                                                                                                                                    int v13_15 = new StringBuilder();
                                                                                                                                    v13_15.append(v10_5);
                                                                                                                                    v13_15.append("=");
                                                                                                                                    v13_15.append(v12_14);
                                                                                                                                    String v10_7 = v13_15.toString();
                                                                                                                                    String v12_15 = v6_9.size();
                                                                                                                                    int v13_16 = 0;
                                                                                                                                    int v14_19 = 0;
                                                                                                                                    while (v14_19 < v12_15) {
                                                                                                                                        boolean v15_15 = v6_9.get(v14_19);
                                                                                                                                        v14_19++;
                                                                                                                                        if (!io.d(android.net.Uri.decode(((String) ((vu) v15_15).a)), v9_18)) {
                                                                                                                                            v13_16++;
                                                                                                                                        }
                                                                                                                                        if (v13_16 < 0) {
                                                                                                                                            if (!v8_9.optBoolean("replaceOnly", 0)) {
                                                                                                                                                v6_9.add(new vu(v9_18, v10_7));
                                                                                                                                            }
                                                                                                                                        } else {
                                                                                                                                            v6_9.set(v13_16, new vu(v9_18, v10_7));
                                                                                                                                        }
                                                                                                                                    }
                                                                                                                                    v13_16 = -1;
                                                                                                                                }
                                                                                                                                v7_7++;
                                                                                                                            }
                                                                                                                        }
                                                                                                                        boolean v1_30 = rb.l0(v6_9, "&", new e6(5), 30);
                                                                                                                        if (v1_30.length() == 0) {
                                                                                                                            v1_30 = v16;
                                                                                                                        }
                                                                                                                        v11_9.encodedQuery(v1_30);
                                                                                                                        if (v2_14.has("fragment")) {
                                                                                                                            boolean v1_34 = v2_14.optString("fragment");
                                                                                                                            v1_34.getClass();
                                                                                                                            boolean v1_35 = m10.J(v1_34, "#");
                                                                                                                            if (v1_35.length() == 0) {
                                                                                                                                v1_35 = v16;
                                                                                                                            }
                                                                                                                            v11_9.encodedFragment(v1_35);
                                                                                                                        }
                                                                                                                        v3_5 = v11_9.build().toString();
                                                                                                                        v3_5.getClass();
                                                                                                                        if (v3_5 != null) {
                                                                                                                            if (v3_5.equals(v5_0)) {
                                                                                                                                v3_5 = v16;
                                                                                                                            }
                                                                                                                            if (v3_5 != null) {
                                                                                                                                v1_41 = new ze(v3_5);
                                                                                                                                if (v1_41) {
                                                                                                                                    if (!v1_41.equals(ye.a)) {
                                                                                                                                        if (!(v1_41 instanceof ze)) {
                                                                                                                                            throw new uk();
                                                                                                                                        } else {
                                                                                                                                            int v2_30 = ((ze) v1_41);
                                                                                                                                            String v3_29 = android.net.Uri.parse(v2_30.a);
                                                                                                                                            if (io.d(v3_29.getHost(), "appassets.androidplatform.net")) {
                                                                                                                                                int v4_36 = v3_29.getPath();
                                                                                                                                                if (v4_36 == 0) {
                                                                                                                                                    v4_36 = "";
                                                                                                                                                }
                                                                                                                                                if (v4_36.startsWith("/extensions/")) {
                                                                                                                                                    return this.v(v3_29);
                                                                                                                                                }
                                                                                                                                            }
                                                                                                                                            String v3_30 = p21.getMethod();
                                                                                                                                            if (v3_30 == null) {
                                                                                                                                                v3_30 = "GET";
                                                                                                                                            }
                                                                                                                                            java.util.ArrayList v6_15 = v3_30;
                                                                                                                                            int v7_12 = p21.isForMainFrame();
                                                                                                                                            String v3_31 = p21.getRequestHeaders();
                                                                                                                                            if (v3_31 == null) {
                                                                                                                                                v3_31 = rh.a;
                                                                                                                                            }
                                                                                                                                            String v3_32 = pg.p(new af(v5_0, v6_15, v7_12, v3_31, 0));
                                                                                                                                            if ((v3_32.equals("main_frame")) || (v3_32.equals("sub_frame"))) {
                                                                                                                                                try {
                                                                                                                                                    this.u.put(((ze) v1_41).a, Long.valueOf(System.currentTimeMillis()));
                                                                                                                                                    Throwable v0_5 = v2_30.a;
                                                                                                                                                    boolean v1_48 = org.json.JSONObject.quote(v0_5);
                                                                                                                                                    Throwable v0_8 = u10.y(u10.y(u10.y(v0_5, "&", "&amp;"), "\"", "&quot;"), "<", "&lt;");
                                                                                                                                                    int v2_35 = new StringBuilder("<!doctype html><html data-instatool-redirect><head><meta charset=\"utf-8\"><meta http-equiv=\"refresh\" content=\"0;url=");
                                                                                                                                                    v2_35.append(v0_8);
                                                                                                                                                    v2_35.append("\"><script>location.replace(");
                                                                                                                                                    v2_35.append(v1_48);
                                                                                                                                                    v2_35.append(");</script></head><body></body></html>");
                                                                                                                                                    Throwable v0_11 = v2_35.toString();
                                                                                                                                                    java.util.ArrayList v6_17 = java.util.Collections.singletonMap("Cache-Control", "no-store");
                                                                                                                                                    v6_17.getClass();
                                                                                                                                                    Throwable v0_12 = v0_11.getBytes(ka.a);
                                                                                                                                                    v0_12.getClass();
                                                                                                                                                    return new android.webkit.WebResourceResponse("text/html", "utf-8", 200, "OK", v6_17, new java.io.ByteArrayInputStream(v0_12));
                                                                                                                                                } catch (Throwable v0_13) {
                                                                                                                                                    throw v0_13;
                                                                                                                                                }
                                                                                                                                            } else {
                                                                                                                                                boolean v1_52 = new StringBuilder("Redirect of ");
                                                                                                                                                v1_52.append(v3_32);
                                                                                                                                                v1_52.append(" requests is not supported: ");
                                                                                                                                                v1_52.append(v5_0);
                                                                                                                                                android.util.Log.d("ExtensionManager", v1_52.toString());
                                                                                                                                                return v16;
                                                                                                                                            }
                                                                                                                                        }
                                                                                                                                    } else {
                                                                                                                                        Throwable v0_16 = new byte[0];
                                                                                                                                        return new android.webkit.WebResourceResponse("text/plain", "utf-8", 403, "Blocked", ri.e(), new java.io.ByteArrayInputStream(v0_16));
                                                                                                                                    }
                                                                                                                                }
                                                                                                                                return v16;
                                                                                                                            }
                                                                                                                        }
                                                                                                                        v1_41 = v16;
                                                                                                                    }
                                                                                                                    while(true) {
                                                                                                                        v6_9.remove(v4_19);
                                                                                                                        if (v4_19 == v10_4) {
                                                                                                                            break;
                                                                                                                        }
                                                                                                                        v4_19--;
                                                                                                                    }
                                                                                                                }
                                                                                                            }
                                                                                                        }
                                                                                                    } else {
                                                                                                        boolean v1_31 = v2_14.optString("query");
                                                                                                        v1_31.getClass();
                                                                                                        boolean v1_32 = m10.J(v1_31, "?");
                                                                                                        if (v1_32.length() == 0) {
                                                                                                            v1_32 = v16;
                                                                                                        }
                                                                                                        v11_9.encodedQuery(v1_32);
                                                                                                    }
                                                                                                }
                                                                                            } else {
                                                                                                boolean v1_37 = v10_2.g;
                                                                                                if (!v1_37) {
                                                                                                } else {
                                                                                                    boolean v1_38 = ox.a(v1_37, v5_0);
                                                                                                    if (v1_38) {
                                                                                                        v3_5 = new ox("\\\\(\\d)").c(v3_10, new f(v1_38, 2));
                                                                                                    }
                                                                                                }
                                                                                            }
                                                                                        } else {
                                                                                            int v2_20 = v10_2.a;
                                                                                            String v3_23 = m10.J(v3_8, "/");
                                                                                            int v4_31 = new StringBuilder("https://appassets.androidplatform.net/extensions/");
                                                                                            v4_31.append(v2_20);
                                                                                            v4_31.append("/");
                                                                                            v4_31.append(v3_23);
                                                                                            v3_5 = v4_31.toString();
                                                                                        }
                                                                                    }
                                                                                }
                                                                            }
                                                                        } else {
                                                                            if (v2_11 == 93832333) {
                                                                                if (v1_21.equals("block")) {
                                                                                    v1_41 = ye.a;
                                                                                }
                                                                            } else {
                                                                                if ((v2_11 == 1146205921) && ((v1_21.equals("upgradeScheme")) && (v5_0.startsWith("http://")))) {
                                                                                    v1_41 = new ze("https://".concat(m10.J(v5_0, "http://")));
                                                                                }
                                                                            }
                                                                        }
                                                                    }
                                                                }
                                                            }
                                                        }
                                                    }
                                                }
                                                v19 = v1_1;
                                            }
                                        } else {
                                            boolean v15_3 = v4_51.b;
                                            v16 = v2_8;
                                            int v2_2 = java.util.Locale.ROOT;
                                            v2_2.getClass();
                                            int v2_3 = v15_3.toLowerCase(v2_2);
                                            v2_3.getClass();
                                            if (v14_9.contains(v2_3)) {
                                            }
                                        }
                                    } else {
                                        v19 = v1_1;
                                        v16 = v2_8;
                                    }
                                } else {
                                    if (!v15_2.contains(v8_1)) {
                                    }
                                }
                            } else {
                                if (v14_2.contains(v8_1)) {
                                }
                            }
                        }
                        v16 = v2_8;
                        v22_1 = 0;
                        v10_1 = v16;
                    } else {
                        v1_41 = 0;
                        v16 = 0;
                    }
                } else {
                    return 0;
                }
            } else {
                v16 = 0;
            }
        }
        return v16;
    }

    public final boolean n(ei p2)
    {
        p2.getClass();
        return this.e.getBoolean("enabled:".concat(p2.a), 1);
    }

    public final void o(ei p4)
    {
        boolean v0_4 = new java.io.File(this.g, p4.a.concat(".json"));
        if (v0_4.isFile()) {
            try {
                org.json.JSONArray v1_2 = new org.json.JSONArray(xj.f0(v0_4));
            } catch (boolean v0_2) {
                v1_2 = new hy(v0_2);
            }
            if (!(v1_2 instanceof hy)) {
                this.s.put(p4.a, ((org.json.JSONArray) v1_2));
            }
        }
        return;
    }

    public final boolean p()
    {
        java.util.Iterator v0_1 = this.l.values();
        if ((v0_1 == null) || (!v0_1.isEmpty())) {
            java.util.Iterator v0_2 = v0_1.iterator();
            while (v0_2.hasNext()) {
                if (this.n(((ei) v0_2.next()))) {
                    return 1;
                }
            }
        }
        return 0;
    }

    public final void r()
    {
        java.util.List v0_1 = new java.util.ArrayList();
        java.util.ArrayList v1_4 = this.l.values().iterator();
        while(true) {
            org.json.JSONArray v3_0 = 0;
            if (!v1_4.hasNext()) {
                df v11_1 = this.i;
                v11_1.getClass();
                java.util.ArrayList v1_1 = new java.util.ArrayList();
                java.util.ArrayList v2_0 = v0_1.size();
                while (v3_0 < v2_0) {
                    String v4_0 = v0_1.get(v3_0);
                    v3_0++;
                    int v5_1 = ((bf) v4_0);
                    if ((!v5_1.i) && (v5_1.a() >= 0)) {
                        v1_1.add(v4_0);
                    }
                }
                v11_1.a = rb.o0(v1_1, new cf(new ed(2)));
                return;
            } else {
                java.util.ArrayList v2_5 = ((ei) v1_4.next());
                if (this.n(v2_5)) {
                    String v4_2 = this.h(v2_5);
                    int v5_3 = v2_5.o;
                    boolean v6_1 = v5_3.size();
                    while (v3_0 < v6_1) {
                    }
                    org.json.JSONArray v3_3 = ((org.json.JSONArray) this.s.get(v2_5.a));
                    if (v3_3 != null) {
                        v0_1.addAll(pg.o(v2_5.a, v3_3));
                    }
                    org.json.JSONArray v3_7 = ((org.json.JSONArray) this.t.get(v2_5.a));
                    if (v3_7 != null) {
                        v0_1.addAll(pg.o(v2_5.a, v3_7));
                    }
                }
            }
        }
        String v7_1 = v5_3.get(v3_0);
        v3_0++;
        String v7_2 = ((qy) v7_1);
        if (v4_2.contains(v7_2.a)) {
            Throwable v8_3 = v2_5.b.h(v7_2.b);
            if (v8_3 != null) {
                try {
                    v0_1.addAll(pg.o(v2_5.a, new org.json.JSONArray(v8_3)));
                    Throwable v8_5 = a50.a;
                } catch (Throwable v8_6) {
                    v8_5 = new hy(v8_6);
                }
                Throwable v8_7 = iy.a(v8_5);
                if (v8_7 != null) {
                    String v7_3 = v7_2.b;
                    StringBuilder v10_0 = new StringBuilder(v2_5.a);
                    v10_0.append(": invalid ruleset ");
                    v10_0.append(v7_3);
                    android.util.Log.w("ExtensionManager", v10_0.toString(), v8_7);
                }
            }
        }
    }

    public final void s()
    {
        this.r.clear();
        int v0_3 = this.n.values();
        v0_3.getClass();
        java.util.ArrayList v1_1 = new java.util.ArrayList();
        int v0_4 = v0_3.iterator();
        while (v0_4.hasNext()) {
            int v2_2 = v0_4.next();
            if ((((gi) v2_2).b instanceof mi)) {
                v1_1.add(v2_2);
            }
        }
        int v0_1 = v1_1.size();
        int v2_1 = 0;
        while (v2_1 < v0_1) {
            gi v3_0 = v1_1.get(v2_1);
            v2_1++;
            this.l(((gi) v3_0));
        }
        m8 v4_1 = this.a;
        if (v4_1 != null) {
            v4_1.a();
        }
        return;
    }

    public final android.webkit.WebResourceResponse v(android.net.Uri p25)
    {
        StringBuilder v2_33 = p25.getPathSegments();
        if (v2_33.size() >= 3) {
            String v3_1 = ((ei) this.l.get(v2_33.get(1)));
            if (v3_1 != null) {
                String v7_1 = rb.l0(rb.f0(v2_33, 2), "/", 0, 62);
                String v11_0 = "text/javascript";
                String v12 = "page";
                String v15 = "";
                if (!io.d(v2_33.get(2), "_instatool_")) {
                    String v0_51 = m10.M(v7_1, 46, "").toLowerCase(java.util.Locale.ROOT);
                    v0_51.getClass();
                    switch (v0_51.hashCode()) {
                        case 3401:
                            if (v0_51.equals("js")) {
                            } else {
                                v11_0 = "application/octet-stream";
                            }
                            break;
                        case 98819:
                            if (v0_51.equals("css")) {
                                v11_0 = "text/css";
                            } else {
                            }
                            break;
                        case 102340:
                            if (v0_51.equals("gif")) {
                                v11_0 = "image/gif";
                            } else {
                            }
                            break;
                        case 103649:
                            if (v0_51.equals("htm")) {
                                v11_0 = "text/html";
                            } else {
                            }
                            break;
                        case 104085:
                            if (v0_51.equals("ico")) {
                                v11_0 = "image/x-icon";
                            } else {
                            }
                            break;
                        case 105441:
                            if (v0_51.equals("jpg")) {
                                v11_0 = "image/jpeg";
                            } else {
                            }
                            break;
                        case 107868:
                            if (v0_51.equals("map")) {
                                v11_0 = "application/json";
                            } else {
                            }
                            break;
                        case 108150:
                            if (v0_51.equals("mjs")) {
                            } else {
                            }
                            break;
                        case 108272:
                            if (v0_51.equals("mp3")) {
                                v11_0 = "audio/mpeg";
                            } else {
                            }
                            break;
                        case 108273:
                            if (v0_51.equals("mp4")) {
                                v11_0 = "video/mp4";
                            } else {
                            }
                            break;
                        case 109967:
                            if (v0_51.equals("ogg")) {
                                v11_0 = "audio/ogg";
                            } else {
                            }
                            break;
                        case 110369:
                            if (v0_51.equals("otf")) {
                                v11_0 = "font/otf";
                            } else {
                            }
                            break;
                        case 111145:
                            if (v0_51.equals("png")) {
                                v11_0 = "image/png";
                            } else {
                            }
                            break;
                        case 114276:
                            if (v0_51.equals("svg")) {
                                v11_0 = "image/svg+xml";
                            } else {
                            }
                            break;
                        case 115174:
                            if (v0_51.equals("ttf")) {
                                v11_0 = "font/ttf";
                            } else {
                            }
                            break;
                        case 115312:
                            if (v0_51.equals("txt")) {
                                v11_0 = "text/plain";
                            } else {
                            }
                            break;
                        case 117484:
                            if (v0_51.equals("wav")) {
                                v11_0 = "audio/wav";
                            } else {
                            }
                            break;
                        case 118807:
                            if (v0_51.equals("xml")) {
                                v11_0 = "application/xml";
                            } else {
                            }
                            break;
                        case 3213227:
                            if (v0_51.equals("html")) {
                            } else {
                            }
                            break;
                        case 3268712:
                            if (v0_51.equals("jpeg")) {
                            } else {
                            }
                            break;
                        case 3271912:
                            if (v0_51.equals("json")) {
                            } else {
                            }
                            break;
                        case 3642020:
                            if (v0_51.equals("wasm")) {
                                v11_0 = "application/wasm";
                            } else {
                            }
                            break;
                        case 3645337:
                            if (v0_51.equals("webm")) {
                                v11_0 = "video/webm";
                            } else {
                            }
                            break;
                        case 3645340:
                            if (v0_51.equals("webp")) {
                                v11_0 = "image/webp";
                            } else {
                            }
                            break;
                        case 3655064:
                            if (v0_51.equals("woff")) {
                                v11_0 = "font/woff";
                            } else {
                            }
                            break;
                        case 113307034:
                            if (v0_51.equals("woff2")) {
                                v11_0 = "font/woff2";
                            } else {
                            }
                            break;
                        default:
                    }
                    StringBuilder v2_15 = v3_1.b;
                    if (!v11_0.equals("text/html")) {
                        java.io.InputStream v23 = v2_15.d(v7_1);
                        if (v23 != null) {
                            if ((!v11_0.startsWith("text/")) && ((!v11_0.endsWith("json")) && (!v11_0.endsWith("javascript")))) {
                                String v19 = 0;
                            } else {
                                v19 = "utf-8";
                            }
                            return new android.webkit.WebResourceResponse(v11_0, v19, 200, "OK", ri.e(), v23);
                        } else {
                            return ri.q();
                        }
                    } else {
                        String v0_23 = v2_15.h(v7_1);
                        if (v0_23 != null) {
                            if (io.d(p25.getQueryParameter("__instatool_ctx"), "background")) {
                                v12 = "background";
                            }
                            String v1_3 = v3_1.i;
                            StringBuilder v2_18 = new StringBuilder("<script src=\"");
                            v2_18.append(v1_3);
                            v2_18.append("_instatool_/api.js?context=");
                            v2_18.append(v12);
                            v2_18.append("\"></script>");
                            String v1_5 = v2_18.toString();
                            StringBuilder v2_19 = px.IGNORE_CASE;
                            v2_19.getClass();
                            String v3_2 = v2_19.getValue();
                            if ((v3_2 & 2) != 0) {
                                v3_2 |= 64;
                            }
                            String v0_24;
                            String v3_3 = java.util.regex.Pattern.compile("<head[^>]*>", v3_2);
                            v3_3.getClass();
                            String v3_4 = v3_3.matcher(v0_23);
                            v3_4.getClass();
                            String v3_5 = io.o(v3_4, 0, v0_23);
                            if (v3_5 == null) {
                                StringBuilder v2_20 = v2_19.getValue();
                                if ((v2_20 & 2) != 0) {
                                    v2_20 |= 64;
                                }
                                StringBuilder v2_21 = java.util.regex.Pattern.compile("<html[^>]*>", v2_20);
                                v2_21.getClass();
                                StringBuilder v2_22 = v2_21.matcher(v0_23);
                                v2_22.getClass();
                                StringBuilder v2_23 = io.o(v2_22, 0, v0_23);
                                if (v2_23 == null) {
                                    v0_24 = v1_5.concat(v0_23);
                                } else {
                                    String v3_11 = v0_23.substring(0, (v2_23.b().b + 1));
                                    String v0_25 = v0_23.substring((v2_23.b().b + 1));
                                    StringBuilder v2_28 = new StringBuilder(v3_11);
                                    v2_28.append("<head>");
                                    v2_28.append(v1_5);
                                    v2_28.append("</head>");
                                    v2_28.append(v0_25);
                                    v0_24 = v2_28.toString();
                                }
                            } else {
                                v0_24 = g.e(v0_23.substring(0, (v3_5.b().b + 1)), v1_5, v0_23.substring((v3_5.b().b + 1)));
                            }
                            String v0_27 = v0_24.getBytes(ka.a);
                            v0_27.getClass();
                            return ri.u(v11_0, v0_27);
                        } else {
                            return ri.q();
                        }
                    }
                } else {
                    StringBuilder v2_35 = rb.l0(rb.f0(v2_33, 3), "/", 0, 62);
                    if (!v2_35.equals("background.html")) {
                        if (!v2_35.equals("api.js")) {
                            return ri.q();
                        } else {
                            if (io.d(p25.getQueryParameter("context"), "background")) {
                                v12 = "background";
                            }
                            String v0_33 = ((String) this.x.a());
                            String v1_10 = ri.b(v3_1, v12, 0);
                            StringBuilder v2_39 = new StringBuilder("(");
                            v2_39.append(v0_33);
                            v2_39.append(")(");
                            v2_39.append(v1_10);
                            v2_39.append(");");
                            String v0_37 = v2_39.toString().getBytes(ka.a);
                            v0_37.getClass();
                            return ri.u("text/javascript", v0_37);
                        }
                    } else {
                        String v0_39 = v3_1.k;
                        String v1_12 = v3_1.i;
                        if (v0_39 != null) {
                            if (v0_39.c) {
                                v15 = " type=\"module\"";
                            }
                            StringBuilder v2_42 = new StringBuilder("<!doctype html><html><head><meta charset=\"utf-8\">");
                            String v3_19 = new StringBuilder("<script src=\"");
                            v3_19.append(v1_12);
                            v3_19.append("_instatool_/api.js?context=background\"></script>");
                            v2_42.append(v3_19.toString());
                            String v0_41 = v0_39.a.iterator();
                            while (v0_41.hasNext()) {
                                String v3_24 = m10.J(((String) v0_41.next()), "/");
                                String v4_8 = new StringBuilder("<script");
                                v4_8.append(v15);
                                v4_8.append(" src=\"");
                                v4_8.append(v1_12);
                                v4_8.append(v3_24);
                                v4_8.append("\"></script>");
                                v2_42.append(v4_8.toString());
                            }
                            v2_42.append("</head><body></body></html>");
                            String v0_44 = v2_42.toString().getBytes(ka.a);
                            v0_44.getClass();
                            return ri.u("text/html", v0_44);
                        } else {
                            return ri.q();
                        }
                    }
                }
            } else {
                return ri.q();
            }
        } else {
            return ri.q();
        }
    }

    public final void w(ei p5)
    {
        String v1 = p5.a;
        if (p5.k != null) {
            java.util.HashMap v0_1 = this.m;
            if (!v0_1.containsKey(v1)) {
                android.content.Context v3 = this.b;
                v3.getClass();
                u6 v2_0 = new u6(v3, this, p5);
                v0_1.put(v1, v2_0);
                v2_0.d();
            }
        }
        return;
    }

    public final void x(String p1)
    {
        u6 v0_3 = ((u6) this.m.remove(p1));
        if (v0_3 != null) {
            v0_3.e();
        }
        return;
    }

    public final Integer y(org.json.JSONObject p3)
    {
        if ((!p3.has("tabId")) || (p3.isNull("tabId"))) {
            Integer v2_1 = this.a().iterator();
            while (v2_1.hasNext()) {
                oi v3_2 = v2_1.next();
                if (((oi) v3_2).e) {
                }
                oi v3_3 = ((oi) v3_2);
                if (v3_3 == null) {
                    return 0;
                } else {
                    return Integer.valueOf(v3_3.a);
                }
            }
            v3_2 = 0;
        } else {
            return Integer.valueOf(p3.optInt("tabId"));
        }
    }

    public final String z(String p7)
    {
        String v7_2 = p7.toLowerCase(java.util.Locale.ROOT);
        v7_2.getClass();
        String v0_3 = java.util.regex.Pattern.compile("[^a-z0-9]+");
        v0_3.getClass();
        String v7_1 = v0_3.matcher(v7_2).replaceAll("-");
        v7_1.getClass();
        int v1_1 = new char[1];
        v1_1[0] = 45;
        String v7_4 = m10.O(40, m10.Q(v7_1, v1_1));
        if (v7_4.length() == 0) {
            v7_4 = "extension";
        }
        int v1_4 = 2;
        String v2_1 = v7_4;
        while ((this.l.containsKey(v2_1)) || ((new java.io.File(this.f, v2_1).exists()) || (v2_1.equals("_instatool_")))) {
            String v2_2 = (v1_4 + 1);
            boolean v3_9 = new StringBuilder(v7_4);
            v3_9.append("-");
            v3_9.append(v1_4);
            v2_1 = v3_9.toString();
            v1_4 = v2_2;
        }
        return v2_1;
    }
}
