public final synthetic class Lv8 implements android.view.View$OnClickListener {
    public final synthetic byte a;
    public final synthetic String b;
    public final synthetic com.example.instatool.browser.BrowserActivity c;

    public synthetic v8(byte p1, com.example.instatool.browser.BrowserActivity p2, String p3)
    {
        this.a = p1;
        this.b = p3;
        this.c = p2;
        return;
    }

    public final void onClick(android.view.View p3)
    {
        com.example.instatool.browser.BrowserActivity v1 = this.c;
        android.net.Uri v2_2 = this.b;
        switch (this.a) {
            case 0:
                try {
                    if (v2_2 != null) {
                        v1.startActivity(new android.content.Intent("android.intent.action.VIEW", android.net.Uri.parse(v2_2)));
                    }
                } catch (Throwable) {
                }
                return;
            default:
                if (v2_2 != null) {
                    v1.startActivity(new android.content.Intent("android.intent.action.VIEW", android.net.Uri.parse(v2_2)));
                }
                return;
        }
    }
}
