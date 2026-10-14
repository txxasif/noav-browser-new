public final synthetic class Lh8 implements android.widget.TextView$OnEditorActionListener {
    public final synthetic byte a;
    public final synthetic com.example.instatool.browser.BrowserActivity b;

    public synthetic h8(com.example.instatool.browser.BrowserActivity p1, byte p2)
    {
        this.a = p2;
        this.b = p1;
        return;
    }

    public final boolean onEditorAction(android.widget.TextView p5, int p6, android.view.KeyEvent p7)
    {
        int v1 = 1;
        android.webkit.WebView v4_4 = this.b;
        switch (this.a) {
            case 0:
                if (p6 != 3) {
                    v1 = 0;
                } else {
                    android.webkit.WebView v4_2 = ((p9) v4_4.C.c);
                    if (v4_2 != null) {
                        android.webkit.WebView v4_3 = v4_2.i;
                        if (v4_3 != null) {
                            v4_3.findNext(1);
                        }
                    }
                }
                return v1;
            default:
                int v7_2;
                if (p7 == 0) {
                    v7_2 = 0;
                    if ((p6 != 2) && (v7_2 == 0)) {
                        v1 = 0;
                    } else {
                        v4_4.G(p5.getText().toString());
                    }
                    return v1;
                } else {
                    if ((p7.getKeyCode() != 66) || (p7.getAction() != 0)) {
                    } else {
                        v7_2 = 1;
                    }
                }
        }
    }
}
