public final class Lpm {
    public final android.content.Context a;
    public final h20 b;
    public volatile String c;
    public volatile long d;

    public pm(com.example.instatool.InstaToolApp p2)
    {
        this.a = p2.getApplicationContext();
        this.b = new h20(new cc(this, 2));
        return;
    }

    public static String f(String p1, String p2, String p3, String p4, boolean p5)
    {
        Throwable v2_1 = new java.net.URL(p2).openConnection();
        v2_1.getClass();
        Throwable v2_3 = ((java.net.HttpURLConnection) v2_1);
        v2_3.setRequestMethod(p1);
        v2_3.setConnectTimeout(20000);
        v2_3.setReadTimeout(20000);
        if (p3 != null) {
            v2_3.setRequestProperty("Authorization", "Bearer ".concat(p3));
        }
        if (p4 != null) {
            om v1_5;
            v2_3.setDoOutput(1);
            if (p5 == 0) {
                v1_5 = "application/json; charset=utf-8";
            } else {
                v1_5 = "application/x-www-form-urlencoded";
            }
            v2_3.setRequestProperty("Content-Type", v1_5);
            om v1_6 = v2_3.getOutputStream();
            try {
                String v3_6 = p4.getBytes(ka.a);
                v3_6.getClass();
                v1_6.write(v3_6);
                v1_6.close();
            } catch (Throwable v2_2) {
                try {
                    throw v2_2;
                } catch (String v3_7) {
                    c8.i(v1_6, v2_2);
                    throw v3_7;
                }
            }
        }
        try {
            om v1_7 = v2_3.getResponseCode();
        } catch (om v1_2) {
            v2_3.disconnect();
            throw v1_2;
        }
        if ((200 > v1_7) || (v1_7 >= 300)) {
            String v4_2;
            om v1_8 = v2_3.getErrorStream();
            String v3_10 = 0;
            if (v1_8 == null) {
                v4_2 = 0;
            } else {
                try {
                    v4_2 = new String(io.D(v1_8), ka.a);
                } catch (String v3_11) {
                    try {
                        throw v3_11;
                    } catch (String v4_4) {
                        c8.i(v1_8, v3_11);
                        throw v4_4;
                    }
                }
                v1_8.close();
            }
            if (v4_2 == null) {
                v4_2 = "";
            }
            int v5_3 = v2_3.getResponseCode();
            try {
                String v4_8;
                String v4_6 = new org.json.JSONObject(v4_2).optJSONObject("error");
            } catch (String v4_7) {
                v4_8 = new hy(v4_7);
                if ((v4_8 instanceof hy)) {
                    v4_8 = 0;
                }
                String v4_9 = ((String) v4_8);
                if (v4_9 == null) {
                    v3_10 = g.c(v5_3, "HTTP ");
                } else {
                    if (!m10.G(v4_9)) {
                        v3_10 = v4_9;
                    }
                    if (v3_10 == null) {
                    } else {
                    }
                }
                throw new om(v3_10);
            }
            if (v4_6 == null) {
                v4_8 = 0;
            } else {
                v4_8 = v4_6.optString("message");
            }
        } else {
            om v1_12 = v2_3.getInputStream();
            try {
                v1_12.getClass();
                String v3_1 = new String(io.D(v1_12), ka.a);
            } catch (String v3_2) {
                try {
                    throw v3_2;
                } catch (String v4_1) {
                    c8.i(v1_12, v3_2);
                    throw v4_1;
                }
            }
            v1_12.close();
            v2_3.disconnect();
            return v3_1;
        }
    }

