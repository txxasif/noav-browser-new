public final synthetic class Le8 implements android.os.Handler$Callback {
    public final synthetic com.example.instatool.browser.BrowserActivity a;
    public final synthetic p9 b;
    public final synthetic String c;

    public synthetic e8(com.example.instatool.browser.BrowserActivity p1, p9 p2, String p3)
    {
        this.a = p1;
        this.b = p2;
        this.c = p3;
        return;
    }

    public final boolean handleMessage(android.os.Message p3)
    {
        Class vtmp1 = p3.getClass();
        this.a.e0(this.b, p3.getData().getString("url"), this.c);
        return 1;
    }
}
