public final synthetic class Lw8 implements ll {
    public final synthetic byte a;
    public final synthetic com.example.instatool.browser.BrowserActivity b;
    public final synthetic String c;

    public synthetic w8(byte p1, com.example.instatool.browser.BrowserActivity p2, String p3)
    {
        this.a = p1;
        this.b = p2;
        this.c = p3;
        return;
    }

    public final Object a()
    {
        String v1 = this.c;
        com.example.instatool.browser.BrowserActivity v2 = this.b;
        a50 v3 = a50.a;
        switch (this.a) {
            case 0:
                com.example.instatool.browser.BrowserActivity.O(this.b, this.c, 1, 0, 0, 12);
                return v3;
            case 1:
                v2.v(v1);
                return v3;
            case 2:
                v2.c0(v1, "");
                return v3;
            default:
                v2.v(v1);
                return v3;
        }
    }
}