    public final String a()
    {
        String v0_0 = this.c;
        if ((v0_0 == null) || (System.currentTimeMillis() >= (this.d - 60000))) {
            String v0_7 = ((org.json.JSONObject) this.b.a());
            long v1_5 = v0_7.optString("token_uri", "https://oauth2.googleapis.com/token");
            org.json.JSONObject v2_7 = v0_7.getString("client_email");
            v2_7.getClass();
            String v0_12 = v0_7.getString("private_key");
            v0_12.getClass();
            v1_5.getClass();
            long v3_9 = (System.currentTimeMillis() / 1000);
            String v7_1 = ka.a;
            java.security.spec.PKCS8EncodedKeySpec v8_1 = "{\"alg\":\"RS256\",\"typ\":\"JWT\"}".getBytes(v7_1);
            v8_1.getClass();
            java.security.spec.PKCS8EncodedKeySpec v8_2 = android.util.Base64.encodeToString(v8_1, 11);
            v8_2.getClass();
            org.json.JSONObject v2_13 = new org.json.JSONObject().put("iss", v2_7).put("scope", "https://www.googleapis.com/auth/spreadsheets").put("aud", v1_5).put("iat", v3_9).put("exp", (v3_9 + 3600)).toString();
            v2_13.getClass();
            org.json.JSONObject v2_14 = v2_13.getBytes(v7_1);
            v2_14.getClass();
            org.json.JSONObject v2_15 = android.util.Base64.encodeToString(v2_14, 11);
            v2_15.getClass();
            long v3_14 = new StringBuilder(v8_2);
            v3_14.append(".");
            v3_14.append(v2_15);
            org.json.JSONObject v2_16 = v3_14.toString();
            String v0_14 = u10.y(u10.y(v0_12, "-----BEGIN PRIVATE KEY-----", ""), "-----END PRIVATE KEY-----", "");
            long v3_18 = java.util.regex.Pattern.compile("\\s");
            v3_18.getClass();
            String v0_16 = v3_18.matcher(v0_14).replaceAll("");
            v0_16.getClass();
            String v0_1 = java.security.KeyFactory.getInstance("RSA").generatePrivate(new java.security.spec.PKCS8EncodedKeySpec(android.util.Base64.decode(v0_16, 0)));
            long v3_1 = java.security.Signature.getInstance("SHA256withRSA");
            v3_1.initSign(v0_1);
            String v0_2 = v2_16.getBytes(v7_1);
            v0_2.getClass();
            v3_1.update(v0_2);
            String v0_4 = v3_1.sign();
            v0_4.getClass();
            String v0_5 = android.util.Base64.encodeToString(v0_4, 11);
            v0_5.getClass();
            String v0_6 = g.e(v2_16, ".", v0_5);
            org.json.JSONObject v2_1 = java.net.URLEncoder.encode("urn:ietf:params:oauth:grant-type:jwt-bearer", "UTF-8");
            v2_1.getClass();
            long v3_4 = new StringBuilder("grant_type=");
            v3_4.append(v2_1);
            v3_4.append("&assertion=");
            v3_4.append(v0_6);
            org.json.JSONObject v2_4 = new org.json.JSONObject(pm.f("POST", v1_5, 0, v3_4.toString(), 1));
            String v0_11 = v2_4.getString("access_token");
            this.d = ((v2_4.optLong("expires_in", 3600) * 1000) + System.currentTimeMillis());
            this.c = v0_11;
            v0_11.getClass();
            return v0_11;
        } else {
            return v0_0;
        }
    }

    public final void b(String p8, java.util.ArrayList p9)
    {
        p8.getClass();
        String v0_4 = new java.util.ArrayList();
        String v1_1 = p9.size();
        String v3_2 = 0;
        while (v3_2 < v1_1) {
            String v4_8 = p9.get(v3_2);
            v3_2++;
            if (((Number) v4_8).intValue() >= 2) {
                v0_4.add(v4_8);
            }
        }
        String v9_3;
        String v9_1 = rb.r0(new java.util.LinkedHashSet(v0_4));
        if (v9_1.size() > 1) {
            String v0_2 = new Comparable[0];
            String v9_2 = v9_1.toArray(v0_2);
            String v0_5 = ((Comparable[]) v9_2);
            v0_5.getClass();
            if (v0_5.length > 1) {
                java.util.Arrays.sort(v0_5);
            }
            v9_2.getClass();
            v9_3 = java.util.Arrays.asList(v9_2);
            v9_3.getClass();
        } else {
            v9_3 = rb.r0(v9_1);
        }
        if (!v9_3.isEmpty()) {
            String v7_1 = this.a();
            String v0_8 = new org.json.JSONArray();
            String v9_4 = v9_3.iterator();
            while (v9_4.hasNext()) {
                String v1_8 = ((Number) v9_4.next()).intValue();
                String v3_4 = new org.json.JSONObject();
                String v4_1 = new StringBuilder("C");
                v4_1.append(v1_8);
                v0_8.put(v3_4.put("range", v4_1.toString()).put("majorDimension", "ROWS").put("values", new org.json.JSONArray().put(new org.json.JSONArray().put(""))));
            }
            pm.f("POST", g.e("https://sheets.googleapis.com/v4/spreadsheets/", p8, "/values:batchUpdate"), v7_1, new org.json.JSONObject().put("valueInputOption", "RAW").put("data", v0_8).toString(), 0);
            return;
        } else {
            return;
        }
    }

