public abstract class Lp40 {
    public static final Object a;
    public static java.util.concurrent.ExecutorService b;
    public static final int[] c;
    public static final Object[] d;
    public static final Object e;
    public static final pg f;
    public static final Object g;
    public static reflect.Method h;
    public static boolean i;
    public static final int[] j;
    public static final int[] k;

    static synthetic p40()
    {
        p40.a = new Object();
        int v1_1 = new int[0];
        p40.c = v1_1;
        int[] v0_11 = new Object[0];
        p40.d = v0_11;
        p40.e = new Object();
        p40.f = new pg(26);
        p40.g = new Object();
        p40.j = new int[] {2130903329});
        p40.k = new int[] {2130903336});
        return;
    }

    public static boolean C(int p21)
    {
        int v20_0;
        if (p21 == 0) {
            v20_0 = 0;
        } else {
            double v1_1 = ac.a;
            double[] v2_1 = ((double[]) v1_1.get());
            if (v2_1 == null) {
                v2_1 = new double[3];
                v1_1.set(v2_1);
            }
            double v1_0 = android.graphics.Color.red(p21);
            int v4 = android.graphics.Color.green(p21);
            int v5_0 = android.graphics.Color.blue(p21);
            if (v2_1.length != 3) {
                e6.g("outXyz must have a length of 3.");
                return 0;
            } else {
                long v6_5;
                long v6_2 = (((double) v1_0) / 4643176031446892544);
                if (v6_2 >= 4585990280393462802) {
                    v6_5 = Math.pow(((v6_2 + 4588087156379966505) / 4607430116779522785), 4612586738352862003);
                } else {
                    v6_5 = (v6_2 / 4623462931452961751);
                }
                int v3_4;
                int v3_1 = (((double) v4) / 4643176031446892544);
                if (v3_1 >= 4585990280393462802) {
                    v3_4 = Math.pow(((v3_1 + 4588087156379966505) / 4607430116779522785), 4612586738352862003);
                } else {
                    v3_4 = (v3_1 / 4623462931452961751);
                }
                double v0_5;
                v20_0 = 0;
                double v0_2 = (((double) v5_0) / 4643176031446892544);
                if (v0_2 >= 4585990280393462802) {
                    v0_5 = Math.pow(((v0_2 + 4588087156379966505) / 4607430116779522785), 4612586738352862003);
                } else {
                    v0_5 = (v0_2 / 4623462931452961751);
                }
                v2_1[0] = (((4595671218152458420 * v0_5) + ((4600113568824896677 * v3_4) + (4601100757863216290 * v6_5))) * 4636737291354636288);
                double v8_12 = (((4589866978952703325 * v0_5) + ((4604617168452267173 * v3_4) + (4596827742536767164 * v6_5))) * 4636737291354636288);
                v2_1[1] = v8_12;
                v2_1[2] = (((v0_5 * 4606736562436907729) + ((v3_4 * 4593253685872485938) + (v6_5 * 4581220067668151973))) * 4636737291354636288);
                if ((v8_12 / 4636737291354636288) > 4602678819172646912) {
                    return 1;
                }
            }
        }
        return v20_0;
    }

    public static boolean D(android.view.MotionEvent p0, int p1)
    {
        if ((p0.getSource() & p1) != p1) {
            return 0;
        } else {
            return 1;
        }
    }

    public static int E(int p1, int p2, float p3)
    {
        return ac.c(ac.e(p2, Math.round((((float) android.graphics.Color.alpha(p2)) * p3))), p1);
    }

    public static float F(float p1, float p2, float p3)
    {
        return ((p3 * p2) + ((1065353216 - p3) * p1));
    }

    public static boolean G(String p3)
    {
        p3.getClass();
        boolean v3_4 = m10.P(p3).toString();
        if ((v3_4.length() == 0) || ((!m10.A(v3_4, "sessionid=", 1)) && ((v3_4.length() <= 60) || ((!m10.B(v3_4, 61)) || (!m10.B(v3_4, 59)))))) {
            return 0;
        } else {
            return 1;
        }
    }

    public static boolean H(String p4)
    {
        p4.getClass();
        int v4_2 = u10.y(p4, " ", "");
        int v0_3 = java.util.Locale.US;
        v0_3.getClass();
        int v4_3 = v4_2.toUpperCase(v0_3);
        v4_3.getClass();
        int v0_1 = v4_3.length();
        if ((16 <= v0_1) && (v0_1 < 65)) {
            int v0_2 = 0;
            while (v0_2 < v4_3.length()) {
                if (m10.B("ABCDEFGHIJKLMNOPQRSTUVWXYZ234567", v4_3.charAt(v0_2))) {
                    v0_2++;
                }
            }
            return 1;
        }
        return 0;
    }

    public static void I(xu[] p33, android.graphics.Path p34)
    {
        int v0_0 = p33;
        android.graphics.Path v1_0 = p34;
        float[] v12 = new float[6];
        int v13 = p33.length;
        float v15_7 = 0;
        float v8_3 = 0;
        int v2_34 = 109;
        while (v8_3 < v13) {
            int v22;
            int v9_0 = v0_0[v8_3];
            int v10_0 = v9_0.a;
            float v3_1 = v9_0.b;
            int v4_3 = v12[v15_7];
            int v5_2 = v12[1];
            int v6_1 = v12[2];
            int v7_1 = v12[3];
            float v11_2 = v12[4];
            int v21 = v15_7;
            float v15_1 = v12[5];
            switch (v10_0) {
                case 65:
                case 97:
                    v22 = 7;
                    break;
                case 67:
                case 99:
                    v22 = 6;
                    break;
                case 72:
                case 86:
                case 104:
                case 118:
                    v22 = 1;
                    break;
                case 81:
                case 83:
                case 113:
                case 115:
                    v22 = 4;
                    break;
                case 90:
                case 122:
                    v1_0.close();
                    v1_0.moveTo(v11_2, v15_1);
                    v4_3 = v11_2;
                    v6_1 = v4_3;
                    v5_2 = v15_1;
                    v7_1 = v5_2;
                    v22 = 2;
                    break;
                default:
            }
            int v23 = v11_2;
            int v24 = v15_1;
            float v11_3 = v4_3;
            float v15_2 = v5_2;
            int v4_21 = v21;
            while (v4_21 < v3_1.length) {
                float v15_0;
                int v25;
                float v11_0;
                int v30;
                int v0_1;
                float v3_3;
                int v2_0;
                if (v10_0 == 65) {
                    int v9_3;
                    v25 = v3_1;
                    v30 = v4_21;
                    v0_1 = v9_0;
                    v15_0 = v8_3;
                    v11_0 = v10_0;
                    int v14_17 = (v30 + 5);
                    int v27_3 = (v30 + 6);
                    if (v25[(v30 + 3)] == 0) {
                        v9_3 = v21;
                    } else {
                        v9_3 = 1;
                    }
                    int v10_3;
                    if (v25[(v30 + 4)] == 0) {
                        v10_3 = v21;
                    } else {
                        v10_3 = 1;
                    }
                    xu.a(p34, v11_3, v15_2, v25[v14_17], v25[v27_3], v25[v30], v25[(v30 + 1)], v25[(v30 + 2)], v9_3, v10_3);
                    v6_1 = v25[v14_17];
                    v3_3 = v25[v27_3];
                    v7_1 = v3_3;
                    v2_0 = v6_1;
                } else {
                    if (v10_0 == 67) {
                        v25 = v3_1;
                        v30 = v4_21;
                        v15_0 = v8_3;
                        v0_1 = v9_0;
                        v11_0 = v10_0;
                        float v8_0 = (v30 + 2);
                        int v9_1 = (v30 + 3);
                        int v10_1 = (v30 + 4);
                        int v14_0 = (v30 + 5);
                        v1_0.cubicTo(v25[v30], v25[(v30 + 1)], v25[v8_0], v25[v9_1], v25[v10_1], v25[v14_0]);
                        v6_1 = v25[v8_0];
                        v7_1 = v25[v9_1];
                        v3_3 = v25[v14_0];
                        v2_0 = v25[v10_1];
                    } else {
                        if (v10_0 == 72) {
                            v25 = v3_1;
                            v30 = v4_21;
                            v0_1 = v9_0;
                            v11_0 = v10_0;
                            v3_3 = v15_2;
                            v15_0 = v8_3;
                            v1_0.lineTo(v25[v30], v3_3);
                            v2_0 = v25[v30];
                        } else {
                            if (v10_0 == 81) {
                                v25 = v3_1;
                                v30 = v4_21;
                                v15_0 = v8_3;
                                v0_1 = v9_0;
                                v11_0 = v10_0;
                                int v4_4 = (v30 + 1);
                                int v5_3 = (v30 + 2);
                                int v7_2 = (v30 + 3);
                                v1_0.quadTo(v25[v30], v25[v4_4], v25[v5_3], v25[v7_2]);
                                v6_1 = v25[v30];
                                v7_1 = v25[v4_4];
                                v2_0 = v25[v5_3];
                                v3_3 = v25[v7_2];
                            } else {
                                if (v10_0 == 86) {
                                    v25 = v3_1;
                                    v30 = v4_21;
                                    v15_0 = v8_3;
                                    v0_1 = v9_0;
                                    v2_0 = v11_3;
                                    v11_0 = v10_0;
                                    v1_0.lineTo(v2_0, v25[v30]);
                                    v3_3 = v25[v30];
                                } else {
                                    if (v10_0 == 97) {
                                        int v2_9;
                                        int v9_2;
                                        v25 = v3_1;
                                        v30 = v4_21;
                                        int v14_3 = (v30 + 5);
                                        int v27_0 = (v30 + 6);
                                        if (v25[(v30 + 3)] == 0) {
                                            v2_9 = v9_0;
                                            v9_2 = v21;
                                        } else {
                                            v2_9 = v9_0;
                                            v9_2 = 1;
                                        }
                                        int v10_2;
                                        v0_1 = v2_9;
                                        int v2_10 = v11_3;
                                        v11_0 = v10_0;
                                        if (v25[(v30 + 4)] == 0) {
                                            v10_2 = v21;
                                        } else {
                                            v10_2 = 1;
                                        }
                                        float v3_10 = v15_2;
                                        v15_0 = v8_3;
                                        xu.a(p34, v2_10, v3_10, (v25[v14_3] + v11_3), (v25[v27_0] + v15_2), v25[v30], v25[(v30 + 1)], v25[(v30 + 2)], v9_2, v10_2);
                                        v2_0 = (v2_10 + v25[v14_3]);
                                        v3_3 = (v3_10 + v25[v27_0]);
                                        v6_1 = v2_0;
                                        v7_1 = v3_3;
                                    } else {
                                        if (v10_0 == 99) {
                                            v25 = v3_1;
                                            v30 = v4_21;
                                            int v14_4 = (v30 + 2);
                                            int v26_1 = (v30 + 3);
                                            int v27_1 = (v30 + 4);
                                            int v28_0 = (v30 + 5);
                                            v1_0.rCubicTo(v25[v30], v25[(v30 + 1)], v25[v14_4], v25[v26_1], v25[v27_1], v25[v28_0]);
                                            android.graphics.Path v1_9 = (v25[v14_4] + v11_3);
                                            int v2_13 = (v25[v26_1] + v15_2);
                                            v11_3 += v25[v27_1];
                                            v15_2 += v25[v28_0];
                                            v6_1 = v1_9;
                                            v7_1 = v2_13;
                                            v0_1 = v9_0;
                                            v2_0 = v11_3;
                                            v3_3 = v15_2;
                                            v15_0 = v8_3;
                                        } else {
                                            if (v10_0 == 104) {
                                                v25 = v3_1;
                                                v30 = v4_21;
                                                v1_0.rLineTo(v25[v30], 0);
                                                v11_3 += v25[v30];
                                            } else {
                                                float v3_17;
                                                int v2_18;
                                                int v4_13;
                                                if (v10_0 == 113) {
                                                    v25 = v3_1;
                                                    v30 = v4_21;
                                                    int v4_11 = (v30 + 1);
                                                    int v5_12 = (v30 + 2);
                                                    int v7_5 = (v30 + 3);
                                                    v1_0.rQuadTo(v25[v30], v25[v4_11], v25[v5_12], v25[v7_5]);
                                                    v2_18 = (v25[v30] + v11_3);
                                                    v3_17 = (v25[v4_11] + v15_2);
                                                    v11_3 += v25[v5_12];
                                                    v4_13 = v25[v7_5];
                                                } else {
                                                    int v2_20;
                                                    if (v10_0 == 118) {
                                                        v25 = v3_1;
                                                        v30 = v4_21;
                                                        v1_0.rLineTo(0, v25[v30]);
                                                        v2_20 = v25[v30];
                                                    } else {
                                                        if (v10_0 == 76) {
                                                            v25 = v3_1;
                                                            v30 = v4_21;
                                                            int v4_14 = (v30 + 1);
                                                            v1_0.lineTo(v25[v30], v25[v4_14]);
                                                            v2_0 = v25[v30];
                                                            v3_3 = v25[v4_14];
                                                        } else {
                                                            if (v10_0 == 77) {
                                                                v25 = v3_1;
                                                                v30 = v4_21;
                                                                v2_0 = v25[v30];
                                                                v3_3 = v25[(v30 + 1)];
                                                                if (v30 <= 0) {
                                                                    v1_0.moveTo(v2_0, v3_3);
                                                                    v23 = v2_0;
                                                                    v24 = v3_3;
                                                                } else {
                                                                    v1_0.lineTo(v2_0, v3_3);
                                                                }
                                                            } else {
                                                                if (v10_0 == 83) {
                                                                    v25 = v3_1;
                                                                    v30 = v4_21;
                                                                    if ((v2_34 == 99) || ((v2_34 == 115) || ((v2_34 == 67) || (v2_34 == 83)))) {
                                                                        v11_3 = ((v11_3 * 1073741824) - v6_1);
                                                                        v15_2 = ((v15_2 * 1073741824) - v7_1);
                                                                    }
                                                                    float v11_5 = (v30 + 1);
                                                                    int v14_10 = (v30 + 2);
                                                                    float v15_4 = (v30 + 3);
                                                                    v1_0.cubicTo(v11_3, v15_2, v25[v30], v25[v11_5], v25[v14_10], v25[v15_4]);
                                                                    v6_1 = v25[v30];
                                                                    v7_1 = v25[v11_5];
                                                                    v2_0 = v25[v14_10];
                                                                    v3_3 = v25[v15_4];
                                                                } else {
                                                                    if (v10_0 == 84) {
                                                                        v25 = v3_1;
                                                                        v30 = v4_21;
                                                                        if ((v2_34 == 113) || ((v2_34 == 116) || ((v2_34 == 81) || (v2_34 == 84)))) {
                                                                            v11_3 = ((v11_3 * 1073741824) - v6_1);
                                                                            v15_2 = ((v15_2 * 1073741824) - v7_1);
                                                                        }
                                                                        int v4_18 = (v30 + 1);
                                                                        v1_0.quadTo(v11_3, v15_2, v25[v30], v25[v4_18]);
                                                                        v2_0 = v25[v30];
                                                                        v3_3 = v25[v4_18];
                                                                        v0_1 = v9_0;
                                                                        v6_1 = v11_3;
                                                                        v7_1 = v15_2;
                                                                    } else {
                                                                        if (v10_0 == 108) {
                                                                            v25 = v3_1;
                                                                            v30 = v4_21;
                                                                            int v4_19 = (v30 + 1);
                                                                            v1_0.rLineTo(v25[v30], v25[v4_19]);
                                                                            v11_3 += v25[v30];
                                                                            v2_20 = v25[v4_19];
                                                                        } else {
                                                                            if (v10_0 == 109) {
                                                                                v25 = v3_1;
                                                                                v30 = v4_21;
                                                                                int v2_27 = v25[v30];
                                                                                v11_3 += v2_27;
                                                                                float v3_24 = v25[(v30 + 1)];
                                                                                v15_2 += v3_24;
                                                                                if (v30 <= 0) {
                                                                                    v1_0.rMoveTo(v2_27, v3_24);
                                                                                    v0_1 = v9_0;
                                                                                    v2_0 = v11_3;
                                                                                    v23 = v2_0;
                                                                                    v3_3 = v15_2;
                                                                                    v24 = v3_3;
                                                                                } else {
                                                                                    v1_0.rLineTo(v2_27, v3_24);
                                                                                }
                                                                            } else {
                                                                                if (v10_0 == 115) {
                                                                                    if ((v2_34 != 99) && ((v2_34 != 115) && ((v2_34 != 67) && (v2_34 != 83)))) {
                                                                                        int v2_28 = 0;
                                                                                        int v14_12 = 0;
                                                                                    } else {
                                                                                        v14_12 = (v15_2 - v7_1);
                                                                                        v2_28 = (v11_3 - v6_1);
                                                                                    }
                                                                                    int v5_30 = v4_21;
                                                                                    int v26_2 = (v5_30 + 1);
                                                                                    int v6_7 = v5_30;
                                                                                    int v27_2 = (v6_7 + 2);
                                                                                    int v7_7 = v6_7;
                                                                                    int v28_1 = (v7_7 + 3);
                                                                                    v25 = v3_1;
                                                                                    v30 = v7_7;
                                                                                    v1_0.rCubicTo(v2_28, v14_12, v3_1[v5_30], v3_1[v26_2], v3_1[v27_2], v3_1[v28_1]);
                                                                                    v2_18 = (v25[v30] + v11_3);
                                                                                    v3_17 = (v25[v26_2] + v15_2);
                                                                                    v11_3 += v25[v27_2];
                                                                                    v4_13 = v25[v28_1];
                                                                                } else {
                                                                                    if (v10_0 == 116) {
                                                                                        if ((v2_34 != 113) && ((v2_34 != 116) && ((v2_34 != 81) && (v2_34 != 84)))) {
                                                                                            int v2_32 = 0;
                                                                                            int v14_15 = 0;
                                                                                        } else {
                                                                                            v14_15 = (v11_3 - v6_1);
                                                                                            v2_32 = (v15_2 - v7_1);
                                                                                        }
                                                                                        int v6_9 = (v4_21 + 1);
                                                                                        v1_0.rQuadTo(v14_15, v2_32, v3_1[v4_21], v3_1[v6_9]);
                                                                                        int v2_33 = (v2_32 + v15_2);
                                                                                        v15_2 += v3_1[v6_9];
                                                                                        v7_1 = v2_33;
                                                                                        v25 = v3_1;
                                                                                        v30 = v4_21;
                                                                                        v0_1 = v9_0;
                                                                                        v2_0 = (v11_3 + v3_1[v4_21]);
                                                                                        v6_1 = (v14_15 + v11_3);
                                                                                    } else {
                                                                                        v25 = v3_1;
                                                                                        v30 = v4_21;
                                                                                        v0_1 = v9_0;
                                                                                        v2_0 = v11_3;
                                                                                    }
                                                                                    v3_3 = v15_2;
                                                                                }
                                                                            }
                                                                            v15_2 += v4_13;
                                                                            v6_1 = v2_18;
                                                                            v7_1 = v3_17;
                                                                        }
                                                                    }
                                                                    v15_2 += v2_20;
                                                                }
                                                            }
                                                        }
                                                        v15_0 = v8_3;
                                                        v0_1 = v9_0;
                                                        v11_0 = v10_0;
                                                        v4_21 = (v30 + v22);
                                                        v1_0 = p34;
                                                        v9_0 = v0_1;
                                                        v10_0 = v11_0;
                                                        v8_3 = v15_0;
                                                        v11_3 = v2_0;
                                                        v15_2 = v3_3;
                                                        v2_34 = v10_0;
                                                        v3_1 = v25;
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
            int v0_2 = v9_0;
            float v3_27 = v15_2;
            float v15_6 = v8_3;
            v12[v21] = v11_3;
            v12[1] = v3_27;
            v12[2] = v6_1;
            v12[3] = v7_1;
            v12[4] = v23;
            v12[5] = v24;
            v2_34 = v0_2.a;
            v8_3 = (v15_6 + 1);
            v0_0 = p33;
            v1_0 = p34;
            v15_7 = v21;
        }
        return;
    }

    public static void J(android.content.pm.PackageInfo p2, java.io.File p3)
    {
        try {
            Throwable v3_3 = new java.io.DataOutputStream(new java.io.FileOutputStream(new java.io.File(p3, "profileinstaller_profileWrittenFor_lastUpdateTime.dat")));
            try {
                v3_3.writeLong(p2.lastUpdateTime);
            } catch (Throwable v2_1) {
                try {
                    v3_3.close();
                } catch (Throwable v3_1) {
                    v2_1.addSuppressed(v3_1);
                }
                throw v2_1;
            }
            v3_3.close();
            return;
        } catch (java.io.IOException) {
            return;
        }
    }

    public static java.util.List K(org.json.JSONArray p4)
    {
        if (p4 != null) {
            java.util.Iterator v0_1 = c8.Z(0, p4.length());
            java.util.ArrayList v1_2 = new java.util.ArrayList();
            java.util.Iterator v0_2 = v0_1.iterator();
            do {
                org.json.JSONObject v2_1 = ((fo) v0_2);
                if (!v2_1.c) {
                    return v1_2;
                } else {
                    org.json.JSONObject v2_3 = p4.optJSONObject(v2_1.nextInt());
                }
            } while(v2_3 == null);
            v1_2.add(v2_3);
        } else {
            return qh.a;
        }
    }

    public static varargs android.content.res.TypedArray L(android.content.Context p0, android.util.AttributeSet p1, int[] p2, int p3, int p4, int[] p5)
    {
        p40.i(p0, p1, p3, p4);
        p40.k(p0, p1, p2, p3, p4, p5);
        return p0.obtainStyledAttributes(p1, p2, p3, p4);
    }

    public static byte[] T(java.io.InputStream p3, int p4)
    {
        byte[] v0 = new byte[p4];
        int v1 = 0;
        while (v1 < p4) {
            int v2_1 = p3.read(v0, v1, (p4 - v1));
            if (v2_1 < 0) {
                e6.j(g.c(p4, "Not enough bytes to read: "));
                return 0;
            } else {
                v1 += v2_1;
            }
        }
        return v0;
    }

    public static byte[] U(java.io.FileInputStream p8, int p9, int p10)
    {
        java.util.zip.Inflater v0_1 = new java.util.zip.Inflater();
        try {
            byte[] v1 = new byte[p10];
            byte[] v2_1 = new byte[2048];
            int v4 = 0;
            int v5 = 0;
        } catch (String v8_11) {
            v0_1.end();
            throw v8_11;
        }
        while ((!v0_1.finished()) && ((!v0_1.needsDictionary()) && (v4 < p9))) {
            int v6_1 = p8.read(v2_1);
            if (v6_1 < 0) {
                String v8_7 = new StringBuilder();
                v8_7.append("Invalid zip data. Stream ended after $totalBytesRead bytes. Expected ");
                v8_7.append(p9);
                v8_7.append(" bytes");
                throw new IllegalStateException(v8_7.toString());
            } else {
                v0_1.setInput(v2_1, 0, v6_1);
                try {
                    v5 += v0_1.inflate(v1, v5, (p10 - v5));
                    v4 += v6_1;
                } catch (String v8_9) {
                    throw new IllegalStateException(v8_9.getMessage());
                }
            }
        }
        if (v4 != p9) {
            String v8_2 = new StringBuilder();
            v8_2.append("Didn\'t read enough bytes during decompression. expected=");
            v8_2.append(p9);
            v8_2.append(" actual=");
            v8_2.append(v4);
            throw new IllegalStateException(v8_2.toString());
        } else {
            if (!v0_1.finished()) {
                throw new IllegalStateException("Inflater did not finish");
            } else {
                v0_1.end();
                return v1;
            }
        }
    }

    public static long V(java.io.InputStream p6, int p7)
    {
        byte[] v6_1 = p40.T(p6, p7);
        long v0 = 0;
        int v2 = 0;
        while (v2 < p7) {
            v0 += (((long) (v6_1[v2] & 255)) << (v2 * 8));
            v2++;
        }
        return v0;
    }

    public static final void W(Object[] p1, int p2, int p3)
    {
        p1.getClass();
        while (p2 < p3) {
            p1[p2] = 0;
            p2++;
        }
        return;
    }

    public static String X(String p2)
    {
        int v0_2 = java.util.regex.Pattern.compile("(?:^|;\\s*)sessionid=([^;]+)");
        v0_2.getClass();
        int v0_4 = v0_2.matcher(p2);
        v0_4.getClass();
        int v2_6 = io.o(v0_4, 0, p2);
        if (v2_6 != 0) {
            int v2_4 = ((String) ((pr) v2_6.a()).get(1));
            if ((v2_4 != 0) && (v2_4.length() > 10)) {
                return v2_4;
            }
        }
        return 0;
    }

    public static void Y(k4 p5, float p6)
    {
        double v0_1 = ((ly) p5.b);
        boolean v1_1 = ((w9) p5.c);
        int v2_5 = v1_1.getUseCompatPadding();
        boolean v3 = v1_1.getPreventCornerOverlap();
        if ((p6 != v0_1.e) || ((v0_1.f != v2_5) || (v0_1.g != v3))) {
            v0_1.e = p6;
            v0_1.f = v2_5;
            v0_1.g = v3;
            v0_1.b(0);
            v0_1.invalidateSelf();
        }
        if (v1_1.getUseCompatPadding()) {
            int v6_4 = ((ly) p5.b);
            double v0_2 = v6_4.e;
            int v6_5 = v6_4.a;
            p5.y(((int) Math.ceil(((double) my.a(v0_2, v6_5, v1_1.getPreventCornerOverlap())))), ((int) Math.ceil(((double) my.b(v0_2, v6_5, v1_1.getPreventCornerOverlap())))), ((int) Math.ceil(((double) my.a(v0_2, v6_5, v1_1.getPreventCornerOverlap())))), ((int) Math.ceil(((double) my.b(v0_2, v6_5, v1_1.getPreventCornerOverlap())))));
            return;
        } else {
            p5.y(0, 0, 0, 0);
            return;
        }
    }

    public static final void a0(com.example.instatool.databinding.DialogClearDataBinding p6, lx p7, lx p8, k9 p9, com.example.instatool.browser.BrowserActivity p10)
    {
        d9 v0_3;
        int v2 = 0;
        if ((!p6.clearHistory.isChecked()) && ((!p6.clearCookies.isChecked()) && (!p6.clearCache.isChecked()))) {
            v0_3 = 0;
        } else {
            v0_3 = 1;
        }
        q8 v7_1 = p7.a;
        if (v7_1 == null) {
            io.T("dialog");
            throw 0;
        } else {
            q8 v7_4 = ((j2) v7_1).f.i;
            if (v7_4 != null) {
                v7_4.setEnabled(v0_3);
            }
            q8 v7_5 = p6.rangeNote;
            v7_5.getClass();
            if ((p8.a == jb.ALL_TIME) || ((!p6.clearCookies.isChecked()) && (!p6.clearCache.isChecked()))) {
                v2 = 8;
            }
            v7_5.setVisibility(v2);
            p9.c(new d9(jb.since$default(((jb) p8.a), 0, 1, 0), 1), new q8(p6, p10));
            return;
        }
    }

    public static java.util.List b0(String p3, org.json.JSONObject p4)
    {
        p4.getClass();
        qh v3_1 = p4.optJSONArray(p3);
        if (v3_1 != null) {
            java.util.Iterator v4_3 = c8.Z(0, v3_1.length());
            java.util.ArrayList v0_0 = new java.util.ArrayList();
            java.util.Iterator v4_1 = v4_3.iterator();
            while(true) {
                int v1_1 = ((fo) v4_1);
                if (!v1_1.c) {
                    break;
                }
                int v1_3 = v3_1.optString(v1_1.nextInt());
                v1_3.getClass();
                if (v1_3.length() <= 0) {
                    v1_3 = 0;
                }
                if (v1_3 != 0) {
                    v0_0.add(v1_3);
                }
            }
            return v0_0;
        } else {
            return qh.a;
        }
    }

    public static final int c(int p3, int p4, int[] p5)
    {
        p5.getClass();
        int v3_1 = (p3 - 1);
        int v0 = 0;
        while (v0 <= v3_1) {
            int v1_1 = ((v0 + v3_1) >> 1);
            int v2 = p5[v1_1];
            if (v2 >= p4) {
                if (v2 <= p4) {
                    return v1_1;
                } else {
                    v3_1 = (v1_1 - 1);
                }
            } else {
                v0 = (v1_1 + 1);
            }
        }
        return (~ v0);
    }

    public static final String c0(Object[] p3, int p4, int p5, l p6)
    {
        StringBuilder v0_1 = new StringBuilder(((p5 * 3) + 2));
        v0_1.append("[");
        int v1_2 = 0;
        while (v1_2 < p5) {
            if (v1_2 > 0) {
                v0_1.append(", ");
            }
            String v2_2 = p3[(p4 + v1_2)];
            if (v2_2 != p6) {
                v0_1.append(v2_2);
            } else {
                v0_1.append("(this Collection)");
            }
            v1_2++;
        }
        v0_1.append("]");
        return v0_1.toString();
    }

    public static final int d(long[] p4, int p5, long p6)
    {
        p4.getClass();
        int v5_1 = (p5 - 1);
        int v0 = 0;
        while (v0 <= v5_1) {
            int v1_1 = ((v0 + v5_1) >> 1);
            long v2_1 = p4[v1_1] cmp p6;
            if (v2_1 >= 0) {
                if (v2_1 <= 0) {
                    return v1_1;
                } else {
                    v5_1 = (v1_1 - 1);
                }
            } else {
                v0 = (v1_1 + 1);
            }
        }
        return (~ v0);
    }

    public static void d0(Object p1, String p2)
    {
        ClassCastException v2_2 = new ClassCastException(g.e(p1.getClass().getName(), " cannot be cast to ", p2));
        io.L(v2_2, p40.getName());
        throw v2_2;
    }

    public static String e0(String p11)
    {
        StringBuilder v0_4;
        StringBuilder v0_3 = org.json.JSONObject.quote("PROBLEM:");
        int v1_7 = new StringBuilder("\n            (function(){\n              function vis(el){\n                if(!el) return false;\n                var r=el.getBoundingClientRect(), s=window.getComputedStyle(el);\n                return r.width>0 && r.height>0 && s.display!==\'none\' && s.visibility!==\'hidden\' && Number(s.opacity)!==0;\n              }\n              function norm(s){ return ((s||\'\')+\'\').replace(/[\\u2018\\u2019]/g,\"\'\").replace(/[ \\t\\u00a0]+/g,\' \').trim(); }\n              function setVal(el,val){\n                try{ el.focus(); }catch(e){}\n                var d=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,\'value\')\n                  ||Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,\'value\');\n                if(d&&d.set) d.set.call(el,val); else el.value=val;\n                try{ el.dispatchEvent(new InputEvent(\'input\',{bubbles:true,cancelable:true,inputType:\'insertReplacementText\',data:val})); }\n                catch(e){ el.dispatchEvent(new Event(\'input\',{bubbles:true})); }\n                el.dispatchEvent(new Event(\'change\',{bubbles:true}));\n              }\n              // Instagram\'s buttons are divs that ignore el.click(). The sign-up screens (Meta \"Bloks\",\n              // class wbloks_*) only react to touchstart/touchend; the login page to the pointer sequence.\n              function tap(el){\n                try{ el.scrollIntoView({block:\'center\',inline:\'center\'}); }catch(e){}\n                var r=el.getBoundingClientRect(), x=r.left+r.width/2, y=r.top+r.height/2;\n                var t=document.elementFromPoint(x,y);\n                if(!t||!el.contains(t)) t=el;\n                if(el.closest(\'[class*=\"wbloks\"]\')){\n                  var touch=new Touch({identifier:Date.now(),target:t,clientX:x,clientY:y,pageX:x+scrollX,pageY:y+scrollY,\n                                       screenX:x,screenY:y,radiusX:5,radiusY:5,force:1});\n                  var to=function(list){ return {bubbles:true,cancelable:true,composed:true,view:window,\n                                                 touches:list,targetTouches:list,changedTouches:[touch]}; };\n                  t.dispatchEvent(new TouchEvent(\'touchstart\',to([touch])));\n                  setTimeout(function(){ t.dispatchEvent(new TouchEvent(\'touchend\',to([]))); },80);\n                  return;\n                }\n                var o={bubbles:true,cancelable:true,composed:true,view:window,clientX:x,clientY:y,\n                       button:0,buttons:1,pointerId:1,pointerType:\'touch\',isPrimary:true};\n                t.dispatchEvent(new PointerEvent(\'pointerdown\',o));\n                t.dispatchEvent(new MouseEvent(\'mousedown\',o));\n                o.buttons=0;\n                t.dispatchEvent(new PointerEvent(\'pointerup\',o));\n                t.dispatchEvent(new MouseEvent(\'mouseup\',o));\n                t.dispatchEvent(new MouseEvent(\'click\',o));\n              }\n              // The visible element with the shortest matching text, so page containers never win.\n              function best(selector, match){\n                var els=document.querySelectorAll(selector), pick=null, len=1e9;\n                for(var i=0;i<els.length;i++){\n                  var el=els[i];\n                  if(!vis(el)||el.disabled||el.getAttribute(\'aria-disabled\')===\'true\') continue;\n                  var t=norm(el.innerText||el.value||el.getAttribute(\'aria-label\')||el.textContent).replace(/\\s+/g,\' \').toLowerCase();\n                  if(t&&match(t)&&t.length<len){ pick=el; len=t.length; }\n                }\n                return pick;\n              }\n              // Phrases are tried in order, so \'allow and continue\' wins over a plain \'continue\'.\n              function clickText(texts){\n                for(var j=0;j<texts.length;j++){\n                  var el=best(\'button,[role=\"button\"],a,input[type=\"submit\"]\', function(t){\n                    return t.length<=40 && t.indexOf(texts[j])>-1;\n                  });\n                  if(el){ tap(el); return true; }\n                }\n                return false;\n              }\n              // Exact labels only: \"Continue without Meta account\" must never match \"continue\".\n              function tapLabel(labels){\n                for(var j=0;j<labels.length;j++){\n                  var el=best(\'button,[role=\"button\"],input[type=\"submit\"]\', function(t){ return t===labels[j]; });\n                  if(!el) continue;\n                  // \"I agree\" stays labelled while its own spinner is up. Tapping it again aborts the\n                  // consent request, so the spinner never finishes. One tap, then leave it alone.\n                  // If it is still here 15s later, the caller goes back instead of tapping again.\n                  if(labels[j]===\"i agree\"||labels[j]===\"agree\"){\n                    window.__instaToolSawAgree=true;\n                    var spinning=el.getAttribute(\"aria-busy\")===\"true\"||!!el.querySelector(\"[role=progressbar]\");\n                    var tappedAt=window.__instaToolAgreeTap||0;\n                    if(!tappedAt){\n                      window.__instaToolAgreeTap=Date.now();\n                      if(spinning) return \"\";\n                    } else if(Date.now()-tappedAt<15000) {\n                      return \"\";\n                    } else {\n                      return \"__stuck__\";\n                    }\n                  }\n                  tap(el);\n                  return labels[j];\n                }\n                return \'\';\n              }\n              function clickable(el){\n                var c=el;\n                while(c&&c!==document.body&&c.getAttribute(\'role\')!==\'button\'&&c.tagName!==\'BUTTON\'&&c.tagName!==\'A\'&&c.tagName!==\'LI\'){ c=c.parentElement; }\n                return c&&c!==document.body?c:el;\n              }\n              function clickContains(text){\n                var el=best(\'[role=\"button\"],button,li,a,div,span\', function(t){ return t.indexOf(text)>-1; });\n                if(!el) return false;\n                tap(clickable(el));\n                return true;\n              }\n              // The account card in the \"No Instagram account/profile found\" popup. It shows the email\n              // or only the Meta account\'s name (\"Jessica Pugh \u00b7 Meta Horizon\").\n              function accountOption(email){\n                var ds=document.querySelectorAll(\'[role=\"dialog\"]\');\n                for(var i=0;i<ds.length;i++){\n                  if(!/no instagram (account|profile) found/.test(norm(ds[i].innerText).toLowerCase())) continue;\n                  var cards=[].filter.call(ds[i].querySelectorAll(\'[role=\"button\"]\'),function(b){\n                    if(!vis(b)) return false;\n                    var l=norm(b.innerText||b.getAttribute(\'aria-label\')).replace(/\\s+/g,\' \').toLowerCase();\n                    return l&&!/^(find (another )?account|close|cancel|ok|back)$/.test(l);\n                  });\n                  var withEmail=cards.filter(function(b){\n                    return (norm(b.innerText)+\' \'+(b.getAttribute(\'aria-label\')||\'\')).toLowerCase().indexOf(email)>-1;\n                  });\n                  return withEmail[0]||cards[cards.length-1]||null;\n                }\n                return null;\n              }\n              // Popup text without its button labels (\"Sign up\", \"Try again\").\n              function popupText(d){\n                var buttons=[].map.call(d.querySelectorAll(\'button,[role=\"button\"]\'),function(b){ return norm(b.innerText); });\n                var lines=norm(d.innerText).split(\'\\n\').map(function(l){ return l.trim(); }).filter(Boolean);\n                var kept=lines.filter(function(l){ return buttons.indexOf(l)<0; });\n                return (kept.length?kept:lines).join(\'\\n\');\n              }\n              function allowCookies(){\n                if(norm(document.body.innerText).toLowerCase().indexOf(\'cookie\')<0) return false;\n                var labels=[\'allow all cookies\',\'allow cookies\',\'accept all cookies\',\'accept cookies\',\'allow essential and optional cookies\'];\n                var buttons=document.querySelectorAll(\'button,[role=\"button\"],input[type=\"submit\"]\');\n                for(var i=0;i<buttons.length;i++){\n                  var b=buttons[i];\n                  if(!vis(b)||b.disabled||b.getAttribute(\'aria-disabled\')===\'true\') continue;\n                  var t=norm(b.innerText||b.value||b.getAttribute(\'aria-label\')||\'\').replace(/\\s+/g,\' \').toLowerCase();\n                  if(t.length>80||/decline|reject|deny|only allow|essential only/.test(t)) continue;\n                  for(var j=0;j<labels.length;j++){\n                    if(t===labels[j]){ b.click(); return true; }\n                  }\n                }\n                return false;\n              }\n              function problem(){\n                var re=/(can\'?t|cannot|couldn\'?t) find (an |your )?account/i;\n                var ds=document.querySelectorAll(\'[role=\"dialog\"],[role=\"alertdialog\"]\');\n                for(var i=0;i<ds.length;i++){\n                  if(vis(ds[i])&&re.test(norm(ds[i].innerText))) return popupText(ds[i]);\n                }\n                var found=\'\', all=document.querySelectorAll(\'div,p,span,h1,h2\');\n                for(var k=0;k<all.length;k++){\n                  if(!vis(all[k])) continue;\n                  var tx=norm(all[k].innerText);\n                  if(re.test(tx)&&tx.length>0&&tx.length<400&&(found===\'\'||tx.length<found.length)) found=tx;\n                }\n                return found;\n              }\n              // Sync exact-label button lookup. Kotlin re-polls when the target is not ready yet\n              // (evaluateJavascript cannot await Promises / async IIFEs).\n              function findExactBtn(labels, root){\n                root=root||document;\n                var els=root.querySelectorAll(\'[role=\"button\"],button,input[type=\"submit\"],div[role=\"button\"],span[role=\"button\"]\');\n                for(var j=0;j<labels.length;j++){\n                  for(var i=0;i<els.length;i++){\n                    var b=els[i];\n                    if(!vis(b)||b.getAttribute(\'aria-disabled\')===\'true\'||b.disabled) continue;\n                    var lab=norm(b.innerText||b.value||b.getAttribute(\'aria-label\')||\'\').replace(/\\s+/g,\' \').toLowerCase();\n                    if(lab===labels[j]) return b;\n                  }\n                }\n                return null;\n              }\n              if(allowCookies()) return \'cookies\';\n              var p=problem();\n              if(p) return ");
        v1_7.append(v0_3);
        v1_7.append("+p;\n              ");
        v1_7.append(p11);
        v1_7.append("\n            })();\n        ");
        String v11_3 = v1_7.toString();
        StringBuilder v0_2 = new hq(v11_3);
        if (v0_2.hasNext()) {
            int v1_1 = v0_2.next();
            if (v0_2.hasNext()) {
                java.util.ArrayList v2_2 = new java.util.ArrayList();
                v2_2.add(v1_1);
                while (v0_2.hasNext()) {
                    v2_2.add(v0_2.next());
                }
                v0_4 = v2_2;
            } else {
                v0_4 = io.y(v1_1);
            }
        } else {
            v0_4 = qh.a;
        }
        int v1_6 = new java.util.ArrayList();
        java.util.ArrayList v2_4 = v0_4.iterator();
        while (v2_4.hasNext()) {
            int v3_0 = v2_4.next();
            if (!m10.G(((String) v3_0))) {
                v1_6.add(v3_0);
            }
        }
        java.util.ArrayList v2_6 = new java.util.ArrayList(tb.e0(v1_6));
        int v3_3 = v1_6.size();
        String v4_3 = 0;
        java.util.ArrayList v5_0 = 0;
        while (v5_0 < v3_3) {
            String v6_1 = v1_6.get(v5_0);
            v5_0++;
            String v6_2 = ((String) v6_1);
            int v7_1 = v6_2.length();
            int v8 = 0;
            while (v8 < v7_1) {
                if (io.x(v6_2.charAt(v8))) {
                    v8++;
                }
                if (v8 == -1) {
                    v8 = v6_2.length();
                }
                v2_6.add(Integer.valueOf(v8));
            }
            v8 = -1;
        }
        java.util.ArrayList v2_9;
        int v1_8 = v2_6.iterator();
        if (v1_8.hasNext()) {
            v2_9 = ((Comparable) v1_8.next());
            while (v1_8.hasNext()) {
                java.util.ArrayList v5_3 = ((Comparable) v1_8.next());
                if (v2_9.compareTo(v5_3) > 0) {
                    v2_9 = v5_3;
                }
            }
        } else {
            v2_9 = 0;
        }
        int v1_9;
        java.util.ArrayList v2_10 = ((Integer) v2_9);
        if (v2_10 == null) {
            v1_9 = 0;
        } else {
            v1_9 = v2_10.intValue();
        }
        String v11_4 = v11_3.length();
        v0_4.size();
        java.util.ArrayList v2_12 = (v0_4.size() - 1);
        java.util.ArrayList v5_5 = new java.util.ArrayList();
        StringBuilder v0_6 = v0_4.iterator();
        while (v0_6.hasNext()) {
            String v6_6 = v0_6.next();
            int v7_0 = (v4_3 + 1);
            if (v4_3 < null) {
                sb.d0();
                throw 0;
            } else {
                String v4_2;
                String v6_0 = ((String) v6_6);
                if (((v4_3 != null) && (v4_3 != v2_12)) || (!m10.G(v6_0))) {
                    v6_0.getClass();
                    if (v1_9 < 0) {
                        e6.b(v1_9, "Requested character count ");
                        return 0;
                    } else {
                        String v4_1 = v6_0.length();
                        if (v1_9 <= v4_1) {
                            v4_1 = v1_9;
                        }
                        v4_2 = v6_0.substring(v4_1);
                    }
                } else {
                    v4_2 = 0;
                }
                if (v4_2 != null) {
                    v5_5.add(v4_2);
                }
                v4_3 = v7_0;
            }
        }
        StringBuilder v0_8 = new StringBuilder(v11_4);
        rb.k0(v5_5, v0_8, "\n");
        return v0_8.toString();
    }

    public static void f0(android.content.Context p18, java.util.concurrent.Executor p19, lv p20, boolean p21)
    {
        Throwable v0_52 = p18.getApplicationContext();
        Throwable v2_1 = v0_52.getPackageName();
        int v3_10 = v0_52.getApplicationInfo();
        Throwable v4_6 = v0_52.getAssets();
        int v6_4 = new java.io.File(v3_10.sourceDir).getName();
        try {
            android.content.pm.PackageInfo v10 = p18.getPackageManager().getPackageInfo(v2_1, 0);
            java.io.File v11 = p18.getFilesDir();
        } catch (Throwable v0_41) {
            p20.f(7, v0_41);
            rv.c(p18, 0);
            return;
        }
        if (p21) {
            int v9_11;
            int v7_0;
            Throwable v0_67 = new StringBuilder("Installing profile for ");
            v0_67.append(p18.getPackageName());
            android.util.Log.d("ProfileInstaller", v0_67.toString());
            long v13_2 = c8.n;
            int v7_19 = new java.io.File(new java.io.File("/data/misc/profiles/cur/0", v2_1), "primary.prof");
            int v3_12 = v4_6;
            Throwable v2_0 = new le(v3_12, p19, p20, v6_4, v7_19);
            Throwable v4_8 = v2_0.c;
            if (v4_8 != null) {
                if (!v7_19.exists()) {
                    try {
                        if (!v7_19.createNewFile()) {
                            v2_0.b(4, 0);
                            v7_0 = 1;
                            v9_11 = 0;
                            if ((v9_11 == 0) || (!p21)) {
                                int v9_12 = 0;
                            } else {
                                v9_12 = v7_0;
                            }
                            rv.c(p18, v9_12);
                            return;
                        }
                    } catch (java.io.IOException) {
                        v7_0 = 1;
                        v2_0.b(4, 0);
                    }
                } else {
                    if (!v7_19.canWrite()) {
                        v2_0.b(4, 0);
                    }
                }
                v2_0.f = 1;
                try {
                    int v7_1 = v2_0.a(v3_12, "dexopt/baseline.prof");
                } catch (Throwable v0_3) {
                    p20.f(6, v0_3);
                    v7_1 = 0;
                } catch (Throwable v0_2) {
                    p20.f(7, v0_2);
                }
                if (v7_1 != 0) {
                    try {
                        if (!java.util.Arrays.equals(v13_2, p40.T(v7_1, 4))) {
                            throw new IllegalStateException("Invalid magic");
                        } else {
                            int v9_1 = c8.S(v7_1, p40.T(v7_1, 4), v2_0.e);
                            try {
                                v7_1.close();
                            } catch (Throwable v0_15) {
                                p20.f(7, v0_15);
                            }
                        }
                    } catch (Throwable v0_11) {
                        p20.f(7, v0_11);
                        try {
                            v7_1.close();
                        } catch (Throwable v0_14) {
                            p20.f(7, v0_14);
                        }
                        v9_1 = 0;
                    } catch (Throwable v0_10) {
                        p20.f(8, v0_10);
                    } catch (Throwable v0_12) {
                        Throwable v1_1 = v0_12;
                        try {
                            v7_1.close();
                        } catch (Throwable v0_13) {
                            p20.f(7, v0_13);
                        }
                        throw v1_1;
                    }
                    v2_0.g = v9_1;
                }
                Throwable v0_16 = v2_0.g;
                if (v0_16 != null) {
                    int v7_2 = android.os.Build$VERSION.SDK_INT;
                    if ((v7_2 >= 31) || ((v7_2 == 24) || (v7_2 == 25))) {
                        try {
                            Throwable v0_23;
                            int v3_1 = v2_0.a(v3_12, "dexopt/baseline.profm");
                        } catch (Throwable v0_26) {
                            p20.f(9, v0_26);
                            v0_23 = 0;
                            if (v0_23 != null) {
                                v2_0 = v0_23;
                            }
                        } catch (Throwable v0_25) {
                            p20.f(7, v0_25);
                        } catch (Throwable v0_24) {
                            v2_0.g = 0;
                            p20.f(8, v0_24);
                        }
                        if (v3_1 == 0) {
                            if (v3_1 == 0) {
                            } else {
                                v3_1.close();
                            }
                        } else {
                            try {
                                if (!java.util.Arrays.equals(c8.o, p40.T(v3_1, 4))) {
                                    throw new IllegalStateException("Invalid magic");
                                } else {
                                    v2_0.g = c8.P(v3_1, p40.T(v3_1, 4), v4_8, v0_16);
                                    v3_1.close();
                                    v0_23 = v2_0;
                                }
                            } catch (Throwable v0_21) {
                                Throwable v4_0 = v0_21;
                                try {
                                    v3_1.close();
                                } catch (Throwable v0_22) {
                                    v4_0.addSuppressed(v0_22);
                                }
                                throw v4_0;
                            }
                        }
                    }
                }
                int v3_3 = v2_0.b;
                Throwable v0_27 = v2_0.g;
                Throwable v4_1 = v2_0.c;
                if ((v0_27 != null) && (v4_1 != null)) {
                    if (!v2_0.f) {
                        e6.j("This device doesn\'t support aot. Did you call deviceSupportsAotProfile()?");
                        return;
                    } else {
                        try {
                            int v7_9 = new java.io.ByteArrayOutputStream();
                            try {
                                v7_9.write(v13_2);
                                v7_9.write(v4_1);
                            } catch (Throwable v0_31) {
                                Throwable v4_2 = v0_31;
                                try {
                                    v7_9.close();
                                } catch (Throwable v0_32) {
                                    v4_2.addSuppressed(v0_32);
                                }
                                throw v4_2;
                            }
                            if (c8.Y(v7_9, v4_1, v0_27)) {
                                v2_0.h = v7_9.toByteArray();
                                v7_9.close();
                                v2_0.g = 0;
                            } else {
                                v3_3.f(5, 0);
                                v2_0.g = 0;
                                v7_9.close();
                            }
                        } catch (Throwable v0_34) {
                            v3_3.f(7, v0_34);
                        } catch (Throwable v0_33) {
                            v3_3.f(8, v0_33);
                        }
                    }
                }
                int v6_7;
                Throwable v0_35 = v2_0.h;
                if (v0_35 != null) {
                    if (!v2_0.f) {
                        e6.j("This device doesn\'t support aot. Did you call deviceSupportsAotProfile()?");
                        return;
                    } else {
                        try {
                            int v3_7 = new java.io.ByteArrayInputStream(v0_35);
                            try {
                                Throwable v4_4 = new java.io.FileOutputStream(v2_0.d);
                                try {
                                    Throwable v5_2 = v4_4.getChannel();
                                    try {
                                        int v6_5 = v5_2.tryLock();
                                        try {
                                            if ((v6_5 == 0) || (!v6_5.isValid())) {
                                                v7_0 = 1;
                                                throw new java.io.IOException("Unable to acquire a lock on the underlying file channel.");
                                            } else {
                                                Throwable v0_47 = new byte[512];
                                                while(true) {
                                                    int v7_10 = v3_7.read(v0_47);
                                                    if (v7_10 <= 0) {
                                                        break;
                                                    }
                                                    v4_4.write(v0_47, 0, v7_10);
                                                }
                                                v7_0 = 1;
                                                v2_0.b(1, 0);
                                                v6_5.close();
                                                v5_2.close();
                                                v4_4.close();
                                                v3_7.close();
                                                v2_0.h = 0;
                                                v2_0.g = 0;
                                                v6_7 = 1;
                                                if (v6_7 != 0) {
                                                    p40.J(v10, v11);
                                                }
                                                v9_11 = v6_7;
                                            }
                                        } catch (Throwable v0_48) {
                                            v7_0 = 1;
                                        } catch (Throwable v0_48) {
                                        } catch (Throwable v0_42) {
                                            int v6_6 = v0_42;
                                            if (v5_2 != null) {
                                                try {
                                                    v5_2.close();
                                                } catch (Throwable v0_50) {
                                                    v6_6.addSuppressed(v0_50);
                                                }
                                            }
                                            throw v6_6;
                                        }
                                        int v9_9 = v0_48;
                                        if (v6_5 != 0) {
                                            try {
                                                v6_5.close();
                                            } catch (Throwable v0_49) {
                                                v9_9.addSuppressed(v0_49);
                                            }
                                        }
                                        throw v9_9;
                                    } catch (Throwable v0_42) {
                                        v7_0 = 1;
                                    } catch (Throwable v0_40) {
                                        Throwable v5_3 = v0_40;
                                        try {
                                            v4_4.close();
                                        } catch (Throwable v0_51) {
                                            v5_3.addSuppressed(v0_51);
                                        }
                                        throw v5_3;
                                    }
                                } catch (Throwable v0_40) {
                                    v7_0 = 1;
                                } catch (Throwable v0_39) {
                                    Throwable v4_5 = v0_39;
                                    try {
                                        v3_7.close();
                                    } catch (Throwable v0_53) {
                                        v4_5.addSuppressed(v0_53);
                                    }
                                    throw v4_5;
                                }
                            } catch (Throwable v0_39) {
                                v7_0 = 1;
                            } catch (Throwable v0_37) {
                                v2_0.b(6, v0_37);
                                v2_0.h = 0;
                                v2_0.g = 0;
                                v6_7 = 0;
                            } catch (Throwable v0_36) {
                                v2_0.b(7, v0_36);
                            }
                        } catch (Throwable v0_37) {
                            v7_0 = 1;
                        } catch (Throwable v0_36) {
                            v7_0 = 1;
                        } catch (Throwable v0_55) {
                            v2_0.h = 0;
                            v2_0.g = 0;
                            throw v0_55;
                        }
                    }
                } else {
                    v6_7 = 0;
                    v7_0 = 1;
                }
            } else {
                v2_0.b(3, Integer.valueOf(android.os.Build$VERSION.SDK_INT));
            }
        } else {
            Throwable v0_62;
            Throwable v0_56 = new java.io.File(v11, "profileinstaller_profileWrittenFor_lastUpdateTime.dat");
            try {
                if (v0_56.exists()) {
                    int v7_14 = new java.io.DataInputStream(new java.io.FileInputStream(v0_56));
                    try {
                        long v14_2 = v7_14.readLong();
                    } catch (Throwable v0_59) {
                        long v13_0 = v0_59;
                        try {
                            v7_14.close();
                        } catch (Throwable v0_60) {
                            v13_0.addSuppressed(v0_60);
                        }
                        throw v13_0;
                    }
                    v7_14.close();
                    if (v14_2 != v10.lastUpdateTime) {
                        v0_62 = 0;
                    } else {
                        v0_62 = 1;
                    }
                    if (v0_62 != null) {
                        p20.f(2, 0);
                    }
                } else {
                    v0_62 = 0;
                }
            } catch (java.io.IOException) {
            }
            if (v0_62 != null) {
                Throwable v0_64 = new StringBuilder("Skipping profile installation for ");
                v0_64.append(p18.getPackageName());
                android.util.Log.d("ProfileInstaller", v0_64.toString());
                rv.c(p18, 0);
            }
        }
        return;
    }

    public static void g0(java.io.OutputStream p6, long p7, int p9)
    {
        byte[] v0 = new byte[p9];
        int v1 = 0;
        while (v1 < p9) {
            v0[v1] = ((byte) ((int) ((p7 >> (v1 * 8)) & 255)));
            v1++;
        }
        p6.write(v0);
        return;
    }

    public static void h0(java.io.ByteArrayOutputStream p2, int p3)
    {
        p40.g0(p2, ((long) p3), 2);
        return;
    }

    public static void i(android.content.Context p1, android.util.AttributeSet p2, int p3, int p4)
    {
        int v2_2 = p1.obtainStyledAttributes(p2, yv.D, p3, p4);
        String v3_7 = v2_2.getBoolean(1, 0);
        v2_2.recycle();
        if (v3_7 != null) {
            int v2_1 = new android.util.TypedValue();
            if ((!p1.getTheme().resolveAttribute(2130903708, v2_1, 1)) || ((v2_1.type == 18) && (v2_1.data == 0))) {
                p40.l(p1, p40.k, "Theme.MaterialComponents");
            }
        }
        p40.l(p1, p40.j, "Theme.AppCompat");
        return;
    }

    public static void j(Object p0, String p1)
    {
        if (p0 == null) {
            throw new NullPointerException(p1);
        } else {
            return;
        }
    }

    public static varargs void k(android.content.Context p5, android.util.AttributeSet p6, int[] p7, int p8, int p9, int[] p10)
    {
        android.content.res.TypedArray v0_1 = p5.obtainStyledAttributes(p6, yv.D, p8, p9);
        int v2 = 0;
        if (v0_1.getBoolean(2, 0)) {
            if (p10.length != 0) {
                String v5_1 = p5.obtainStyledAttributes(p6, p7, p8, p9);
                int v7_1 = 0;
                while (v7_1 < p10.length) {
                    if (v5_1.getResourceId(p10[v7_1], -1) != -1) {
                        v7_1++;
                    } else {
                        v5_1.recycle();
                    }
                }
                v5_1.recycle();
                v2 = 1;
            } else {
                if (v0_1.getResourceId(0, -1) != -1) {
                }
            }
            v0_1.recycle();
            if (v2 == 0) {
                e6.g("This component requires that you specify a valid TextAppearance attribute. Update your app theme to inherit from Theme.MaterialComponents (or a descendant).");
                return;
            } else {
                return;
            }
        } else {
            v0_1.recycle();
            return;
        }
    }

    public static void l(android.content.Context p2, int[] p3, String p4)
    {
        String v2_1 = p2.obtainStyledAttributes(p3);
        int v0 = 0;
        while (v0 < p3.length) {
            if (!v2_1.hasValue(v0)) {
                v2_1.recycle();
                e6.g(g.e("The style on this component requires your app theme to be ", p4, " (or a descendant)."));
                return;
            } else {
                v0++;
            }
        }
        v2_1.recycle();
        return;
    }

    public static int m(Comparable p0, Comparable p1)
    {
        if (p0 != p1) {
            if (p0 != 0) {
                if (p1 != null) {
                    return p0.compareTo(p1);
                } else {
                    return 1;
                }
            } else {
                return -1;
            }
        } else {
            return 0;
        }
    }

    public static int n(int p1, int p2)
    {
        return ac.e(p1, ((android.graphics.Color.alpha(p1) * p2) / 255));
    }

    public static android.graphics.drawable.Drawable o(android.graphics.drawable.Drawable p2, android.graphics.drawable.Drawable p3, int p4, int p5)
    {
        if (p2 != 0) {
            if (p3 != 0) {
                if (p4 == -1) {
                    p4 = p3.getIntrinsicWidth();
                    if (p4 == -1) {
                        p4 = p2.getIntrinsicWidth();
                    }
                }
                if (p5 == -1) {
                    p5 = p3.getIntrinsicHeight();
                    if (p5 == -1) {
                        p5 = p2.getIntrinsicHeight();
                    }
                }
                if ((p4 > p2.getIntrinsicWidth()) || (p5 > p2.getIntrinsicHeight())) {
                    int v4_2 = (((float) p4) / ((float) p5));
                    if (v4_2 < (((float) p2.getIntrinsicWidth()) / ((float) p2.getIntrinsicHeight()))) {
                        p5 = p2.getIntrinsicHeight();
                        p4 = ((int) (v4_2 * ((float) p5)));
                    } else {
                        int v5_6 = p2.getIntrinsicWidth();
                        p5 = ((int) (((float) v5_6) / v4_2));
                        p4 = v5_6;
                    }
                }
                android.graphics.drawable.LayerDrawable v0_9 = new android.graphics.drawable.LayerDrawable(new android.graphics.drawable.Drawable[] {p2, p3}));
                v0_9.setLayerSize(1, p4, p5);
                v0_9.setLayerGravity(1, 17);
                return v0_9;
            } else {
                return p2;
            }
        } else {
            return p3;
        }
    }

    public static byte[] p(byte[] p3)
    {
        java.util.zip.Deflater v0_1 = new java.util.zip.Deflater(1);
        Throwable v1_3 = new java.io.ByteArrayOutputStream();
        try {
            java.util.zip.DeflaterOutputStream v2_1 = new java.util.zip.DeflaterOutputStream(v1_3, v0_1);
            try {
                v2_1.write(p3);
            } catch (byte[] v3_3) {
                try {
                    v2_1.close();
                } catch (Throwable v1_1) {
                    v3_3.addSuppressed(v1_1);
                }
                throw v3_3;
            }
            v2_1.close();
            v0_1.end();
            return v1_3.toByteArray();
        } catch (byte[] v3_2) {
            v0_1.end();
            throw v3_2;
        }
    }

    public static float[] q(float[] p2, int p3)
    {
        if (p3 < null) {
            throw new IllegalArgumentException();
        } else {
            int v0_1 = p2.length;
            if (v0_1 < 0) {
                throw new ArrayIndexOutOfBoundsException();
            } else {
                float[] v3_1 = new float[p3];
                System.arraycopy(p2, 0, v3_1, 0, Math.min(p3, v0_1));
                return v3_1;
            }
        }
    }

    public static xu[] s(String p17)
    {
        RuntimeException v1_3 = new java.util.ArrayList();
        int v2_2 = 0;
        char v5_1 = 0;
        int v4_0 = 1;
        while (v4_0 < p17.length()) {
            while (v4_0 < p17.length()) {
                float[] v6_1 = p17.charAt(v4_0);
                if (((((v6_1 - 90) * (v6_1 - 65)) <= 0) || (((v6_1 - 122) * (v6_1 - 97)) <= 0)) && ((v6_1 != 101) && (v6_1 != 69))) {
                    break;
                }
                v4_0++;
            }
            char v5_3 = p17.substring(v5_1, v4_0).trim();
            if (!v5_3.isEmpty()) {
                if ((v5_3.charAt(v2_2) != 122) && (v5_3.charAt(v2_2) != 90)) {
                    float[] v6_6 = new float[v5_3.length()];
                    int v9_4 = v5_3.length();
                    int v11 = v2_2;
                    int v10_0 = 1;
                    while (v10_0 < v9_4) {
                        int v13 = v2_2;
                        int v14 = v13;
                        int v15 = v14;
                        int v16 = v15;
                        int v12 = v10_0;
                        while (v12 < v5_3.length()) {
                            float v3_6 = v5_3.charAt(v12);
                            if (v3_6 == 32) {
                                v13 = 0;
                                v15 = 1;
                            } else {
                                if ((v3_6 == 69) || (v3_6 == 101)) {
                                    v13 = 1;
                                } else {
                                    switch (v3_6) {
                                        case 45:
                                            if ((v12 == v10_0) || (v13 != 0)) {
                                                v13 = 0;
                                            } else {
                                                v13 = 0;
                                                v15 = 1;
                                                v16 = 1;
                                            }
                                            break;
                                        case 46:
                                            if (v14 != 0) {
                                            } else {
                                                v13 = 0;
                                                v14 = 1;
                                            }
                                            break;
                                        default:
                                    }
                                }
                            }
                            if (v15 == 0) {
                                v12++;
                            } else {
                                break;
                            }
                        }
                        if (v10_0 < v12) {
                            int v2_1 = (v11 + 1);
                            v6_6[v11] = Float.parseFloat(v5_3.substring(v10_0, v12));
                            v11 = v2_1;
                        }
                        if (v16 == 0) {
                            v10_0 = (v12 + 1);
                        } else {
                            v10_0 = v12;
                        }
                        v2_2 = 0;
                    }
                    float v3_3 = p40.q(v6_6, v11);
                    v2_2 = 0;
                } else {
                    v3_3 = new float[v2_2];
                }
                v1_3.add(new xu(v5_3.charAt(v2_2), v3_3));
            }
            v5_1 = v4_0;
            v4_0++;
            v2_2 = 0;
        }
        if (((v4_0 - v5_1) != 1) || (v5_1 >= p17.length())) {
            int v2_9 = 0;
        } else {
            v2_9 = 0;
            float v3_4 = new float[0];
            v1_3.add(new xu(p17.charAt(v5_1), v3_4));
        }
        NumberFormatException v0_3 = new xu[v2_9];
        return ((xu[]) v1_3.toArray(v0_3));
    }

    public static android.graphics.drawable.Drawable t(android.graphics.drawable.Drawable p0, android.content.res.ColorStateList p1, android.graphics.PorterDuff$Mode p2)
    {
        if (p0 != null) {
            if (p1 != null) {
                p0 = p0.mutate();
                if (p2 != null) {
                    p0.setTintMode(p2);
                }
            }
            return p0;
        } else {
            return 0;
        }
    }

    public static java.util.LinkedHashMap u(qi p5)
    {
        java.util.Map$Entry v1_5;
        java.util.LinkedHashMap v0_1 = new java.util.LinkedHashMap();
        switch (p5.a) {
            case 0:
                v1_5 = p5.b.iterator();
                break;
            default:
                v1_5 = p5.b.iterator();
        }
        while (v1_5.hasNext()) {
            Integer v2_8;
            Integer v2_6 = v1_5.next();
            switch (p5.a) {
                case 0:
                    v2_8 = ((hi) v2_6).b;
                    break;
                default:
                    v2_8 = ((hi) v2_6).b;
            }
            kx v3_3 = v0_1.get(v2_8);
            if ((v3_3 == null) && (!v0_1.containsKey(v2_8))) {
                v3_3 = new kx();
            }
            kx v3_5 = ((kx) v3_3);
            v3_5.a = (v3_5.a + 1);
            v0_1.put(v2_8, v3_5);
        }
        String v5_2 = v0_1.entrySet().iterator();
        while (v5_2.hasNext()) {
            java.util.Map$Entry v1_3 = ((java.util.Map$Entry) v5_2.next());
            v1_3.getClass();
            if (((v1_3 instanceof so)) && (!(v1_3 instanceof ir))) {
                p40.d0(v1_3, "kotlin.collections.MutableMap.MutableEntry");
                throw 0;
            } else {
                v1_3.setValue(Integer.valueOf(((kx) v1_3.getValue()).a));
            }
        }
        if ((v0_1 instanceof so)) {
            p40.d0(v0_1, "kotlin.collections.MutableMap");
            throw 0;
        } else {
            return v0_1;
        }
    }

    public static int[] v(int[] p3)
    {
        int v0_0 = 0;
        while (v0_0 < p3.length) {
            int v1_1 = p3[v0_0];
            if (v1_1 != 16842912) {
                if (v1_1 != 0) {
                    v0_0++;
                } else {
                    int[] v3_2 = ((int[]) p3.clone());
                    v3_2[v0_0] = 16842912;
                    return v3_2;
                }
            } else {
                return p3;
            }
        }
        int v0_3 = java.util.Arrays.copyOf(p3, (p3.length + 1));
        v0_3[p3.length] = 16842912;
        return v0_3;
    }

    public static int w(android.content.Context p1, int p2, int p3)
    {
        int v1_2;
        android.util.TypedValue v2_1 = io.H(p1.getTheme(), p2);
        if (v2_1 == null) {
            v1_2 = 0;
        } else {
            int v1_1;
            int v0_1 = v2_1.resourceId;
            if (v0_1 == 0) {
                v1_1 = v2_1.data;
            } else {
                v1_1 = p1.getColor(v0_1);
            }
            v1_2 = Integer.valueOf(v1_1);
        }
        if (v1_2 == 0) {
            return p3;
        } else {
            return v1_2.intValue();
        }
    }

    public static int x(android.view.View p2, int p3)
    {
        android.content.Context v0 = p2.getContext();
        int v2_5 = io.K(p3, p2.getContext(), p2.getClass().getCanonicalName());
        int v3_1 = v2_5.resourceId;
        if (v3_1 == 0) {
            return v2_5.data;
        } else {
            return v0.getColor(v3_1);
        }
    }

    public static android.content.res.ColorStateList y(android.graphics.drawable.Drawable p2)
    {
        if (!(p2 instanceof android.graphics.drawable.ColorDrawable)) {
            if ((android.os.Build$VERSION.SDK_INT < 29) || (!b0.n(p2))) {
                return 0;
            } else {
                return b0.c(b0.e(p2));
            }
        } else {
            return android.content.res.ColorStateList.valueOf(((android.graphics.drawable.ColorDrawable) p2).getColor());
        }
    }

    public static android.graphics.drawable.Drawable z(android.content.Context p1, int p2)
    {
        return ay.c().d(p1, p2);
    }

    public l0 A(b3 p1, Object p2)
    {
        return 0;
    }

    public abstract float B(android.graphics.drawable.Drawable p0);

    public abstract void M(Throwable p0);

    public void N(int p1)
    {
        return;
    }

    public abstract void O(android.graphics.Typeface p0);

    public abstract void P(ue p0);

    public abstract Object Q(int p0, android.content.Intent p1);

    public void R(t p1, t p2)
    {
        p1.b = p2;
        return;
    }

    public void S(t p1, Thread p2)
    {
        p1.a = p2;
        return;
    }

    public abstract void Z(android.graphics.drawable.Drawable p0, float p1);

    public abstract boolean a(Object p0, Object p1);

    public abstract boolean b(Object p0, Object p1);

    public void e(int p4)
    {
        new android.os.Handler(android.os.Looper.getMainLooper()).post(new ey(this, p4, 0));
        return;
    }

    public boolean f(u p2, q p3)
    {
        if (p2.b != p3) {
            return 0;
        } else {
            p2.b = q.b;
            return 1;
        }
    }

    public boolean g(u p1, Object p2, Object p3)
    {
        if (p1.a != p2) {
            return 0;
        } else {
            p1.a = p3;
            return 1;
        }
    }

    public boolean h(u p1, t p2, t p3)
    {
        if (p1.c != p2) {
            return 0;
        } else {
            p1.c = p3;
            return 1;
        }
    }

    public abstract android.content.Intent r(b3 p0, Object p1);
}
