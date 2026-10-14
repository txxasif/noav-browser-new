public final class Leo {
    public static final java.util.Set l0;
    public static final ox m0;
    public static final java.util.List n0;
    public boolean A;
    public long B;
    public boolean C;
    public String D;
    public String E;
    public boolean F;
    public int G;
    public boolean H;
    public String I;
    public final java.util.LinkedHashSet J;
    public int K;
    public int L;
    public int M;
    public String N;
    public boolean O;
    public long P;
    public String Q;
    public boolean R;
    public boolean S;
    public boolean T;
    public boolean U;
    public boolean V;
    public int W;
    public int X;
    public long Y;
    public boolean Z;
    public final com.example.instatool.browser.BrowserActivity a;
    public boolean a0;
    public final pm b;
    public long b0;
    public final java.util.concurrent.Executor c;
    public android.net.Uri c0;
    public final m8 d;
    public String d0;
    public final g9 e;
    public final java.util.LinkedHashSet e0;
    public final h9 f;
    public long f0;
    public bo g;
    public long g0;
    public CharSequence h;
    public boolean h0;
    public final android.os.Handler i;
    public boolean i0;
    public final android.webkit.CookieManager j;
    public final java.util.LinkedHashSet j0;
    public String k;
    public boolean k0;
    public java.util.Set l;
    public java.util.Set m;
    public final ov n;
    public boolean o;
    public boolean p;
    public boolean q;
    public String r;
    public java.util.List s;
    public int t;
    public bo u;
    public int v;
    public int w;
    public String x;
    public long y;
    public boolean z;

    static eo()
    {
        eo.l0 = jy.p(new bo[] {bo.LOADING, bo.FILLING, bo.WAITING, bo.SAVING}));
        eo.m0 = new ox("[A-Za-z0-9._]{1,30}");
        eo.n0 = sb.b0(new co[] {new co(2131689562, 1000, new e6(11)), new co(2131689563, 1200, new e6(12))}));
        return;
    }

    public eo(com.example.instatool.browser.BrowserActivity p1, pm p2, v20 p3, java.util.concurrent.Executor p4, m8 p5, g9 p6, h9 p7)
    {
        p4.getClass();
        this.a = p1;
        this.b = p2;
        this.c = p4;
        this.d = p5;
        this.e = p6;
        this.f = p7;
        this.g = bo.IDLE;
        ov v2_2 = p1.getString(2131689537);
        v2_2.getClass();
        this.h = v2_2;
        this.i = new android.os.Handler(android.os.Looper.getMainLooper());
        this.j = android.webkit.CookieManager.getInstance();
        this.l = jy.o(ao.COOKIES);
        this.m = sh.a;
        this.n = new ov(p1);
        this.s = qh.a;
        this.x = "";
        this.E = "";
        this.G = 2131689567;
        this.J = new java.util.LinkedHashSet();
        this.e0 = new java.util.LinkedHashSet();
        this.j0 = new java.util.LinkedHashSet();
        return;
    }

    public static String g(String p4)
    {
        String v1_0 = "";
        if (p4 != null) {
            if (!p4.startsWith("\"")) {
                return p4;
            } else {
                try {
                    StringBuilder v3_0 = new StringBuilder("[");
                    v3_0.append(p4);
                    v3_0.append("]");
                    hy v4_4 = new org.json.JSONArray(v3_0.toString()).getString(0);
                } catch (hy v4_5) {
                    v4_4 = new hy(v4_5);
                }
                if (!(v4_4 instanceof hy)) {
                    v1_0 = v4_4;
                }
                return ((String) v1_0);
            }
        } else {
            return "";
        }
    }

    public static void r(eo p7, nm p8, java.util.Map p9)
    {
        if (!p9.isEmpty()) {
            String v3 = p7.k;
            if (v3 != null) {
                p7.c.execute(new tn(p7, v3, p8, p9, 0));
                return;
            }
        }
        return;
    }

    public final android.webkit.WebView A()
    {
        android.webkit.WebView v0_2 = ((android.webkit.WebView) this.d.a());
        if (v0_2 != null) {
            if (!this.q) {
                this.r = v0_2.getSettings().getUserAgentString();
                this.q = 1;
            }
            String v4_4;
            android.webkit.WebSettings v1_2 = v0_2.getSettings();
            String v4_2 = android.webkit.WebSettings.getDefaultUserAgent(this.a);
            StringBuilder v2_1 = java.util.regex.Pattern.compile("Chrome/[\\d.]+");
            v2_1.getClass();
            v4_2.getClass();
            StringBuilder v2_2 = v2_1.matcher(v4_2);
            v2_2.getClass();
            String v4_3 = io.o(v2_2, 0, v4_2);
            if (v4_3 == null) {
                v4_4 = "Chrome/131.0.0.0";
            } else {
                v4_4 = v4_3.a.group();
                v4_4.getClass();
            }
            StringBuilder v2_4 = new StringBuilder("Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) ");
            v2_4.append(v4_4);
            v2_4.append(" Mobile Safari/537.36");
            v1_2.setUserAgentString(v2_4.toString());
            return v0_2;
        } else {
            return 0;
        }
    }

    public final void B(nm p14)
    {
        String v1_0 = bo.FILLING;
        if (this.g == v1_0) {
            boolean v2_6 = System.currentTimeMillis();
            int v4_0 = 0;
            if (v2_6 <= this.P) {
                String v0_1 = this.A();
                if (v0_1 != null) {
                    String v1_17;
                    this.x(v1_0, this.E(this.G));
                    int v5_4 = this.g0;
                    if ((v5_4 <= 0) || ((this.h0) || ((v2_6 - v5_4) <= 90000))) {
                        v1_17 = 0;
                    } else {
                        v1_17 = 1;
                    }
                    int v5_6 = this.Q;
                    Object v6 = 0;
                    if (v5_6 != 0) {
                        try {
                            Object v8_8 = gy.e(v5_6, v2_6);
                        } catch (Object v8_9) {
                            v8_8 = new hy(v8_9);
                        }
                        if ((v8_8 instanceof hy)) {
                            v8_8 = 0;
                        }
                        Object v8_10 = ((String) v8_8);
                        if (v8_10 != null) {
                            try {
                                int v5_7 = gy.e(v5_6, (v2_6 - 30000));
                            } catch (int v5_8) {
                                v5_7 = new hy(v5_8);
                            }
                            if ((v5_7 instanceof hy)) {
                                v5_7 = 0;
                            }
                            java.util.LinkedHashSet v11_4 = this.j0;
                            if ((v11_4.isEmpty()) || (this.k0)) {
                                if ((30000 - (v2_6 % 30000)) < 8000) {
                                    v8_10 = 0;
                                }
                                if (this.k0) {
                                    boolean v2_12 = f6.m0(new String[] {v8_10, ((String) v5_7)}));
                                    int v3_2 = v2_12.size();
                                    int v5_10 = 0;
                                    while (v5_10 < v3_2) {
                                        Object v8_11 = v2_12.get(v5_10);
                                        v5_10++;
                                        if (!v11_4.contains(((String) v8_11))) {
                                            v6 = v8_11;
                                            break;
                                        }
                                    }
                                    v6 = ((String) v6);
                                } else {
                                    if ((v8_10 != null) && (!v11_4.contains(v8_10))) {
                                        v6 = v8_10;
                                    }
                                }
                            }
                        }
                    }
                    boolean v2_0 = this.d0;
                    if (this.Q != null) {
                        v4_0 = 1;
                    }
                    Object v8_0;
                    int v3_4 = this.R;
                    if (v2_0) {
                        v8_0 = v2_0;
                    } else {
                        v8_0 = "";
                    }
                    boolean v9_0;
                    Object v8_1 = org.json.JSONObject.quote(v8_0);
                    if (v6 != null) {
                        v9_0 = v6;
                    } else {
                        v9_0 = "";
                    }
                    boolean v9_1 = org.json.JSONObject.quote(v9_0);
                    if (!v2_0) {
                        v2_0 = "";
                    }
                    boolean v2_1 = org.json.JSONObject.quote(v2_0);
                    int v5_1 = new StringBuilder("\n            var dialogs=[].filter.call(document.querySelectorAll(\'[role=\"dialog\"]\'),function(d){ return norm(d.innerText).length>20; });\n            var root=dialogs.length?dialogs[dialogs.length-1]:document.body;\n            var text=norm(root.innerText).toLowerCase();\n            function codeFields(scope){\n              return [].filter.call((scope||document).querySelectorAll(\'input,textarea\'), function(n){\n                if(!vis(n)||n.disabled||n.getAttribute(\'aria-disabled\')===\'true\') return false;\n                var ty=(n.type||\'text\').toLowerCase();\n                return ty!==\'hidden\'&&ty!==\'checkbox\'&&ty!==\'radio\'&&ty!==\'submit\'&&ty!==\'button\'&&ty!==\'file\'&&ty!==\'email\';\n              });\n            }\n            function middleField(scope){\n              var fields=codeFields(scope);\n              if(!fields.length && scope!==document) fields=codeFields(document);\n              var otp=fields.filter(function(n){\n                var ac=(n.getAttribute(\'autocomplete\')||\'\').toLowerCase();\n                var mode=(n.getAttribute(\'inputmode\')||\'\').toLowerCase();\n                return ac===\'one-time-code\'||mode===\'numeric\'||n.maxLength===6||n.maxLength===8;\n              });\n              var pool=otp.length?otp:fields;\n              var cy=window.innerHeight/2, cx=window.innerWidth/2, best=null, bestD=1e12;\n              for(var i=0;i<pool.length;i++){\n                var r=pool[i].getBoundingClientRect();\n                var d=Math.abs(r.top+r.height/2-cy)+Math.abs(r.left+r.width/2-cx)*0.35;\n                if(d<bestD){ best=pool[i]; bestD=d; }\n              }\n              return best;\n            }\n            var input=middleField(root);\n            function tapIn(labels){\n              for(var j=0;j<labels.length;j++){\n                var els=root.querySelectorAll(\'[role=\"button\"],button\');\n                for(var i=0;i<els.length;i++){\n                  var b=els[i];\n                  if(!vis(b)||b.getAttribute(\'aria-disabled\')===\'true\'||b.disabled) continue;\n                  if(norm(b.innerText).toLowerCase()===labels[j]){ tap(b); return true; }\n                }\n              }\n              return false;\n            }\n            function tapExact(labels){\n              var els=document.querySelectorAll(\'[role=\"button\"],button,input[type=\"submit\"]\');\n              for(var j=0;j<labels.length;j++){\n                for(var i=0;i<els.length;i++){\n                  var b=els[i];\n                  if(!vis(b)||b.getAttribute(\'aria-disabled\')===\'true\'||b.disabled) continue;\n                  var lab=norm(b.innerText||b.value||\'\').replace(/\\s+/g,\' \').toLowerCase();\n                  if(lab===labels[j]){ tap(b); return true; }\n                }\n              }\n              return false;\n            }\n            function finished(t){\n              return /has been set up|authentication is on|two[- ]factor authentication is on|two[- ]factor authentication (is )?enabled|two[- ]factor authentication has been enabled|two[- ]factor authentication.{0,50}(on|enabled|active|protected)|2fa.{0,30}(on|enabled|active)|turned on two[- ]factor|turned on 2[- ]step|you.?re all set|you are all set|is now on|successfully (turned on|enabled|set up)|is ready|extra security is on|2[- ]step verification is on/.test(t);\n            }\n            function rejected(t){\n              return /incorrect code|code is incorrect|wrong code|isn.?t right|isn.?t correct|couldn.?t verify|could not verify|does not match|doesn.?t match|please check the code/.test(t);\n            }\n            function hasVisibleCodeInput(scope){\n              return [].some.call(\n                scope.querySelectorAll(\'input[type=\"text\"],input[type=\"tel\"],input[type=\"number\"],input[type=\"password\"],input:not([type]),input[autocomplete=\"one-time-code\"]\'),\n                vis\n              );\n            }\n            if(location.pathname.indexOf(\'/auth_platform/codeentry\')>-1){\n              var codeInput=middleField(document);\n              var page=norm(document.body.innerText).toLowerCase();\n              if(");
                    v5_1.append(v3_4);
                    v5_1.append("&&finished(page.replace(/\\s+/g,\' \'))) return finish();\n              if(!codeInput){\n                if(rejected(page.replace(/\\s+/g,\' \'))) return \'totp-rejected\';\n                if(");
                    v5_1.append(v3_4);
                    v5_1.append(") return finish();\n                return \'\';\n              }\n              var appPage=/authentication app|authenticator app|6-digit code|get your code from your authentication|enter code/.test(page);\n              var emailPage=/check your email|code that we sent|code we sent|sent to your email|email code/.test(page) && !appPage;\n              if(appPage && !emailPage) return enterTotp(codeInput);\n              if(!appPage && ");
                    v5_1.append(v1_17);
                    v5_1.append(" && tapExact([\'get a new code\'])) return \'resent\';\n              var mailed=");
                    v5_1.append(v8_1);
                    v5_1.append(";\n              if(mailed){\n                setVal(codeInput, mailed);\n                var codeBtn=findExactBtn([\'continue\',\'next\',\'submit\',\'confirm\'], document);\n                if(codeBtn) tap(codeBtn);\n                return \'code\';\n              }\n              if(!emailPage){\n                var filled=enterTotp(codeInput);\n                if(filled) return filled;\n              }\n              return \'need-code\';\n            }\n            function keyOk(s){\n              var k=((s||\'\')+\'\').toUpperCase().replace(/\\s+/g,\'\');\n              if(k.length<16||k.length>64||!/^[A-Z2-7]+$/.test(k)) return false;\n              var spaced=((s||\'\')+\'\').toUpperCase().replace(/[\\s\\u00a0]+/g,\' \').trim();\n              // \"Get your code from your authentication app\" => YOUR CODE FROM YOUR (false key).\n              if(/YOUR CODE FROM YOUR|CODE FROM YOUR|FROM YOUR AUTH|GET YOUR CODE|ENTER THE CODE|COPY THE KEY|SCAN THE QR|OPEN YOUR AUTH|USE YOUR AUTH/.test(spaced)) return false;\n              // Unspaced UI phrases (e.g. GOOGLEAUTHENTICATOR=20) beat a real 16-char key if allowed.\n              if(/AUTHENTICATOR|GOOGLEAUTH|DUOMOBILE|DOWNLOADAN|AUTHENTICATIONAPP|INSTRUCTIONSFOR|BARCODEORQR|PASSWORDAND|TWOFACTOR|SECURITYCODE|ACCOUNTSCENTER/.test(k)) return false;\n              var groups=spaced.split(\' \').filter(Boolean);\n              if(groups.length>=4){\n                var ui={YOUR:1,CODE:1,FROM:1,WITH:1,THIS:1,THAT:1,NEXT:1,BACK:1,DONE:1,COPY:1,SCAN:1,OPEN:1,HERE:1,INTO:1,EACH:1,STEP:1,THEN:1,WHEN:1,HAVE:1,WERE:1,THEY:1,THEM:1,WHAT:1,WILL:1,MAKE:1,TAKE:1,ONLY:1,OVER:1,JUST:1,LIKE:1,SOME:1,TIME:1,VERY:1,ENTER:1,AUTH:1,PASS:1,WORD:1,SAFE:1,HELP:1,MORE:1,THAN:1,ALSO:1,ABLE:1,USED:1,USER:1,NAME:1,MAIL:1,EDIT:1,SAVE:1,LINK:1,PAGE:1,HOME:1,MENU:1,LIST:1,VIEW:1,SHOW:1,HIDE:1,TEXT:1,TYPE:1,FORM:1,SEND:1,LEFT:1,DOWN:1,APP:1,KEY:1,MANUAL:1,SETUP:1};\n                // Any English UI token in a 4-char group means the regex ate \"Copy key\" etc.\n                for(var i=0;i<groups.length;i++) if(ui[groups[i]]) return false;\n                // Spaced setup keys are groups of 4 chars (typically 4 or 8 groups).\n                var all4=true;\n                for(var g=0;g<groups.length;g++) if(groups[g].length!==4) all4=false;\n                if(!all4) return false;\n                if(groups.length<4||groups.length>16) return false;\n              }\n              return true;\n            }\n            function pickKey(text){\n              var upper=norm(text||\'\').toUpperCase().replace(/[\\s\\u00a0]+/g,\' \').trim();\n              var best=\'\', bestScore=-1, m, re;\n              function score(raw, spaced){\n                var n=raw.replace(/\\s+/g,\'\').length;\n                // Prefer spaced 4x4-group keys (Instagram shows them that way) over unspaced UI glue.\n                var s=(spaced?1000:0)+n;\n                // Common TOTP secret sizes.\n                if(n===16||n===32) s+=50;\n                return s;\n              }\n              // Try 4..8 groups of 4 from each start so \"KEY Copy\" does not swallow Copy,\n              // while still accepting 32-char (8-group) secrets.\n              re=/\\b([A-Z2-7]{4})(?=([ \\t]+[A-Z2-7]{4}){3,15})\\b/g;\n              while((m=re.exec(upper))){\n                var start=m.index;\n                var tail=upper.slice(start);\n                var parts=tail.match(/^[A-Z2-7]{4}(?:[ \\t]+[A-Z2-7]{4}){0,15}/);\n                if(!parts) continue;\n                var toks=parts[0].split(/[ \\t]+/);\n                for(var ng=4;ng<=toks.length && ng<=8;ng++){\n                  var cand=toks.slice(0,ng).join(\' \');\n                  if(!keyOk(cand)) continue;\n                  var sc=score(cand, true);\n                  if(sc>bestScore){ best=cand; bestScore=sc; }\n                }\n                // Avoid overlapping restarts inside the same run.\n                re.lastIndex=start+1;\n              }\n              // Unspaced only if no spaced candidate.\n              if(!best){\n                re=/\\b([A-Z2-7]{16,64})\\b/g;\n                while((m=re.exec(upper))){\n                  if(!keyOk(m[1])) continue;\n                  var sc2=score(m[1], false);\n                  if(sc2>bestScore){ best=m[1]; bestScore=sc2; }\n                }\n              }\n              return best;\n            }\n            function findKey(scope){\n              scope=scope||document.body;\n              var best=\'\', bestLen=0;\n              function consider(raw){\n                var k=pickKey(raw);\n                if(!k) return;\n                var n=k.replace(/\\s+/g,\'\').length;\n                if(n>bestLen){ best=k; bestLen=n; }\n              }\n              // Prefer real key carriers: clipboard attr, code/pre/kbd, readonly fields (not 6-digit OTP).\n              var nodes=scope.querySelectorAll?scope.querySelectorAll(\'[data-clipboard-text],code,pre,kbd,input,textarea\'):[];\n              for(var i=0;i<nodes.length;i++){\n                var n=nodes[i];\n                var clip=n.getAttribute?n.getAttribute(\'data-clipboard-text\'):\'\';\n                if((n.tagName===\'INPUT\'||n.tagName===\'TEXTAREA\') && !clip){\n                  if(n.maxLength>0 && n.maxLength<=8) continue;\n                  if(!(n.readOnly || (n.type||\'\')===\'\' || (n.type||\'\').toLowerCase()===\'text\')) continue;\n                }\n                consider(clip||n.value||n.innerText||\'\');\n              }\n              if(best) return best;\n              // Lone visible key chip/label (short node = key alone, not a paragraph of UI copy).\n              var els=scope.querySelectorAll?scope.querySelectorAll(\'span,div,p,li,td,section,label\'):[];\n              for(var j=0;j<els.length;j++){\n                var el=els[j];\n                if(!vis(el)) continue;\n                var t=norm(el.innerText||\'\').replace(/\\s+/g,\' \');\n                if(t.length<16||t.length>96) continue;\n                var u=t.toUpperCase();\n                var only=u.match(/^([A-Z2-7]{4}(?:[ \\t]+[A-Z2-7]{4}){3,15})$/)||u.match(/^([A-Z2-7]{16,64})$/);\n                if(only&&keyOk(only[1])){\n                  var n2=only[1].replace(/\\s+/g,\'\').length;\n                  if(n2>bestLen){ best=only[1]; bestLen=n2; }\n                }\n              }\n              if(best) return best;\n              // Last resort on scope text (keyOk strips UI phrases like YOUR CODE FROM YOUR).\n              consider(scope.innerText||scope.textContent||\'\');\n              return best;\n            }\n            function isCodeEntryScreen(t){\n              if(/get your code from your authentication|enter the 6-digit code generated|6-digit code generated by your|enter code[\\s\\S]{0,80}(isn\'?t right|try again)/.test(t)) return true;\n              // Authenticator code prompt without QR/key-setup chrome.\n              return /authentication app|authenticator app/.test(t)\n                && /enter (the )?code|6-digit code/.test(t)\n                && !/scan|qr code|copy (the )?key|can\'?t scan|cannot scan|instructions for setup|setup key/.test(t);\n            }\n            function isKeyScreen(t){\n              // Never treat the TOTP code-entry dialog as the setup/QR/key screen.\n              if(isCodeEntryScreen(t)) return false;\n              // Phrase match only for setup/QR/key copy. Do not treat method-picker icons as the key screen.\n              if(/instructions for setup|copy the key|copy key|copy setup key|can\'?t scan|cannot scan|or enter the key|enter (the )?key manually|enter this code manually|setup key|set up (the )?key|manual (setup|entry)|scan (the |this )?qr|qr code|add authentication app|open your authentication app|scan.*authentication app|authentication app.*scan|use (an |your )?authentication app to scan/.test(t)) return true;\n              var imgs=[].filter.call(root.querySelectorAll(\'img,canvas,[role=\"img\"]\'),vis);\n              for(var i=0;i<imgs.length;i++){\n                var a=((imgs[i].alt||\'\')+\' \'+(imgs[i].getAttribute(\'aria-label\')||\'\')).toLowerCase();\n                if(/qr|barcode|scan/.test(a)) return true;\n              }\n              return false;\n            }\n            function tapRevealKey(){\n              var phrases=[\"can\'t scan it\",\"can\'t scan the qr\",\"can\'t scan\",\"cannot scan\",\"copy setup key\",\"copy the key\",\"copy key\",\"set up manually\",\"setup manually\",\"enter setup key\",\"enter key manually\",\"enter the key\",\"or enter the key\",\"or enter manually\"];\n              var roots=[root,document];\n              for(var r=0;r<roots.length;r++){\n                var els=roots[r].querySelectorAll(\'[role=\"button\"],button,a,div[tabindex],span[role=\"button\"]\');\n                for(var j=0;j<phrases.length;j++){\n                  for(var i=0;i<els.length;i++){\n                    var b=els[i];\n                    if(!vis(b)||b.getAttribute(\'aria-disabled\')===\'true\'||b.disabled) continue;\n                    var lab=norm(b.innerText||b.value||b.getAttribute(\'aria-label\')||\'\').replace(/\\s+/g,\' \').toLowerCase();\n                    if(!lab||lab.length>70) continue;\n                    if(lab.indexOf(phrases[j])>-1){ tap(b); return true; }\n                  }\n                }\n              }\n              return false;\n            }\n            function finish(){\n              var seen=findKey(root)||findKey(document.body);\n              tapIn([\'done\']);\n              tapExact([\'done\']);\n              return \'done:\'+(seen||\'\');\n            }\n            function codeWasAccepted(){\n              return ");
                    v5_1.append(v3_4);
                    v5_1.append(" && !hasVisibleCodeInput(document);\n            }\n            function enterTotp(field){\n              var page=norm(document.body.innerText).toLowerCase();\n              var appCode=");
                    v5_1.append(v9_1);
                    v5_1.append(";\n              var current=(field.value||\'\').replace(/\\s/g,\'\');\n              if(rejected(page)&&(!appCode||current===appCode)) return \'totp-rejected\';\n              if(!appCode) return \'\';\n              if(current!==appCode) setVal(field, appCode);\n              // Tap Next/Continue only when visible+enabled; else totp-wait (does not mark TOTP used).\n              var totpBtn=findExactBtn([\'next\',\'continue\',\'submit\',\'confirm\'], document);\n              if(totpBtn){ tap(totpBtn); return \'totp\'; }\n              return \'totp-wait\';\n            }\n            var bodyText=norm(document.body.innerText).toLowerCase();\n            if(");
                    v5_1.append(v3_4);
                    v5_1.append("&&rejected((text+\' \'+bodyText).replace(/\\s+/g,\' \'))) return \'totp-rejected\';\n            if((");
                    v5_1.append(v3_4);
                    v5_1.append("&&\n                (finished(text.replace(/\\s+/g,\' \'))||finished(bodyText.replace(/\\s+/g,\' \'))))\n                ||codeWasAccepted()) return finish();\n            if(/choose an account/.test(text)){\n              var ig=[].filter.call(root.querySelectorAll(\'[role=\"button\"]\'),function(b){\n                return vis(b)&&norm(b.innerText).split(\'\\n\').some(function(l){ return l.trim().toLowerCase()===\'instagram\'; });\n              })[0];\n              if(!ig) return \'\';\n              tap(ig);\n              return \'account\';\n            }\n            if(/set up extra protection|add an extra login step/.test(text)){\n              return tapIn([\'get started\',\'continue\',\'next\'])?\'start\':\'\';\n            }\n            if(/check your email|code that we sent/.test(text)&&input){\n              if(");
                    v5_1.append(v1_17);
                    v5_1.append("&&tapIn([\'get a new code\'])) return \'resent\';\n              var code=");
                    v5_1.append(v2_1);
                    v5_1.append(";\n              if(!code) return \'need-code\';\n              setVal(input,code);\n              var emailBtn=findExactBtn([\'continue\',\'next\',\'submit\'], root);\n              if(emailBtn) tap(emailBtn);\n              return \'code\';\n            }\n            // Code entry (\"Get your code from your authentication app\") before key/QR screen.\n            if(isCodeEntryScreen(text)||isCodeEntryScreen(bodyText)){\n              var codeField=middleField(document)||input;\n              if(codeField) return enterTotp(codeField);\n              return ");
                    v5_1.append(v3_4);
                    v5_1.append("&&!rejected(bodyText.replace(/\\s+/g,\' \'))?finish():\'\';\n            }\n            if(isKeyScreen(text)||isKeyScreen(bodyText)){\n              var key=findKey(root)||findKey(document.body);\n              if(!key){\n                // Key often sits behind Can\'t scan / Copy key; reveal it, never tap Next yet.\n                if(!");
                    v5_1.append(v4_0);
                    v5_1.append(" && tapRevealKey()) return \'key-wait\';\n                return ");
                    v5_1.append(v4_0);
                    v5_1.append(" ? \'\' : \'key-wait\';\n              }\n              if(");
                    v5_1.append(v4_0);
                    v5_1.append("){\n                // Key already saved. Accounts Center setup CTA is \"Enter code\" (not Next).\n                var keyBtn=findExactBtn([\'enter code\',\'enter code manually\',\'next\',\'continue\'], root)\n                  ||findExactBtn([\'enter code\',\'enter code manually\',\'next\',\'continue\'], document);\n                if(keyBtn){ tap(keyBtn); return \'key-next\'; }\n                return \'key-wait\';\n              }\n              return \'key:\'+key;\n            }\n            if(/choose how to confirm|help protect your account/.test(text)){\n              var radio=root.querySelector(\'input[type=\"radio\"][value=\"TOTP\"]\')||[].filter.call(root.querySelectorAll(\'input[type=\"radio\"]\'),function(r){ return /authentication app/i.test((r.closest(\'label\')||r.parentElement||{}).innerText||\'\'); })[0];\n              if(radio&&!radio.checked){ tap(radio); return \'method\'; }\n              return tapIn([\'continue\',\'next\'])?\'method\':\'\';\n            }\n            if(/authentication app|authenticator app|6-digit code|enter code/.test(text)&&input){\n              return enterTotp(input);\n            }\n            if(");
                    v5_1.append(v3_4);
                    v5_1.append("&&!hasVisibleCodeInput(document)&&!rejected(bodyText.replace(/\\s+/g,\' \'))) return finish();\n            return \'\';\n            ");
                    v0_1.evaluateJavascript(p40.e0(v5_1.toString()), new wn(this, p14, v6, 1));
                    return;
                } else {
                    this.h(new IllegalStateException("No open tab"));
                    return;
                }
            } else {
                String v14_7;
                String v14_3 = this.Q;
                String v0_3 = this.a;
                if (v14_3 != null) {
                    String v1_11 = new StringBuilder();
                    while (v4_0 < v14_3.length()) {
                        boolean v2_5 = v14_3.charAt(v4_0);
                        if ((!io.x(v2_5)) && (v2_5 != 61)) {
                            v1_11.append(v2_5);
                        }
                        v4_0++;
                    }
                    String v14_5 = v1_11.toString().toUpperCase(java.util.Locale.ROOT);
                    v14_5.getClass();
                    v14_7 = v0_3.getString(2131689528, new Object[] {v14_5}));
                } else {
                    v14_7 = v0_3.getString(2131689527);
                }
                v14_7.getClass();
                this.y(v14_7);
                return;
            }
        } else {
            return;
        }
    }

    public final void C()
    {
        long v1_2 = this.a.getString(2131689570, new Object[] {Integer.valueOf(this.K), Integer.valueOf(this.L), Integer.valueOf(this.M)}));
        v1_2.getClass();
        this.x(bo.LOADING, v1_2);
        this.i.postDelayed(new q1(this, 13), 30000);
        return;
    }

    public final String D(String p2)
    {
        String v1_1 = this.N;
        if (v1_1 == null) {
            return p2;
        } else {
            return g.e(p2, "\n", v1_1);
        }
    }

    public final String E(int p5)
    {
        int v0_4;
        int v0_3 = ((nm) rb.i0(this.s, this.t));
        if (v0_3 == 0) {
            v0_4 = 0;
        } else {
            v0_4 = v0_3.b;
        }
        if (v0_4 == 0) {
            v0_4 = "";
        }
        Integer v1_2 = (this.t + 1);
        Integer v2_1 = this.s.size();
        if (v1_2 > v2_1) {
            v1_2 = v2_1;
        }
        com.example.instatool.browser.BrowserActivity v3 = this.a;
        String v5_3 = v3.getString(2131689571, new Object[] {Integer.valueOf(v1_2), Integer.valueOf(this.s.size()), v0_4, v3.getString(p5)}));
        v5_3.getClass();
        return this.D(v5_3);
    }

    public final void F(nm p8, java.util.Map p9, String p10, ll p11)
    {
        String v2 = this.k;
        if (v2 != null) {
            this.e();
            this.x(bo.SAVING, this.t(2131689548));
            this.c.execute(new vn(this, v2, p8, p9, p11, p10));
            return;
        } else {
            this.h(new IllegalStateException(this.a.getString(2131689918)));
            return;
        }
    }

    public final void a(nm p15)
    {
        String v1_0 = bo.FILLING;
        if (this.g == v1_0) {
            String v0_15 = p40.X(this.f());
            String v5_2 = this.i;
            if ((v0_15 == null) || (v0_15.equals(this.I))) {
                if ((this.I != null) || (!this.o())) {
                    if (System.currentTimeMillis() <= this.y) {
                        String v0_13 = this.A();
                        if (v0_13 != null) {
                            if ((this.A) && (System.currentTimeMillis() > this.B)) {
                                this.A = 0;
                                this.C = 1;
                            }
                            this.x(v1_0, this.E(this.G));
                            String v1_8 = p15.b;
                            zn v2_8 = this.x;
                            String v4_2 = this.z;
                            String v5_0 = this.D;
                            if (v5_0 == null) {
                                v5_0 = "";
                            }
                            String v6_2 = this.A;
                            String v7_1 = this.C;
                            String v8_0 = this.E;
                            boolean v9 = this.F;
                            v1_8.getClass();
                            v2_8.getClass();
                            v8_0.getClass();
                            String v10_0 = java.util.Locale.ROOT;
                            String v11_0 = v1_8.toLowerCase(v10_0);
                            v11_0.getClass();
                            String v11_1 = org.json.JSONObject.quote(v11_0);
                            String v1_9 = v1_8.toLowerCase(v10_0);
                            v1_9.getClass();
                            String v1_10 = org.json.JSONObject.quote(v1_9);
                            zn v2_9 = org.json.JSONObject.quote(v2_8);
                            String v8_1 = org.json.JSONObject.quote(v8_0);
                            String v10_1 = org.json.JSONObject.quote(v5_0);
                            String v5_1 = org.json.JSONObject.quote(v5_0);
                            StringBuilder v12_1 = new StringBuilder("\n            if(");
                            v12_1.append(v7_1);
                            v12_1.append(") window.__instaToolAgreeTap=0;\n            if(");
                            v12_1.append(v6_2);
                            v12_1.append("){\n              window.__instaToolAgreeTap=0;\n              var popup=tapLabel([\'agree and continue\']);\n              return popup?\'tap:\'+popup:\'\';\n            }\n            window.__instaToolSawAgree=false;\n            if(!");
                            v12_1.append(v4_2);
                            v12_1.append("){\n              var em=accountOption(");
                            v12_1.append(v11_1);
                            v12_1.append(");\n              if(!em){\n                var hit=best(\'[role=\"button\"],button,li,a,div,span\', function(t){ return t.indexOf(");
                            v12_1.append(v1_10);
                            v12_1.append(")>-1; });\n                if(hit) em=clickable(hit);\n              }\n              if(em){\n                var top=Math.round(em.getBoundingClientRect().top), settled=window.__instaToolEmailTop===top;\n                window.__instaToolEmailTop=top;\n                if(settled){ window.__instaToolAgreeTap=0; tap(em); return \'email\'; }\n                window.__instaToolAgreeTap=0;\n                return \'\';\n              }\n            }\n            var inputs=document.querySelectorAll(\'input[name=\"fullName\"],input[name=\"full_name\"],input[name=\"firstName\"],input[aria-label*=\"name\" i],input[placeholder*=\"name\" i]\');\n            for(var i=0;i<inputs.length;i++){\n              var n=inputs[i], hint=((n.name||\'\')+\' \'+(n.getAttribute(\'aria-label\')||\'\')+\' \'+(n.placeholder||\'\')).toLowerCase();\n              if(!vis(n)||n.value||n.type===\'password\'||hint.indexOf(\'user\')>-1||hint.indexOf(\'email\')>-1) continue;\n              window.__instaToolAgreeTap=0;\n              setVal(n, ");
                            v12_1.append(v2_9);
                            v12_1.append("); return \'name\';\n            }\n            var pageText=norm(document.body.innerText).toLowerCase();\n            var onUsername=/username|user name/.test(pageText)\n              && !/log in with username|email address or username/.test(pageText);\n            var usernameSelectors=\'input[autocomplete*=\"username\" i],input[name*=\"user\" i],input[id*=\"user\" i],input[aria-label*=\"user\" i],input[placeholder*=\"user\" i],[role=\"textbox\"][aria-label*=\"user\" i],[contenteditable=\"true\"][aria-label*=\"user\" i]\';\n            var fields=[].filter.call(document.querySelectorAll(usernameSelectors),function(n){\n              if(!vis(n)||n.disabled||n.getAttribute(\'aria-disabled\')===\'true\') return false;\n              var type=(n.type||\'\').toLowerCase();\n              return type!==\'password\'&&type!==\'hidden\'&&type!==\'checkbox\'&&type!==\'radio\';\n            });\n            if(!fields.length&&onUsername){\n              fields=[].filter.call(document.querySelectorAll(\'input[type=\"text\"],input:not([type]),[role=\"textbox\"],[contenteditable=\"true\"]\'),function(n){\n                if(!vis(n)||n.disabled||n.getAttribute(\'aria-disabled\')===\'true\') return false;\n                var hint=((n.name||\'\')+\' \'+(n.id||\'\')+\' \'+(n.getAttribute(\'aria-label\')||\'\')+\' \'+(n.placeholder||\'\')+\' \'+(n.getAttribute(\'autocomplete\')||\'\')).toLowerCase();\n                return hint.indexOf(\'email\')<0&&hint.indexOf(\'password\')<0&&hint.indexOf(\'full name\')<0;\n              });\n            }\n            var wanted=");
                            v12_1.append(v8_1);
                            v12_1.append(";\n            var customGaveUp=");
                            v12_1.append(v9);
                            v12_1.append(";\n            function usernameStatus(field){\n              var bits=[];\n              [].forEach.call(document.querySelectorAll(\'[aria-label]\'), function(n){\n                if(!vis(n)) return;\n                var a=n.getAttribute(\'aria-label\')||\'\';\n                if(/user/i.test(a)) bits.push(a);\n              });\n              var scope=field;\n              for(var up=0; up<8 && scope && scope.parentElement; up++) scope=scope.parentElement;\n              bits.push((scope&&scope.innerText)||\'\');\n              var blob=norm(bits.join(\' \')).toLowerCase();\n              if(/isn.?t available|not available|already taken|try another|isn.?t valid|not valid|can.?t be used|unavailable|is taken/.test(blob)) return \'taken\';\n              if(/username is valid/.test(blob)||(/is valid/.test(blob)&&!/isn.?t valid|not valid/.test(blob))) return \'valid\';\n              return \'wait\';\n            }\n            if(fields.length&&wanted){\n              var field0=fields[0];\n              var current=(field0.value||field0.innerText||field0.textContent||\'\').trim().replace(/^@/,\'\');\n              if(!customGaveUp){\n                if(/^[A-Za-z0-9._]{1,30}$/.test(current)&&current.toLowerCase()!==wanted.toLowerCase()){\n                  window.__instaSuggested=current;\n                }\n                if(current.toLowerCase()!==wanted.toLowerCase()){\n                  setVal(field0, wanted);\n                  window.__instaCustomPolls=0;\n                  window.__instaToolAgreeTap=0;\n                  return \'custom-set\';\n                }\n                var status=usernameStatus(field0);\n                window.__instaCustomPolls=(window.__instaCustomPolls||0)+1;\n                if(status===\'taken\'||window.__instaCustomPolls>=12) return \'custom-taken\';\n                if(status===\'valid\'&&window.__instaCustomPolls>=2){\n                  if(current!==");
                            v12_1.append(v10_1);
                            v12_1.append("){\n                    window.__instaToolAgreeTap=0;\n                    return \'username:\'+current;\n                  }\n                }else{\n                  return \'custom-wait\';\n                }\n              }else if(current.toLowerCase()===wanted.toLowerCase()){\n                var back=window.__instaSuggested||\'\';\n                if(/^[A-Za-z0-9._]{1,30}$/.test(back)){\n                  setVal(field0, back);\n                  window.__instaToolAgreeTap=0;\n                  return \'custom-restore\';\n                }\n              }\n            }\n            for(var fi=0;fi<fields.length;fi++){\n              var field=fields[fi];\n              var handle=(field.value||field.innerText||field.textContent||field.getAttribute(\'aria-valuetext\')||\'\')\n                .trim().replace(/^@/,\'\');\n              if(/^[A-Za-z0-9._]{1,30}$/.test(handle)&&handle!==");
                            v12_1.append(v5_1);
                            v12_1.append("){\n                if(customGaveUp&&wanted&&handle.toLowerCase()===wanted.toLowerCase()) continue;\n                window.__instaToolAgreeTap=0;\n                return \'username:\'+handle;\n              }\n            }\n            if(onUsername&&!fields.length){\n              window.__instaToolAgreeTap=0;\n              return \'\';\n            }\n            var tapped=tapLabel([\'allow and continue\',\'i agree\',\'next\',\'continue\',\'agree\',\'accept all\',\'accept\',\'ok\']);\n            if(tapped===\'__stuck__\') return \'stuck-agree\';\n            if(!window.__instaToolSawAgree) window.__instaToolAgreeTap=0;\n            return tapped?\'tap:\'+tapped:\'\';\n            ");
                            v0_13.evaluateJavascript(p40.e0(v12_1.toString()), new zn(this, p15, v0_13, 1));
                            return;
                        } else {
                            this.h(new IllegalStateException("No open tab"));
                            return;
                        }
                    } else {
                        IllegalStateException v15_4 = this.a.getString(2131689540);
                        v15_4.getClass();
                        this.y(v15_4);
                        return;
                    }
                } else {
                    this.x(bo.WAITING, this.t(2131689569));
                    v5_2.postDelayed(new qn(this, p15, 7), 4000);
                    return;
                }
            } else {
                this.x(bo.WAITING, this.t(2131689569));
                v5_2.postDelayed(new qn(this, p15, 7), 4000);
                return;
            }
        } else {
            return;
        }
    }

    public final void b(nm p5)
    {
        if ((!this.p) || (this.U)) {
            String v5_2 = this.a.getString(2131689542);
            v5_2.getClass();
            this.n(v5_2);
            return;
        } else {
            this.V = 1;
            this.W = 0;
            this.X = 0;
            this.Y = (System.currentTimeMillis() + 60000);
            this.x(bo.FILLING, this.j(p5));
            this.j.flush();
            this.p("https://www.instagram.com/explore/people/");
            this.i.postDelayed(new qn(this, p5, 6), 1500);
            return;
        }
    }

    public final void c(nm p7)
    {
        this.K = (this.K + 1);
        if ((this.m.isEmpty()) || (this.Z)) {
            this.b(p7);
            return;
        } else {
            try {
                qn v0_2 = this.n.a(this.m);
            } catch (qn v0_3) {
                v0_2 = new hy(v0_3);
            }
            if ((v0_2 instanceof hy)) {
                v0_2 = 0;
            }
            qn v0_5 = ((android.net.Uri) v0_2);
            if (v0_5 != null) {
                this.c0 = v0_5;
                this.a0 = 1;
                this.b0 = (System.currentTimeMillis() + 45000);
                this.x(bo.FILLING, this.E(2131689546));
                qn v0_10 = this.A();
                if (v0_10 != null) {
                    v0_10.evaluateJavascript("window.__instaPhotoSaved=0;window.__instaPhotoSubmitted=0;window.__instaPhotoSubmitPolls=0", 0);
                }
                this.p("https://www.instagram.com/accounts/edit/");
                this.i.postDelayed(new qn(this, p7, 9), 1500);
            } else {
                this.Z = 1;
                this.b(p7);
            }
            return;
        }
    }

    public final void d()
    {
        rn v0_0 = this.a;
        if (io.d(v0_0.getPackageName(), "com.example.instatool")) {
            rn v0_3 = ((nm) rb.i0(this.s, this.t));
            if (v0_3 != null) {
                this.H = 0;
                sn v3_3 = rb.n0(vt.a);
                String v4_1 = rb.n0(vt.b);
                String v5_1 = new StringBuilder();
                v5_1.append(v3_3);
                v5_1.append(" ");
                v5_1.append(v4_1);
                this.x = v5_1.toString();
                this.v = 0;
                this.w = 0;
                this.z = 0;
                this.A = 0;
                this.B = 0;
                this.C = 0;
                this.D = 0;
                String v5_2 = "";
                if (this.o) {
                    String v4_6 = m10.J(m10.P(v0_3.e).toString(), "@");
                    int v6_1 = eo.m0;
                    v6_1.getClass();
                    if (v6_1.a.matcher(v4_6).matches()) {
                        if (v4_6.length() >= 16) {
                            int v6_6 = 0;
                            while (v6_6 < v4_6.length()) {
                                char v7_2 = v4_6.charAt(v6_6);
                                if (((65 <= v7_2) && (v7_2 < 91)) || ((50 <= v7_2) && (v7_2 < 56))) {
                                    v6_6++;
                                }
                            }
                            this.E = v5_2;
                            this.F = 0;
                            this.U = 0;
                            this.V = 0;
                            this.W = 0;
                            this.X = 0;
                            this.Z = 0;
                            this.a0 = 0;
                            this.c0 = 0;
                            this.O = 0;
                            this.Q = 0;
                            this.S = 0;
                            this.T = 0;
                            this.G = 2131689567;
                            this.x(bo.FILLING, this.E(2131689555));
                            sn v3_1 = new sn(this, v0_3, 1);
                            rn v0_2 = this.A();
                            if (v0_2 != null) {
                                v0_2.stopLoading();
                                v0_2.clearCache(1);
                                v0_2.clearFormData();
                                v0_2.clearHistory();
                            }
                            android.webkit.WebStorage.getInstance().deleteAllData();
                            this.j.removeAllCookies(new rn(this, v3_1, 0));
                            return;
                        }
                        v5_2 = v4_6;
                    }
                }
            } else {
                this.m(1);
                return;
            }
        } else {
            rn v0_7 = v0_0.getString(2131689946);
            v0_7.getClass();
            this.x(bo.ERROR, v0_7);
            return;
        }
    }

    public final void e()
    {
        this.i.removeCallbacksAndMessages(0);
        return;
    }

    public final String f()
    {
        android.webkit.CookieManager v6_1 = this.j;
        v6_1.flush();
        String v2 = "https://instagram.com/";
        java.util.Iterator v0_1 = sb.b0(new String[] {"https://www.instagram.com/accounts/login/", "https://accountscenter.instagram.com/password_and_security/two_factor/?theme=dark"})).iterator();
        v2 = "";
        while (v0_1.hasNext()) {
            String v3_3 = v6_1.getCookie(((String) v0_1.next()));
            if (v3_3 == null) {
                v3_3 = "";
            }
            if (((p40.X(v3_3) != null) && (v3_3.length() > v2.length())) || ((v2.length() == 0) && (!m10.G(v3_3)))) {
                v2 = v3_3;
            }
        }
        return v2;
    }

    public final void h(Throwable p4)
    {
        this.e();
        com.example.instatool.browser.BrowserActivity v1_1 = p4.getMessage();
        if (v1_1 == null) {
            v1_1 = p4.getClass().getSimpleName();
        }
        String v4_2 = this.a.getString(2131689533, new Object[] {v1_1}));
        v4_2.getClass();
        this.x(bo.ERROR, v4_2);
        return;
    }

    public final void i(nm p9)
    {
        String v1_0 = bo.FILLING;
        if ((this.g == v1_0) && (this.V)) {
            if ((this.W < 5) && ((this.X < 8) && (System.currentTimeMillis() <= this.Y))) {
                String v0_2 = this.A();
                if (v0_2 != null) {
                    this.x(v1_0, this.j(p9));
                    v0_2.evaluateJavascript(p40.e0("\n            var buttons=[].filter.call(document.querySelectorAll(\'button,[role=\"button\"]\'), function(b){\n              if(!vis(b)||b.disabled||b.getAttribute(\'aria-disabled\')===\'true\') return false;\n              var t=norm(b.innerText||b.getAttribute(\'aria-label\')||\'\').replace(/\\s+/g,\' \').toLowerCase();\n              return t===\'follow\'||t===\'follow back\';\n            });\n            if(!buttons.length){\n              window.scrollBy(0, Math.round(window.innerHeight*0.7));\n              return \'none\';\n            }\n            var pick=buttons[Math.floor(Math.random()*buttons.length)];\n            tap(pick);\n            return \'followed\';\n            "), new rn(this, p9, 1));
                    return;
                } else {
                    this.h(new IllegalStateException("No open tab"));
                    return;
                }
            } else {
                this.V = 0;
                this.U = 1;
                IllegalStateException v9_5 = this.a.getString(2131689542);
                v9_5.getClass();
                this.n(v9_5);
            }
        }
        return;
    }

    public final String j(nm p6)
    {
        int v0_1 = (this.t + 1);
        Integer v1_3 = this.s.size();
        if (v0_1 > v1_3) {
            v0_1 = v1_3;
        }
        com.example.instatool.browser.BrowserActivity v3_2 = this.a;
        String v6_3 = v3_2.getString(2131689571, new Object[] {Integer.valueOf(v0_1), Integer.valueOf(this.s.size()), p6.b, v3_2.getString(2131689535, new Object[] {Integer.valueOf(this.W), Integer.valueOf(5)}))}));
        v6_3.getClass();
        return this.D(v6_3);
    }

    public final boolean k()
    {
        return eo.l0.contains(this.g);
    }

    public final kr l(String p4)
    {
        Character v1_3;
        kr v0_1 = new kr();
        if (!this.l.contains(ao.COOKIES)) {
            v1_3 = 67;
        } else {
            v1_3 = 68;
        }
        v0_1.put(Character.valueOf(v1_3), p4);
        if (this.o) {
            v0_1.put(Character.valueOf(68), p4);
        }
        return v0_1.b();
    }

    public final void m(boolean p5)
    {
        String v0_0 = this.k;
        yn v1_0 = this.a;
        if (v0_0 != null) {
            yn v1_1;
            mq v2_2 = bo.LOADING;
            if ((p5 == null) || (this.g != v2_2)) {
                v1_1 = v1_0.getString(2131689539);
                v1_1.getClass();
            } else {
                v1_1 = this.h;
            }
            this.x(v2_2, v1_1);
            yn v1_2 = this.l;
            v1_2.getClass();
            mq v2_1 = new mq(10);
            v2_1.add("Username / Email");
            v2_1.add("Password");
            if (v1_2.contains(ao.COOKIES)) {
                v2_1.add("Cookies");
            }
            if (v1_2.contains(ao.TWO_FACTOR)) {
                v2_1.add("2FA Key");
            }
            v2_1.f();
            v2_1.c = 1;
            if (v2_1.b <= 0) {
                v2_1 = mq.d;
            }
            this.c.execute(new yn(p5, this, v0_0, v2_1));
            return;
        } else {
            this.h(new IllegalStateException(v1_0.getString(2131689918)));
            return;
        }
    }

    public final void n(String p3)
    {
        bo v0_3 = ((nm) rb.i0(this.s, this.t));
        if (v0_3 != null) {
            this.J.add(Integer.valueOf(v0_3.a));
        }
        this.N = p3;
        this.t = (this.t + 1);
        bo v0_1 = bo.PAUSED;
        if (this.g != v0_1) {
            this.d();
            return;
        } else {
            this.u = 0;
            this.x(v0_1, this.t(2131689545));
            return;
        }
    }

    public final boolean o()
    {
        int v2_4;
        int v2_1 = this.A();
        if (v2_1 == 0) {
            v2_4 = 0;
        } else {
            v2_4 = v2_1.getUrl();
        }
        if (v2_4 == 0) {
            v2_4 = "";
        }
        if ((!m10.A(v2_4, "accountscenter.instagram.com", 1)) && ((!m10.A(v2_4, "/password_and_security/", 1)) && (!m10.A(v2_4, "two_factor", 1)))) {
            return 0;
        } else {
            return 1;
        }
    }

    public final void p(String p2)
    {
        this.A();
        this.j.flush();
        this.e.d(p2);
        return;
    }

    public final void q(nm p3)
    {
        kr v0_0 = this.Q;
        if (v0_0 != null) {
            if (m10.G(v0_0)) {
                v0_0 = 0;
            }
            if ((v0_0 != null) && (!this.T)) {
                this.T = 1;
                eo.r(this, p3, this.l(v0_0));
            }
        }
        return;
    }

    public final void s(nm p6)
    {
        if ((this.g == bo.FILLING) && (this.a0)) {
            android.net.Uri v2_0 = 0;
            if (System.currentTimeMillis() <= this.b0) {
                String v0_1 = this.A();
                if (v0_1 != null) {
                    if (this.c0 == null) {
                        try {
                            hy v3_2 = this.n.a(this.m);
                        } catch (hy v3_3) {
                            v3_2 = new hy(v3_3);
                        }
                        if (!(v3_2 instanceof hy)) {
                            v2_0 = v3_2;
                        }
                        this.c0 = ((android.net.Uri) v2_0);
                    }
                    this.x(bo.FILLING, this.E(2131689546));
                    v0_1.evaluateJavascript(p40.e0("\n            function center(el){\n              var r=el.getBoundingClientRect();\n              return Math.round(r.left+r.width/2)+\',\'+Math.round(r.top+r.height/2);\n            }\n            var page=norm(document.body.innerText).toLowerCase();\n            // Edit profile opens under \"Save your login info?\" (Save Info / Not now). Change photo\n            // is already on the page behind it, so Not now has to go first.\n            var later=best(\'button,[role=\"button\"]\', function(t){ return t===\'not now\'; });\n            if(later){ tap(later); return \'dismiss\'; }\n            // The style screen header is \"Profile photo\" with a small Save button at the top right.\n            // A parent div also contains that text, so only an exact Save/Done button counts.\n            var onStyle=/\\/create\\/(style|crop)\\//.test(location.pathname)||(page.indexOf(\'rotate\')>-1&&page.indexOf(\'filter\')>-1);\n            if(onStyle){\n              var saveBtn=best(\'button\', function(t){ return t===\'save\'||t===\'done\'; });\n              if(saveBtn){ tap(saveBtn); window.__instaPhotoSaved=1; window.__instaPhotoSubmitted=0; return \'crop\'; }\n              return \'\';\n            }\n            // Save only returns to Edit profile. Submit is what stores the new photo.\n            if(window.__instaPhotoSaved&&/\\/accounts\\/edit\\/?/.test(location.pathname)){\n              var submit=best(\'button,[role=\"button\"],div\', function(t){ return t===\'submit\'; });\n              if(!window.__instaPhotoSubmitted){\n                if(submit){ tap(submit); window.__instaPhotoSubmitted=1; window.__instaPhotoSubmitPolls=0; return \'submit\'; }\n                return \'\';\n              }\n              window.__instaPhotoSubmitPolls=(window.__instaPhotoSubmitPolls||0)+1;\n              var busy=submit&&(submit.getAttribute(\'aria-busy\')===\'true\'||!!submit.querySelector(\'[role=progressbar]\'));\n              if(busy) return \'\';\n              if(/profile saved|changes saved|photo updated|profile photo has been|picture updated|profile picture updated/.test(page)) return \'done\';\n              if(!submit&&window.__instaPhotoSubmitPolls>=2) return \'done\';\n              if(window.__instaPhotoSubmitPolls>=6) return \'done\';\n              return \'\';\n            }\n            if(/crop|adjust photo|new profile photo|drag to reposition/.test(page)){\n              var confirmBtn=best(\'button,[role=\"button\"],input[type=\"submit\"]\', function(t){\n                return t===\'done\'||t===\'save\'||t===\'apply\'||t===\'next\';\n              });\n              if(confirmBtn){ tap(confirmBtn); window.__instaPhotoSaved=1; window.__instaPhotoSubmitted=0; return \'crop\'; }\n            }\n            var upload=best(\'button,[role=\"button\"],a,div,span,label\', function(t){\n              return t===\'upload photo\'||t===\'upload picture\'||t===\'choose from library\'||t===\'new photo\';\n            });\n            if(upload) return \'tap:\'+center(upload);\n            var file=document.querySelector(\'input[type=\"file\"]\');\n            if(file){\n              var node=file;\n              while(node&&node!==document.body&&!vis(node)) node=node.parentElement;\n              if(node&&vis(node)&&node!==document.body) return \'tap:\'+center(node);\n            }\n            var change=best(\'button,[role=\"button\"],a,div,span,label\', function(t){\n              return t===\'change photo\'||t===\'change profile photo\'||t===\'add profile photo\'||t===\'edit picture\'\n                ||(t.length<=40&&t.indexOf(\'profile photo\')>-1);\n            });\n            if(change) return \'tap:\'+center(change);\n            return \'\';\n            "), new zn(this, p6, v0_1, 0));
                } else {
                    this.h(new IllegalStateException("No open tab"));
                    return;
                }
            } else {
                this.a0 = 0;
                this.Z = 1;
                this.c0 = 0;
                this.j.flush();
                this.b(p6);
                return;
            }
        }
        return;
    }

    public final String t(int p4)
    {
        Object[] v0_4;
        Object[] v0_3 = ((nm) rb.i0(this.s, this.t));
        if (v0_3 == null) {
            v0_4 = 0;
        } else {
            v0_4 = v0_3.b;
        }
        if (v0_4 == null) {
            v0_4 = "";
        }
        com.example.instatool.browser.BrowserActivity v1_2 = (this.t + 1);
        Integer v2_1 = this.s.size();
        if (v1_2 > v2_1) {
            v1_2 = v2_1;
        }
        String v4_1 = this.a.getString(p4, new Object[] {Integer.valueOf(v1_2), Integer.valueOf(this.s.size()), v0_4}));
        v4_1.getClass();
        return this.D(v4_1);
    }

    public final void u(nm p3, String p4)
    {
        cc v0_3 = Character.valueOf(67);
        if (m10.G(p4)) {
            p4 = "Can\'t find account";
        }
        java.util.Map v4_1 = java.util.Collections.singletonMap(v0_3, p4);
        v4_1.getClass();
        this.F(p3, v4_1, 0, new cc(this, 3));
        return;
    }

    public final void v(nm p6)
    {
        String v1_0 = bo.FILLING;
        if (this.g == v1_0) {
            wn v2_7 = eo.n0;
            String v0_6 = ((co) rb.i0(v2_7, this.v));
            if (v0_6 != null) {
                android.webkit.WebView v3 = this.A();
                if (v3 != null) {
                    wn v2_2;
                    wn v2_1 = ((co) rb.i0(v2_7, this.v));
                    if (v2_1 == null) {
                        v2_2 = this.G;
                    } else {
                        v2_2 = v2_1.a;
                    }
                    this.x(v1_0, this.E(v2_2));
                    String v1_1 = p6.b;
                    wn v2_4 = p6.c;
                    v1_1.getClass();
                    v3.evaluateJavascript(p40.e0(((String) v0_6.c.c(v1_1, v2_4))), new wn(this, p6, v0_6, 0));
                    return;
                } else {
                    this.h(new IllegalStateException("No open tab"));
                    return;
                }
            } else {
                this.y = (System.currentTimeMillis() + 420000);
                this.a(p6);
                return;
            }
        } else {
            return;
        }
    }

    public final void w(nm p6)
    {
        int v0 = this.Q;
        if ((v0 == 0) || (m10.G(v0))) {
            v0 = 0;
        }
        kr v1_5 = this.f();
        sn v2_0 = new kr();
        int v3_0 = this.D;
        if (v3_0 != 0) {
            v2_0.put(Character.valueOf(65), v3_0);
        }
        if ((this.l.contains(ao.COOKIES)) && (!m10.G(v1_5))) {
            v2_0.put(Character.valueOf(67), v1_5);
        }
        if ((this.l.contains(ao.TWO_FACTOR)) && (v0 != 0)) {
            v2_0.putAll(this.l(v0));
        }
        kr v1_4 = v2_0.b();
        if (!v1_4.isEmpty()) {
            this.F(p6, v1_4, v0, new sn(this, p6, 0));
            return;
        } else {
            this.c(p6);
            return;
        }
    }

    public final void x(bo p1, CharSequence p2)
    {
        this.g = p1;
        this.h = p2;
        this.f.a();
        return;
    }

    public final void y(String p3)
    {
        this.e();
        this.M = (this.M + 1);
        String v3_2 = this.a.getString(2131689543, new Object[] {p3}));
        v3_2.getClass();
        this.n(v3_2);
        return;
    }

    public final void z()
    {
        this.e();
        this.c0 = 0;
        if (this.q) {
            int v1_7 = ((android.webkit.WebView) this.d.a());
            if (v1_7 != 0) {
                int v1_0 = v1_7.getSettings();
                if (v1_0 != 0) {
                    v1_0.setUserAgentString(this.r);
                }
            }
            this.q = 0;
        }
        this.u = 0;
        this.s = qh.a;
        int v1_3 = this.a.getString(2131689537);
        v1_3.getClass();
        this.x(bo.IDLE, v1_3);
        return;
    }
}
