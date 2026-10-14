public final synthetic class Lap implements wl, am, hu, q30 {
    public final synthetic byte a;
    public final synthetic com.example.instatool.library.LibraryActivity b;

    public synthetic ap(com.example.instatool.library.LibraryActivity p1, byte p2)
    {
        this.a = p2;
        this.b = p1;
        return;
    }

    public Object c(Object p2, Object p3)
    {
        Class vtmp1 = ((String) p2).getClass();
        ((String) p3).getClass();
        if ((!((String) p3).startsWith("http://")) && (!((String) p3).startsWith("https://"))) {
            return this.b.getString(2131689712);
        } else {
            return 0;
        }
    }

    public Object d(Object p23)
    {
        long v3_4 = 0;
        String v5_22 = 4;
        Long v7_2 = 1;
        Long v9_1 = a50.a;
        Throwable v0_12 = this.b;
        switch (this.a) {
            case 0:
                Class vtmp5 = ((java.util.List) p23).getClass();
                int v10_1 = new java.util.ArrayList(tb.e0(((java.util.List) p23)));
                m40 v11_1 = ((java.util.List) p23).iterator();
                while (v11_1.hasNext()) {
                    Long v7_0;
                    StringBuilder v23_1;
                    String v5_2;
                    android.app.DownloadManager$Query v22_1;
                    Integer v12_2 = ((ef) v11_1.next());
                    Long v13_0 = v12_2.b;
                    Long v14_0 = v12_2.c;
                    long v20_0 = v3_4;
                    long v3_3 = v12_2.a;
                    um v4_2 = v9_1;
                    int v8_0 = v12_2.d;
                    if (v13_0 == -1) {
                        v22_1 = -1;
                        v23_1 = v10_1;
                        v7_0 = v11_1;
                        v5_2 = v0_12.getString(2131689936);
                        v5_2.getClass();
                    } else {
                        if (v13_0 == v5_22) {
                            v22_1 = -1;
                            v23_1 = v10_1;
                            v7_0 = v11_1;
                            v5_2 = v0_12.getString(2131689934);
                            v5_2.getClass();
                        } else {
                            if (v13_0 == 16) {
                                v22_1 = -1;
                                v23_1 = v10_1;
                                v7_0 = v11_1;
                                v5_2 = v0_12.getString(2131689933);
                                v5_2.getClass();
                            } else {
                                if (v13_0 == v7_2) {
                                    v22_1 = -1;
                                    v23_1 = v10_1;
                                    v7_0 = v11_1;
                                    v5_2 = v0_12.getString(2131689935);
                                    v5_2.getClass();
                                } else {
                                    if (v13_0 == 2) {
                                        v22_1 = -1;
                                        v23_1 = v10_1;
                                        v7_0 = v11_1;
                                        if (v8_0 <= v20_0) {
                                            int v10_2;
                                            String v5_9 = v0_12.getString(2131689937);
                                            if (v14_0 >= v20_0) {
                                                v10_2 = v14_0;
                                            } else {
                                                v10_2 = v20_0;
                                            }
                                            int v6_4 = android.text.format.Formatter.formatShortFileSize(v0_12, v10_2);
                                            int v10_4 = new StringBuilder();
                                            v10_4.append(v5_9);
                                            v10_4.append(" \u00b7 ");
                                            v10_4.append(v6_4);
                                            v5_2 = v10_4.toString();
                                        } else {
                                            String v5_10 = v0_12.getString(2131689937);
                                            int v6_5 = android.text.format.Formatter.formatShortFileSize(v0_12, v14_0);
                                            m40 v11_2 = android.text.format.Formatter.formatShortFileSize(v0_12, v8_0);
                                            Long v13_2 = new StringBuilder();
                                            v13_2.append(v5_10);
                                            v13_2.append(" \u00b7 ");
                                            v13_2.append(v6_5);
                                            v13_2.append(" / ");
                                            v13_2.append(v11_2);
                                            v5_2 = v13_2.toString();
                                        }
                                    } else {
                                        String v5_13 = v0_12.getString(2131689932);
                                        Long v13_3 = Long.valueOf(v8_0);
                                        if (v8_0 <= v20_0) {
                                            v13_3 = 0;
                                        }
                                        int v6_6;
                                        v22_1 = -1;
                                        if (v13_3 == null) {
                                            v6_6 = 0;
                                        } else {
                                            v6_6 = android.text.format.Formatter.formatShortFileSize(v0_12, v13_3.longValue());
                                        }
                                        v23_1 = v10_1;
                                        v7_0 = v11_1;
                                        v5_2 = rb.l0(f6.m0(new String[] {v5_13, v6_6, android.text.format.DateUtils.getRelativeTimeSpanString(v3_3.g).toString()})), " \u00b7 ", 0, 62);
                                    }
                                }
                            }
                        }
                    }
                    long v18_0;
                    String v5_18;
                    long v16_1 = v5_2;
                    String v5_17 = v12_2.b;
                    if (v5_17 == 1) {
                        v5_18 = Integer.valueOf(v22_1);
                        v18_0 = v5_18;
                    } else {
                        if (v5_17 == 2) {
                            int v6_11;
                            if (v8_0 <= v20_0) {
                                v6_11 = v22_1;
                            } else {
                                v6_11 = ((int) ((v14_0 * 100) / v8_0));
                            }
                            v5_18 = Integer.valueOf(v6_11);
                        } else {
                            v18_0 = 0;
                        }
                    }
                    String v5_21 = v3_3.a;
                    int v8_3 = new StringBuilder("d");
                    v8_3.append(v5_21);
                    long v3_5 = v23_1;
                    v3_5.add(new ip(v8_3.toString(), v3_3.d, v16_1, 2131165343, v18_0, v12_2));
                    v10_1 = v3_5;
                    v9_1 = v4_2;
                    v11_1 = v7_0;
                    v3_4 = v20_0;
                    v5_22 = 4;
                    v7_2 = 1;
                }
                um v4_0 = v9_1;
                v0_12.r(v10_1);
                if (!((java.util.List) p23).isEmpty()) {
                    Throwable v1_14 = ((java.util.List) p23).iterator();
                    while (v1_14.hasNext()) {
                        long v2_4 = ((ef) v1_14.next()).b;
                        if ((v2_4 == 2) || (v2_4 == 1)) {
                            if (!v0_12.E) {
                                break;
                            }
                            v0_12.B.postDelayed(v0_12.C, 1000);
                            break;
                        }
                    }
                }
                return v4_0;
            case 1:
                Class vtmp8 = ((a50) p23).getClass();
                v0_12.q();
                return v9_1;
            case 2:
            case 7:
            case 8:
            default:
                Class vtmp1 = ((k9) p23).getClass();
                Integer v12 = "url";
                Long v14 = "mime_type";
                Throwable v1_20 = ((k9) p23).getReadableDatabase().query("downloads", new String[] {"id", "created"}), 0, 0, 0, 0, "created DESC");
                try {
                    v1_20.getClass();
                    long v2_8 = new java.util.ArrayList(v1_20.getCount());
                } catch (Throwable v0_10) {
                    long v2_9 = v0_10;
                    try {
                        throw v2_9;
                    } catch (Throwable v0_11) {
                        c8.i(v1_20, v2_9);
                        throw v0_11;
                    }
                }
                while(true) {
                    int v10_12 = 0;
                    if (!v1_20.moveToNext()) {
                        break;
                    }
                    long v18_1;
                    Integer v12_10 = v1_20.getLong(0);
                    Long v14_10 = v1_20.getLong(1);
                    long v16_7 = v1_20.getString(2);
                    v16_7.getClass();
                    int v17_1 = v1_20.getString(3);
                    v17_1.getClass();
                    if (!v1_20.isNull(4)) {
                        v18_1 = v1_20.getString(4);
                    } else {
                        v18_1 = 0;
                    }
                    String v19_1;
                    if (!v1_20.isNull(5)) {
                        v19_1 = v1_20.getString(5);
                    } else {
                        v19_1 = 0;
                    }
                    v2_8.add(new ff(v12_10, v14_10, v16_7, v17_1, v18_1, v19_1, v1_20.getLong(6)));
                }
                v1_20.close();
                Throwable v0_3 = ((android.app.DownloadManager) v0_12.getSystemService(android.app.DownloadManager));
                Throwable v1_23 = new java.util.ArrayList();
                String v5_24 = v2_8.size();
                int v6_12 = 0;
                while (v6_12 < v5_24) {
                    Long v7_11 = v2_8.get(v6_12);
                    v6_12++;
                    if (((ff) v7_11).b > 0) {
                        v1_23.add(v7_11);
                    }
                }
                String v5_26 = new java.util.ArrayList(tb.e0(v1_23));
                int v6_14 = v1_23.size();
                Long v7_3 = 0;
                while (v7_3 < v6_14) {
                    int v8_9 = v1_23.get(v7_3);
                    v7_3++;
                    v5_26.add(Long.valueOf(((ff) v8_9).b));
                }
                Throwable v1_25 = new java.util.HashMap();
                if ((v0_3 != null) && (!v5_26.isEmpty())) {
                    int v6_17 = new android.app.DownloadManager$Query();
                    Long v7_4 = v5_26.size();
                    int v8_5 = new long[v7_4];
                    Long v9_5 = v5_26.size();
                    m40 v11_5 = 0;
                    Integer v12_4 = 0;
                    while (v12_4 < v9_5) {
                        Long v13_12 = v5_26.get(v12_4);
                        v12_4++;
                        int v15_2 = (v11_5 + 1);
                        v8_5[v11_5] = ((Number) v13_12).longValue();
                        v11_5 = v15_2;
                    }
                    String v5_29 = v0_3.query(v6_17.setFilterById(java.util.Arrays.copyOf(v8_5, v7_4)));
                    if (v5_29 != null) {
                        try {
                            Throwable v0_5 = v5_29.getColumnIndexOrThrow("_id");
                            int v6_20 = v5_29.getColumnIndexOrThrow("status");
                            Long v7_6 = v5_29.getColumnIndexOrThrow("bytes_so_far");
                            int v8_7 = v5_29.getColumnIndexOrThrow("total_size");
                        } catch (Throwable v0_6) {
                            Throwable v1_26 = v0_6;
                            try {
                                throw v1_26;
                            } catch (Throwable v0_7) {
                                c8.i(v5_29, v1_26);
                                throw v0_7;
                            }
                        }
                        while (v5_29.moveToNext()) {
                            v1_25.put(Long.valueOf(v5_29.getLong(v0_5)), new m40(Integer.valueOf(v5_29.getInt(v6_20)), Long.valueOf(v5_29.getLong(v7_6)), Long.valueOf(v5_29.getLong(v8_7))));
                        }
                        v5_29.close();
                    }
                }
                Throwable v0_9 = new java.util.ArrayList(tb.e0(v2_8));
                String v5_31 = v2_8.size();
                while (v10_12 < v5_31) {
                    m40 v11_7;
                    int v6_21 = v2_8.get(v10_12);
                    v10_12++;
                    Integer v12_7 = ((ff) v6_21);
                    int v6_22 = v12_7.b;
                    if (v6_22 > 0) {
                        int v6_25 = ((m40) v1_25.get(Long.valueOf(v6_22)));
                        if (v6_25 != 0) {
                            v11_7 = new ef(v12_7, v6_25.a.intValue(), v6_25.b.longValue(), v6_25.c.longValue());
                        } else {
                            v11_7 = new ef(v12_7, -1, -1, -1);
                        }
                    } else {
                        v11_7 = new ef(v12_7, 8, -1, -1);
                    }
                    v0_9.add(v11_7);
                }
                return v0_9;
            case 3:
                Class vtmp9 = ((a50) p23).getClass();
                v0_12.q();
                return v9_1;
            case 4:
                Class vtmp10 = ((a50) p23).getClass();
                v0_12.q();
                return v9_1;
            case 5:
                Class vtmp11 = ((a50) p23).getClass();
                v0_12.q();
                return v9_1;
            case 6:
                Class vtmp12 = ((a50) p23).getClass();
                v0_12.q();
                return v9_1;
            case 9:
                Class vtmp13 = ((java.util.List) p23).getClass();
                long v2_11 = new java.util.ArrayList(tb.e0(((java.util.List) p23)));
                Throwable v1_29 = ((java.util.List) p23).iterator();
                while (v1_29.hasNext()) {
                    Integer v12_11;
                    long v3_9 = ((o7) v1_29.next());
                    um v4_6 = v3_9.a;
                    int v6_30 = v3_9.b;
                    Long v7_13 = new StringBuilder("b");
                    v7_13.append(v4_6);
                    m40 v11_15 = v7_13.toString();
                    um v4_7 = v3_9.c;
                    if (!m10.G(v4_7)) {
                        v12_11 = v4_7;
                    } else {
                        v12_11 = v6_30;
                    }
                    v2_11.add(new ip(v11_15, v12_11, d50.a(v6_30), 2131165373, 0, v3_9));
                }
                v0_12.r(v2_11);
                return v9_1;
            case 10:
                Class vtmp16 = ((java.util.List) p23).getClass();
                long v3_2 = new java.util.ArrayList(tb.e0(((java.util.List) p23)));
                Throwable v1_17 = ((java.util.List) p23).iterator();
                while (v1_17.hasNext()) {
                    Integer v12_5;
                    um v4_5 = ((um) v1_17.next());
                    String v5_16 = v4_5.a;
                    Long v7_1 = v4_5.b;
                    int v8_4 = new StringBuilder("h");
                    v8_4.append(v5_16);
                    m40 v11_4 = v8_4.toString();
                    String v5_23 = v4_5.c;
                    if (!m10.G(v5_23)) {
                        v12_5 = v5_23;
                    } else {
                        v12_5 = v7_1;
                    }
                    String v5_32 = d50.a(v7_1);
                    int v6_28 = android.text.format.DateUtils.getRelativeTimeSpanString(v4_5.d);
                    Long v7_10 = new StringBuilder(v5_32);
                    v7_10.append(" \u00b7 ");
                    v7_10.append(v6_28);
                    v3_2.add(new ip(v11_4, v12_5, v7_10.toString(), 2131165344, 0, v4_5));
                }
                v0_12.r(v3_2);
                return v9_1;
        }
    }

    public c90 k(android.view.View p6, c90 p7)
    {
        Class vtmp1 = p6.getClass();
        int v0_2 = p7.a.h(647);
        v0_2.getClass();
        p6.setPadding(v0_2.a, v0_2.b, v0_2.c, p6.getPaddingBottom());
        int v5_2 = this.b.y;
        if (v5_2 == 0) {
            io.T("binding");
            throw 0;
        } else {
            int v5_5 = v5_2.list;
            v5_5.getClass();
            v5_5.setPadding(v5_5.getPaddingLeft(), v5_5.getPaddingTop(), v5_5.getPaddingRight(), v0_2.d);
            return p7;
        }
    }
}
