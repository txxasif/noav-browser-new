public final synthetic class Le9 implements android.webkit.WebView$FindListener {
    public final synthetic com.example.instatool.browser.BrowserActivity a;

    public synthetic e9(com.example.instatool.browser.BrowserActivity p1)
    {
        this.a = p1;
        return;
    }

    public final void onFindResultReceived(int p1, int p2, boolean p3)
    {
        int v0_2 = this.a.y;
        if (v0_2 == 0) {
            io.T("binding");
            throw 0;
        } else {
            String v1_2;
            int v0_5 = v0_2.findCount;
            if (p2 != 0) {
                String v1_3 = (p1 + 1);
                StringBuilder v3_1 = new StringBuilder();
                v3_1.append(v1_3);
                v3_1.append("/");
                v3_1.append(p2);
                v1_2 = v3_1.toString();
            } else {
                v1_2 = "0/0";
            }
            v0_5.setText(v1_2);
            return;
        }
    }
}
