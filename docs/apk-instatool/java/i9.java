public final class Li9 implements android.text.TextWatcher {
    public final synthetic byte a;
    public final synthetic com.example.instatool.browser.BrowserActivity b;

    public synthetic i9(com.example.instatool.browser.BrowserActivity p1, byte p2)
    {
        this.a = p2;
        this.b = p1;
        return;
    }

    private final void a(int p1, int p2, int p3, CharSequence p4)
    {
        return;
    }

    private final void b(int p1, int p2, int p3, CharSequence p4)
    {
        return;
    }

    private final void c(int p1, int p2, int p3, CharSequence p4)
    {
        return;
    }

    private final void d(int p1, int p2, int p3, CharSequence p4)
    {
        return;
    }

    public final void afterTextChanged(android.text.Editable p5)
    {
        String v4_1 = this.b;
        switch (this.a) {
            case 0:
                v4_1.S();
                return;
            default:
                android.webkit.WebView v0_4 = ((p9) v4_1.C.c);
                if (v0_4 != null) {
                    android.webkit.WebView v0_1 = v0_4.i;
                    if (v0_1 != null) {
                        String v5_1;
                        if (p5 == null) {
                            v5_1 = 0;
                        } else {
                            v5_1 = p5.toString();
                        }
                        if (v5_1 == null) {
                            v5_1 = "";
                        }
                        if (v5_1.length() != 0) {
                            v0_1.findAllAsync(v5_1);
                        } else {
                            v0_1.clearMatches();
                            String v4_2 = v4_1.y;
                            if (v4_2 == null) {
                                io.T("binding");
                                throw 0;
                            } else {
                                v4_2.findCount.setText("");
                            }
                        }
                    }
                }
                return;
        }
    }

    public final void beforeTextChanged(CharSequence p1, int p2, int p3, int p4)
    {
        return;
    }

    public final void onTextChanged(CharSequence p1, int p2, int p3, int p4)
    {
        return;
    }
}
