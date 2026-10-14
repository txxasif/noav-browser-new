public final class Lp9 {
    public static final java.util.Set t;
    public final int a;
    public final com.example.instatool.browser.BrowserActivity b;
    public final boolean c;
    public Integer d;
    public final ri e;
    public final k9 f;
    public final jj g;
    public final com.example.instatool.browser.BrowserActivity h;
    public android.webkit.WebView i;
    public String j;
    public String k;
    public android.graphics.Bitmap l;
    public int m;
    public boolean n;
    public uu o;
    public boolean p;
    public android.graphics.Bitmap q;
    public String r;
    public boolean s;

    static p9()
    {
        String v2 = "about";
        String v4 = "blob";
        p9.t = jy.p(new String[] {"http", "file"}));
        return;
    }

    public p9(int p1, com.example.instatool.browser.BrowserActivity p2, boolean p3, Integer p4, boolean p5, ri p6, k9 p7, jj p8, com.example.instatool.browser.BrowserActivity p9)
    {
        this.a = p1;
        this.b = p2;
        this.c = p3;
        this.d = p4;
        this.e = p6;
        this.f = p7;
        this.g = p8;
        this.h = p9;
        this.i = this.b();
        this.j = "";
        this.k = "";
        this.m = 100;
        this.p = p5;
        return;
    }

    public final void a(android.webkit.WebView p3)
    {
        String v0_2;
        android.webkit.WebSettings v3_1 = p3.getSettings();
        String v2_4 = this.b;
        if (!this.p) {
            String v2_10 = android.webkit.WebSettings.getDefaultUserAgent(v2_4);
            v2_10.getClass();
            String v2_1 = u10.y(v2_10, "; wv", "");
            String v0_1 = java.util.regex.Pattern.compile("Version/[\\d.]+\\s*");
            v0_1.getClass();
            v0_2 = v0_1.matcher(v2_1).replaceAll("");
            v0_2.getClass();
        } else {
            v0_2 = jy.c;
            if (v0_2 == null) {
                String v2_9;
                String v2_3 = android.webkit.WebSettings.getDefaultUserAgent(v2_4);
                String v0_5 = java.util.regex.Pattern.compile("Chrome/(\\d+)");
                v0_5.getClass();
                v2_3.getClass();
                String v0_6 = v0_5.matcher(v2_3);
                v0_6.getClass();
                String v2_5 = io.o(v0_6, 0, v2_3);
                if (v2_5 == null) {
                    v2_9 = "130";
                } else {
                    v2_9 = ((String) ((pr) v2_5.a()).get(1));
                    if (v2_9 == null) {
                    }
                }
                v0_2 = g.e("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/", v2_9, ".0.0.0 Safari/537.36");
                jy.c = v0_2;
            }
        }
        v3_1.setUserAgentString(v0_2);
        return;
    }

    public final android.webkit.WebView b()
    {
        android.webkit.WebView v0_1 = new android.webkit.WebView(this.b);
        boolean v2 = this.c;
        if (v2) {
            if (!en.c()) {
                v0_1.getSettings().setCacheMode(2);
            } else {
                if (!s70.e.b()) {
                    throw s70.a();
                } else {
                    p70.c(v0_1).a.setProfile("instatool_incognito");
                }
            }
        }
        gi v3_10;
        v0_1.setLayoutParams(new android.view.ViewGroup$LayoutParams(-1, -1));
        gi v3_7 = v0_1.getSettings();
        v3_7.setJavaScriptEnabled(1);
        v3_7.setDomStorageEnabled(1);
        v3_7.setSupportZoom(1);
        v3_7.setBuiltInZoomControls(1);
        v3_7.setDisplayZoomControls(0);
        v3_7.setUseWideViewPort(1);
        v3_7.setLoadWithOverviewMode(1);
        v3_7.setSupportMultipleWindows(1);
        v3_7.setJavaScriptCanOpenWindowsAutomatically(0);
        v3_7.setMediaPlaybackRequiresUserGesture(1);
        v3_7.setAllowFileAccess(1);
        v3_7.setAllowContentAccess(1);
        v3_7.setMixedContentMode(2);
        this.a(v0_1);
        ri v1_2 = en.a(v2);
        v1_2.setAcceptCookie(1);
        v1_2.setAcceptThirdPartyCookies(v0_1, 1);
        ri v1_3 = this.e;
        gi v3_8 = v1_3.p();
        this.s = v3_8;
        if (v3_8 == null) {
            v3_10 = new r6(this, 1);
        } else {
            v3_10 = new o9(this);
        }
        v0_1.setWebViewClient(v3_10);
        v0_1.setWebChromeClient(new t6(this, 1));
        v0_1.setDownloadListener(new l9(this));
        v0_1.setOnLongClickListener(new m9(v0_1, this, 0));
        gi v3_20 = new gi(v0_1, new mi(this.a, v2));
        v1_3.c(v3_20);
        v1_3.l(v3_20);
        return v0_1;
    }

    public final String c()
    {
        if (!vm.a(this.j)) {
            ox v0_2 = this.k;
            if (!m10.G(v0_2)) {
                return v0_2;
            } else {
                return d50.a(this.j);
            }
        } else {
            return "";
        }
    }

    public final boolean d(String p1)
    {
        if (((this.c) || ((p1 == null) || ((!p1.startsWith("http://")) && (!p1.startsWith("https://"))))) || (vm.a(p1))) {
            return 0;
        } else {
            return 1;
        }
    }

    public final void e(String p9)
    {
        p9.getClass();
        this.r = 0;
        com.example.instatool.browser.BrowserActivity v1 = this.h;
        if (!v1.I(this, p9)) {
            this.o = 0;
            this.j = p9;
            if (!this.c) {
                android.webkit.CookieManager.getInstance().flush();
            }
            android.webkit.WebView v2_0 = this.i;
            if (!vm.a(p9)) {
                v2_0.loadUrl(p9);
            } else {
                v2_0.getClass();
                byte[] v9_1 = vm.a;
                v9_1.getClass();
                v2_0.loadDataWithBaseURL("https://appassets.androidplatform.net/instatool/home", new String(v9_1, ka.a), "text/html", "utf-8", "https://appassets.androidplatform.net/instatool/home");
            }
            v1.J(this);
            return;
        } else {
            return;
        }
    }

    public final void f(android.webkit.WebView p2)
    {
        int v1_3;
        p2.getClass();
        this.e.f(p2);
        int v1_2 = p2.getParent();
        if (!(v1_2 instanceof android.view.ViewGroup)) {
            v1_3 = 0;
        } else {
            v1_3 = ((android.view.ViewGroup) v1_2);
        }
        if (v1_3 != 0) {
            v1_3.removeView(p2);
        }
        p2.stopLoading();
        p2.destroy();
        return;
    }

    public final void g()
    {
        android.webkit.WebView v0_0 = this.o;
        if (v0_0 != null) {
            this.o = 0;
            if (v0_0.b == -1000) {
                this.i.loadUrl(v0_0.a);
            } else {
                int v1_5 = this.i.getUrl();
                if ((v1_5 != 0) && (v1_5.length() != 0)) {
                    this.i.reload();
                }
            }
            this.h.J(this);
            return;
        } else {
            return;
        }
    }

    public final oi h(int p9, boolean p10)
    {
        return new oi(this.a, p9, this.j, this.c(), p10, this.c, this.n);
    }
}
