public final synthetic class Lo8 implements android.view.View$OnFocusChangeListener {
    public final synthetic android.widget.AutoCompleteTextView a;
    public final synthetic com.example.instatool.browser.BrowserActivity b;

    public synthetic o8(android.widget.AutoCompleteTextView p1, com.example.instatool.browser.BrowserActivity p2)
    {
        this.a = p1;
        this.b = p2;
        return;
    }

    public final void onFocusChange(android.view.View p3, boolean p4)
    {
        p3 = this.a;
        com.example.instatool.browser.BrowserActivity v2_1 = this.b;
        if (p4 == 0) {
            p3.dismissDropDown();
        } else {
            int v4_5 = ((p9) v2_1.C.c);
            int v0 = 0;
            if (v4_5 != 0) {
                int v4_1 = v4_5.j;
                if ((v4_1 != 0) && (!vm.a(v4_1))) {
                    v0 = v4_1;
                }
            }
            if (v0 == 0) {
                v0 = "";
            }
            p3.setText(v0, 0);
            p3.selectAll();
        }
        v2_1.R();
        v2_1.X();
        return;
    }
}
