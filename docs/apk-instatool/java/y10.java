public final class Ly10 extends android.widget.BaseAdapter implements android.widget.Filterable {
    public final k9 a;
    public final android.view.LayoutInflater b;
    public java.util.List c;

    public y10(com.example.instatool.browser.BrowserActivity p1, k9 p2)
    {
        this.a = p2;
        this.b = android.view.LayoutInflater.from(p1);
        this.c = qh.a;
        return;
    }

    public final int getCount()
    {
        return this.c.size();
    }

    public final android.widget.Filter getFilter()
    {
        return new x10(this);
    }

    public final Object getItem(int p1)
    {
        return ((w10) this.c.get(p1));
    }

    public final long getItemId(int p1)
    {
        return ((long) p1);
    }

    public final android.view.View getView(int p3, android.view.View p4, android.view.ViewGroup p5)
    {
        String v4_4;
        p5.getClass();
        com.example.instatool.databinding.ItemSuggestionBinding v0_0 = 0;
        if (p4 == null) {
            v4_4 = 0;
        } else {
            v4_4 = p4.getTag();
        }
        if ((v4_4 instanceof com.example.instatool.databinding.ItemSuggestionBinding)) {
            v0_0 = ((com.example.instatool.databinding.ItemSuggestionBinding) v4_4);
        }
        if (v0_0 == null) {
            v0_0 = com.example.instatool.databinding.ItemSuggestionBinding.inflate(this.b, p5, 0);
            v0_0.getRoot().setTag(v0_0);
        }
        android.widget.LinearLayout v2_3 = ((w10) this.c.get(p3));
        String v4_3 = v2_3.b;
        String v5_1 = v2_3.a;
        if (m10.G(v4_3)) {
            v4_3 = v5_1;
        }
        android.widget.LinearLayout v2_5;
        v0_0.title.setText(v4_3);
        v0_0.url.setText(v5_1);
        if (!v2_3.c) {
            v2_5 = 2131165344;
        } else {
            v2_5 = 2131165373;
        }
        v0_0.icon.setImageResource(v2_5);
        android.widget.LinearLayout v2_6 = v0_0.getRoot();
        v2_6.getClass();
        return v2_6;
    }
}