    public final void c(String p11, String p12, java.util.ArrayList p13)
    {
        p11.getClass();
        org.json.JSONArray v0_4 = new java.util.ArrayList();
        org.json.JSONObject v1_9 = p13.size();
        org.json.JSONObject v3_2 = 0;
        while (v3_2 < v1_9) {
            String v4_0 = p13.get(v3_2);
            v3_2++;
            if (((Number) v4_0).intValue() >= 2) {
                v0_4.add(v4_0);
            }
        }
        String v13_2 = rb.o0(rb.r0(new java.util.LinkedHashSet(v0_4)), wt.c);
        if (!v13_2.isEmpty()) {
            org.json.JSONArray v0_7 = new org.json.JSONObject(pm.f("GET", g.e("https://sheets.googleapis.com/v4/spreadsheets/", p11, "?fields=sheets.properties"), this.a(), 0, 0)).optJSONArray("sheets");
            if (v0_7 == null) {
                om v10_1 = new om;
                v10_1("No sheets in spreadsheet");
                throw v10_1;
            } else {
                String v12_1;
                org.json.JSONObject v1_10 = m10.P(p12).toString();
                if ((v1_10.length() != 0) || (v0_7.length() <= 0)) {
                    org.json.JSONObject v3_7 = v0_7.length();
                    String v7_6 = 0;
                    while (v7_6 < v3_7) {
                        String v8_4 = v0_7.getJSONObject(v7_6).getJSONObject("properties");
                        if (!io.d(v8_4.optString("title"), v1_10)) {
                            v7_6++;
                        } else {
                            v12_1 = v8_4.getInt("sheetId");
                        }
                    }
                    om v10_2 = new om;
                    v10_2("Sheet tab not found: ".concat(p12));
                    throw v10_2;
                } else {
                    v12_1 = v0_7.getJSONObject(0).getJSONObject("properties").getInt("sheetId");
                }
                om v10_3 = this.a();
                org.json.JSONArray v0_9 = new org.json.JSONArray();
                String v13_4 = v13_2.iterator();
                while (v13_4.hasNext()) {
                    org.json.JSONObject v1_2 = ((Number) v13_4.next()).intValue();
                    v0_9.put(new org.json.JSONObject().put("deleteDimension", new org.json.JSONObject().put("range", new org.json.JSONObject().put("sheetId", v12_1).put("dimension", "ROWS").put("startIndex", (v1_2 - 1)).put("endIndex", v1_2))));
                }
                pm.f("POST", g.e("https://sheets.googleapis.com/v4/spreadsheets/", p11, ":batchUpdate"), v10_3, new org.json.JSONObject().put("requests", v0_9).toString(), 0);
                return;
            }
        } else {
            return;
        }
    }

    public final void d(String p12, java.util.List p13)
    {
        StringBuilder v1_4;
        p12.getClass();
        p13.getClass();
        String v11_1 = this.a();
        String v0_5 = ((char) (p13.size() + 64));
        StringBuilder v1_0 = new StringBuilder("A1:");
        v1_0.append(v0_5);
        v1_0.append("1");
        String v0_2 = v1_0.toString();
        String v3_0 = java.net.URLEncoder.encode(v0_2, "UTF-8");
        v3_0.getClass();
        boolean v4_1 = new StringBuilder("https://sheets.googleapis.com/v4/spreadsheets/");
        v4_1.append(p12);
        v4_1.append("/values/");
        v4_1.append(v3_0);
        int v7_0 = 0;
        StringBuilder v1_3 = new org.json.JSONObject(pm.f("GET", v4_1.toString(), v11_1, 0, 0)).optJSONArray("values");
        if (v1_3 == null) {
            v1_4 = 0;
        } else {
            v1_4 = v1_3.optJSONArray(0);
        }
        if (v1_4 != null) {
            boolean v4_4 = c8.Z(0, v1_4.length());
            v7_0 = new java.util.ArrayList(tb.e0(v4_4));
            boolean v4_5 = v4_4.iterator();
            while(true) {
                String v9_6 = ((fo) v4_5);
                if (!v9_6.c) {
                    break;
                }
                String v9_1 = v1_4.optString(v9_6.nextInt());
                v9_1.getClass();
                v7_0.add(m10.P(v9_1).toString());
            }
        }
        if (v7_0 == 0) {
            v7_0 = qh.a;
        }
        if (!v7_0.equals(p13)) {
            if (!v7_0.isEmpty()) {
                StringBuilder v1_7 = v7_0.iterator();
                while (v1_7.hasNext()) {
                    if (m10.B(((String) v1_7.next()), 64)) {
                    }
                    return;
                }
            }
            String v13_3 = new org.json.JSONObject().put("range", v0_2).put("majorDimension", "ROWS").put("values", new org.json.JSONArray().put(new org.json.JSONArray(p13)));
            String v0_6 = java.net.URLEncoder.encode(v0_2, "UTF-8");
            v0_6.getClass();
            StringBuilder v1_14 = new StringBuilder("https://sheets.googleapis.com/v4/spreadsheets/");
            v1_14.append(p12);
            v1_14.append("/values/");
            v1_14.append(v0_6);
            v1_14.append("?valueInputOption=RAW");
            pm.f("PUT", v1_14.toString(), v11_1, v13_3.toString(), 0);
        }
        return;
    }

