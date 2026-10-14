public final synthetic class Ln8 implements android.widget.AdapterView$OnItemClickListener {
    public final synthetic com.example.instatool.browser.BrowserActivity a;

    public synthetic n8(com.example.instatool.browser.BrowserActivity p1)
    {
        this.a = p1;
        return;
    }

    public final void onItemClick(android.widget.AdapterView p1, android.view.View p2, int p3, long p4)
    {
        String v1_2;
        String v1_1 = p1.getItemAtPosition(p3);
        if (!(v1_1 instanceof w10)) {
            v1_2 = 0;
        } else {
            v1_2 = ((w10) v1_1);
        }
        if (v1_2 != null) {
            this.a.G(v1_2.a);
        }
        return;
    }
}
