public final synthetic class Li00 implements android.view.View$OnClickListener {
    public final synthetic com.example.instatool.databinding.DialogSheetConfigBinding a;
    public final synthetic java.util.concurrent.Executor b;
    public final synthetic com.example.instatool.browser.BrowserActivity c;
    public final synthetic pm d;
    public final synthetic j2 e;
    public final synthetic String f;

    public synthetic i00(com.example.instatool.databinding.DialogSheetConfigBinding p1, java.util.concurrent.Executor p2, com.example.instatool.browser.BrowserActivity p3, pm p4, j2 p5, String p6)
    {
        this.a = p1;
        this.b = p2;
        this.c = p3;
        this.d = p4;
        this.e = p5;
        this.f = p6;
        return;
    }

    public final void onClick(android.view.View p8)
    {
        com.example.instatool.databinding.DialogSheetConfigBinding v5 = this.a;
        com.example.instatool.browser.BrowserActivity v1 = this.c;
        String v3 = hz.x(v5, v1);
        if (v3 != null) {
            v5.validateSheet.setEnabled(0);
            v5.sheetStatus.setText(2131689910);
            this.b.execute(new vn(v1, this.d, v3, this.e, v5, this.f));
            return;
        } else {
            return;
        }
    }
}