    public final java.util.List e(String p12)
    {
        qh v11_6;
        p12.getClass();
        qh v11_2 = this.a();
        java.util.Iterator v0_6 = java.net.URLEncoder.encode("A2:D", "UTF-8");
        v0_6.getClass();
        java.util.ArrayList v1_0 = new StringBuilder("https://sheets.googleapis.com/v4/spreadsheets/");
        v1_0.append(p12);
        v1_0.append("/values/");
        v1_0.append(v0_6);
        v1_0.append("?majorDimension=ROWS");
        java.util.Iterator v0_1 = new org.json.JSONObject(pm.f("GET", v1_0.toString(), v11_2, 0, 0));
        qh v11_5 = v0_1.optString("range");
        v11_5.getClass();
        int v12_5 = m10.H(v11_5, 33);
        if (v12_5 != -1) {
            v11_6 = v11_5.substring(0, v12_5);
        } else {
            v11_6 = "";
        }
        java.util.ArrayList v1_3 = new char[1];
        v1_3[0] = 39;
        String v10 = m10.Q(v11_6, v1_3);
        qh v11_8 = v0_1.optJSONArray("values");
        if (v11_8 != null) {
            java.util.Iterator v0_4 = c8.Z(0, v11_8.length());
            java.util.ArrayList v1_6 = new java.util.ArrayList(tb.e0(v0_4));
            java.util.Iterator v0_5 = v0_4.iterator();
            while(true) {
                int v2_4 = ((fo) v0_5);
                if (!v2_4.c) {
                    break;
                }
                int v2_5 = v2_4.nextInt();
                int v5_0 = v11_8.getJSONArray(v2_5);
                int v2_6 = (v2_5 + 2);
                String v7_0 = v5_0.optString(0);
                v7_0.getClass();
                String v6_1 = m10.P(v7_0).toString();
                String v7_3 = v5_0.optString(1);
                v7_3.getClass();
                String v8_1 = v5_0.optString(2);
                v8_1.getClass();
                String v8_3 = m10.P(v8_1).toString();
                int v5_1 = v5_0.optString(3);
                v5_1.getClass();
                v1_6.add(new nm(v2_6, v6_1, v7_3, v8_3, m10.P(v5_1).toString(), v10));
            }
            return v1_6;
        } else {
            return qh.a;
        }
    }

    public final void g(String p6, int p7, java.util.Map p8)
    {
        p6.getClass();
        if (p8.isEmpty()) {
            e6.g("Failed requirement.");
            return;
        } else {
            String v5_2 = this.a();
            String v0_0 = new org.json.JSONArray();
            int v8_2 = p8.entrySet().iterator();
            while (v8_2.hasNext()) {
                String v1_3 = ((java.util.Map$Entry) v8_2.next());
                org.json.JSONObject v2_2 = ((Character) v1_3.getKey()).charValue();
                String v1_5 = ((String) v1_3.getValue());
                String v3_1 = new org.json.JSONObject();
                org.json.JSONArray v4_1 = new StringBuilder();
                v4_1.append(v2_2);
                v4_1.append(p7);
                v0_0.put(v3_1.put("range", v4_1.toString()).put("majorDimension", "ROWS").put("values", new org.json.JSONArray().put(new org.json.JSONArray().put(v1_5))));
            }
            pm.f("POST", g.e("https://sheets.googleapis.com/v4/spreadsheets/", p6, "/values:batchUpdate"), v5_2, new org.json.JSONObject().put("valueInputOption", "RAW").put("data", v0_0).toString(), 0);
            return;
        }
    }
}
