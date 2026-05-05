"""
OLIMBEK SAVDO - Admin Web Panel v3.0
=====================================
Barcha yangi funksiyalar:
1. Mijoz AI Chat (bot ichida)
2. Admin AI Chat (web panel)
3. Kengaytirilgan qidiruv (buyurtma tarixi, to'lov cheki)
4. Do'kon qidirish (to'liq statistika)
5. Kutilayotgan buyurtmalar (tugma, modal)
6. Buyurtmalar panel (tugma, modal)
7. Mijozlar (tugma, modal)
8. Kuryerlar (tugma, modal, do'kon azoligi)
9. Do'konlar (tugma, modal)
10. Muammoli (id, kim yozgan, qanday muammo)
11. Oylik hisobot (foyiz, summa)
12. Do'kon login/parol paneli
13. Do'kon egalari uchun AI chat
"""

import os
import json
import psycopg2
import requests
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template_string, request, session, redirect, url_for, jsonify

# ===================== CONFIG =====================
DATABASE_URL = os.environ.get("DATABASE_URL")
ADMIN_WEB_USER = os.environ.get("ADMIN_WEB_USER", "admin")
ADMIN_WEB_PASS = os.environ.get("ADMIN_WEB_PASS", "admin123")
SECRET_KEY = os.environ.get("SECRET_KEY", "olimbek-savdo-secret-2024")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

app = Flask(__name__)
app.secret_key = SECRET_KEY

# ===================== DB =====================
def get_db():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return conn

def db_query(sql, params=None, fetchone=False, fetchall=False, commit=False):
    conn = get_db()
    c = conn.cursor()
    c.execute(sql, params or ())
    result = None
    if fetchone:
        result = c.fetchone()
    elif fetchall:
        result = c.fetchall()
    if commit:
        conn.commit()
    conn.close()
    return result

# ===================== AUTH =====================
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect('/admin/login')
        return f(*args, **kwargs)
    return decorated

def shop_login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('shop_logged_in'):
            return redirect('/shop/login')
        return f(*args, **kwargs)
    return decorated

# ===================== AI HELPER =====================
def call_ai(system_prompt, user_message, history=None):
    """Groq yoki Anthropic API orqali AI javob olish"""
    messages = []
    if history:
        for h in history:
            messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": user_message})

    # Try Anthropic first
    if ANTHROPIC_API_KEY:
        try:
            r = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 1024,
                    "system": system_prompt,
                    "messages": messages
                },
                timeout=30
            )
            data = r.json()
            if "content" in data:
                return data["content"][0]["text"]
        except:
            pass

    # Fallback to Groq
    if GROQ_API_KEY:
        try:
            msgs = [{"role": "system", "content": system_prompt}] + messages
            r = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                json={"model": "llama3-8b-8192", "messages": msgs, "max_tokens": 1024},
                timeout=30
            )
            data = r.json()
            return data["choices"][0]["message"]["content"]
        except:
            pass

    return "AI xizmat hozir mavjud emas. API kalitlarini tekshiring."


def get_system_stats_text(shop_id=None):
    """DB dan statistika olib matn ko'rinishida qaytarish"""
    try:
        conn = get_db()
        c = conn.cursor()
        today = datetime.now().strftime("%d.%m.%Y")

        if shop_id:
            # Do'kon statistikasi
            c.execute("SELECT * FROM shops WHERE id=%s", (shop_id,))
            shop = c.fetchone()
            if not shop:
                conn.close()
                return "Do'kon topilmadi"

            c.execute("SELECT COUNT(*) as cnt FROM orders WHERE shop_id=%s AND status='delivered'", (shop_id,))
            total_orders = c.fetchone()['cnt']
            c.execute("SELECT COALESCE(SUM(total_sum),0) as t FROM orders WHERE shop_id=%s AND status='delivered'", (shop_id,))
            total_income = c.fetchone()['t']
            c.execute("SELECT COUNT(*) as cnt FROM orders WHERE shop_id=%s AND created_at LIKE %s", (shop_id, f"{today}%"))
            today_orders = c.fetchone()['cnt']
            c.execute("SELECT COALESCE(SUM(total_sum),0) as t FROM orders WHERE shop_id=%s AND status='delivered' AND created_at LIKE %s", (shop_id, f"{today}%"))
            today_income = c.fetchone()['t']
            c.execute("SELECT COUNT(*) as cnt FROM orders WHERE shop_id=%s AND status='pending'", (shop_id,))
            pending = c.fetchone()['cnt']
            c.execute("SELECT COUNT(*) as cnt, SUM(CASE WHEN is_busy=0 THEN 1 ELSE 0 END) as free FROM couriers WHERE shop_id=%s AND is_blocked=0", (shop_id,))
            couriers_row = c.fetchone()
            c.execute("SELECT * FROM products WHERE shop_id=%s AND (is_available IS NULL OR is_available=1)", (shop_id,))
            products = c.fetchall()

            # 7 kunlik
            week_stats = []
            for i in range(6, -1, -1):
                d = (datetime.now() - timedelta(days=i)).strftime("%d.%m.%Y")
                c.execute("SELECT COUNT(*) as cnt, COALESCE(SUM(total_sum),0) as inc FROM orders WHERE shop_id=%s AND status='delivered' AND created_at LIKE %s", (shop_id, f"{d}%"))
                row = c.fetchone()
                week_stats.append(f"{d}: {row['cnt']} buyurtma, {int(row['inc']):,} so'm")

            conn.close()
            total_c = couriers_row['cnt'] if couriers_row else 0
            free_c = couriers_row['free'] if couriers_row else 0
            prod_list = ", ".join([f"{p['name']} ({p['price']:,.0f} so'm)" for p in products[:10]])

            return f"""DO'KON: {shop['name']} (ID: {shop_id})
Egasi TG: {shop['owner_tg_id']}
Holat: {'Ochiq' if shop['is_open'] else 'Yopiq'}
Ish vaqti: {shop['work_time'] or 'Noma\'lum'}
Ochilgan: {shop['created_at'] or 'Noma\'lum'}
Reyting: {shop['rating']:.1f} ({shop['rating_count']} ovoz)
Admin foizi: {shop['admin_percent']}%

STATISTIKA:
- Jami buyurtmalar: {total_orders}
- Jami daromad: {total_income:,.0f} so'm
- Bugun buyurtmalar: {today_orders}
- Bugun daromad: {today_income:,.0f} so'm
- Kutilayotgan: {pending}

KURYERLAR: {total_c} ta jami, {free_c} ta bo'sh, {total_c - free_c} ta band

MAHSULOTLAR: {prod_list}

7 KUNLIK:
{chr(10).join(week_stats)}"""

        else:
            # Admin uchun umumiy statistika
            c.execute("SELECT COUNT(*) as cnt FROM users")
            users = c.fetchone()['cnt']
            c.execute("SELECT COUNT(*) as cnt FROM shops")
            shops = c.fetchone()['cnt']
            c.execute("SELECT COUNT(*) as cnt FROM shops WHERE is_open=1")
            open_shops = c.fetchone()['cnt']
            c.execute("SELECT COUNT(*) as cnt FROM couriers")
            couriers = c.fetchone()['cnt']
            c.execute("SELECT COUNT(*) as cnt FROM orders")
            total_orders = c.fetchone()['cnt']
            c.execute("SELECT COUNT(*) as cnt FROM orders WHERE status='delivered'")
            delivered = c.fetchone()['cnt']
            c.execute("SELECT COALESCE(SUM(total_sum),0) as t FROM orders WHERE status='delivered'")
            total_income = c.fetchone()['t']
            c.execute("SELECT COUNT(*) as cnt FROM orders WHERE created_at LIKE %s", (f"{today}%",))
            today_orders = c.fetchone()['cnt']
            c.execute("SELECT COALESCE(SUM(total_sum),0) as t FROM orders WHERE status='delivered' AND created_at LIKE %s", (f"{today}%",))
            today_income = c.fetchone()['t']
            c.execute("SELECT COUNT(*) as cnt FROM orders WHERE status='pending'")
            pending = c.fetchone()['cnt']
            c.execute("SELECT COUNT(*) as cnt FROM orders WHERE status='on_way'")
            on_way = c.fetchone()['cnt']
            c.execute("SELECT COUNT(*) as cnt FROM couriers WHERE is_busy=1 AND is_blocked=0")
            busy_c = c.fetchone()['cnt']
            c.execute("SELECT COUNT(*) as cnt FROM couriers WHERE is_busy=0 AND is_blocked=0")
            free_c = c.fetchone()['cnt']

            # Top do'konlar
            c.execute("""SELECT s.name, COUNT(o.id) as cnt, COALESCE(SUM(o.total_sum),0) as inc
                        FROM shops s LEFT JOIN orders o ON s.id=o.shop_id AND o.status='delivered'
                        GROUP BY s.id, s.name ORDER BY inc DESC LIMIT 5""")
            top_shops = c.fetchall()
            top_text = "\n".join([f"  {i+1}. {s['name']}: {s['cnt']} buyurtma, {int(s['inc']):,} so'm" for i, s in enumerate(top_shops)])

            conn.close()
            return f"""TIZIM STATISTIKASI:
Sana: {datetime.now().strftime("%d.%m.%Y %H:%M")}

FOYDALANUVCHILAR: {users} ta jami
DO'KONLAR: {shops} ta jami ({open_shops} ta ochiq, {shops-open_shops} ta yopiq)
KURYERLAR: {couriers} ta ({free_c} ta bo'sh, {busy_c} ta band)

BUYURTMALAR:
- Jami: {total_orders}
- Yetkazildi: {delivered}
- Kutilayotgan: {pending}
- Yo'lda: {on_way}
- Bugun: {today_orders}

DAROMAD:
- Jami: {total_income:,.0f} so'm
- Bugun: {today_income:,.0f} so'm

TOP DO'KONLAR:
{top_text}"""
    except Exception as e:
        return f"Statistika olishda xatolik: {str(e)}"


# ===================== LOGIN PAGE =====================
LOGIN_HTML = '''<!DOCTYPE html>
<html lang="uz">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Kirish — Olimbek SAVDO Admin</title>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@600;700;800&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box;}
body{min-height:100vh;background:#080c18;font-family:'DM Sans',sans-serif;display:flex;overflow:hidden;}
.bg-animated{position:fixed;inset:0;z-index:0;
  background:radial-gradient(ellipse 80% 60% at 20% 40%, rgba(0,212,170,0.12) 0%, transparent 60%),
             radial-gradient(ellipse 60% 50% at 80% 60%, rgba(14,165,233,0.10) 0%, transparent 60%);
  animation:bgmove 8s ease-in-out infinite alternate;}
@keyframes bgmove{0%{opacity:0.8;}100%{opacity:1;}}
.grid-overlay{position:fixed;inset:0;z-index:0;
  background-image:linear-gradient(rgba(0,212,170,0.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0,212,170,0.04) 1px, transparent 1px);
  background-size:60px 60px;}
.left-panel{flex:1;display:flex;flex-direction:column;justify-content:center;padding:80px;position:relative;z-index:1;}
.brand-title{font-family:'Syne',sans-serif;font-size:64px;font-weight:800;line-height:1.05;margin-bottom:20px;}
.brand-title span.green{color:#00d4aa;}
.brand-title span.white{color:#e2e8f0;}
.brand-desc{font-size:17px;color:#64748b;font-weight:300;line-height:1.7;max-width:420px;}
.right-panel{width:480px;min-height:100vh;display:flex;align-items:center;justify-content:center;
  background:rgba(17,24,39,0.85);backdrop-filter:blur(20px);border-left:1px solid rgba(255,255,255,0.06);
  position:relative;z-index:1;padding:40px;}
.login-box{width:100%;max-width:380px;}
.login-title{font-family:'Syne',sans-serif;font-size:28px;font-weight:800;color:#f1f5f9;margin-bottom:8px;}
.login-sub{font-size:14px;color:#64748b;margin-bottom:32px;}
.error-box{background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.25);border-radius:10px;
  padding:12px 16px;margin-bottom:20px;font-size:13px;color:#f87171;}
.field{margin-bottom:20px;}
.field label{display:block;font-size:12px;font-weight:600;color:#64748b;letter-spacing:0.5px;text-transform:uppercase;margin-bottom:8px;}
.field input{width:100%;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);
  border-radius:12px;padding:14px 16px;color:#e2e8f0;font-size:14px;outline:none;transition:all 0.2s;}
.field input:focus{border-color:#00d4aa;background:rgba(0,212,170,0.05);box-shadow:0 0 0 3px rgba(0,212,170,0.1);}
.submit-btn{width:100%;background:linear-gradient(135deg,#00d4aa,#0ea5e9);color:#000;font-weight:700;
  font-size:15px;padding:14px;border:none;border-radius:12px;cursor:pointer;font-family:'DM Sans',sans-serif;
  transition:all 0.2s;}
.submit-btn:hover{opacity:0.9;transform:translateY(-1px);}
.shop-link{text-align:center;margin-top:20px;font-size:13px;color:#64748b;}
.shop-link a{color:#00d4aa;text-decoration:none;}
@media(max-width:768px){.left-panel{display:none;}.right-panel{width:100%;}}
</style>
</head>
<body>
<div class="bg-animated"></div>
<div class="grid-overlay"></div>
<div class="left-panel">
  <div class="brand-title">
    <span class="green">Olimbek</span><br>
    <span class="white">SAVDO</span>
  </div>
  <div class="brand-desc">Yetkazib berish tizimi — Admin boshqaruv paneli. Barcha do'konlar, buyurtmalar va kuryerlarni nazorat qiling.</div>
</div>
<div class="right-panel">
  <div class="login-box">
    <div class="login-title">🔐 Admin Kirish</div>
    <div class="login-sub">Boshqaruv paneliga kirish</div>
    {% if error %}<div class="error-box">⚠️ {{ error }}</div>{% endif %}
    <form method="POST">
      <div class="field"><label>Username</label><input type="text" name="username" placeholder="admin" required autofocus></div>
      <div class="field"><label>Parol</label><input type="password" name="password" placeholder="••••••••" required></div>
      <button type="submit" class="submit-btn">🔐 Kirish</button>
    </form>
    <div class="shop-link">Do'kon egasi? <a href="/shop/login">Do'kon paneliga kirish</a></div>
  </div>
</div>
</body>
</html>'''

# ===================== SHOP LOGIN PAGE =====================
SHOP_LOGIN_HTML = '''<!DOCTYPE html>
<html lang="uz">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Do'kon Kirish — Olimbek SAVDO</title>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@600;700;800&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box;}
body{min-height:100vh;background:#080c18;font-family:'DM Sans',sans-serif;display:flex;align-items:center;justify-content:center;}
.box{background:rgba(17,24,39,0.95);border:1px solid rgba(255,255,255,0.1);border-radius:20px;padding:40px;width:380px;max-width:95vw;}
.title{font-family:'Syne',sans-serif;font-size:24px;font-weight:800;color:#00d4aa;margin-bottom:8px;}
.sub{font-size:13px;color:#64748b;margin-bottom:28px;}
.error{background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.3);border-radius:8px;padding:10px 14px;margin-bottom:16px;font-size:13px;color:#f87171;}
.field{margin-bottom:16px;}
.field label{display:block;font-size:12px;color:#64748b;margin-bottom:6px;font-weight:500;}
.field input{width:100%;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);border-radius:10px;
  padding:12px 14px;color:#e2e8f0;font-size:13px;outline:none;transition:all 0.2s;}
.field input:focus{border-color:#00d4aa;}
.btn{width:100%;background:linear-gradient(135deg,#00d4aa,#0ea5e9);color:#000;font-weight:700;font-size:14px;
  padding:12px;border:none;border-radius:10px;cursor:pointer;font-family:'DM Sans',sans-serif;}
.admin-link{text-align:center;margin-top:16px;font-size:12px;color:#64748b;}
.admin-link a{color:#00d4aa;text-decoration:none;}
</style>
</head>
<body>
<div class="box">
  <div class="title">🏪 Do'kon Paneli</div>
  <div class="sub">Do'kon ID va parolingizni kiriting</div>
  {% if error %}<div class="error">⚠️ {{ error }}</div>{% endif %}
  <form method="POST">
    <div class="field"><label>Do'kon ID</label><input type="text" name="shop_id" placeholder="123456" required autofocus></div>
    <div class="field"><label>Parol</label><input type="password" name="password" placeholder="••••••••" required></div>
    <button type="submit" class="btn">🔐 Kirish</button>
  </form>
  <div class="admin-link"><a href="/admin/login">← Admin panelga kirish</a></div>
</div>
</body>
</html>'''

# ===================== MAIN DASHBOARD HTML =====================
DASHBOARD_HTML = '''<!DOCTYPE html>
<html lang="uz">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Admin Panel — Olimbek SAVDO</title>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<style>
:root{--bg:#0a0e1a;--surface:#111827;--surface2:#1a2235;--border:#1e2d45;
  --accent:#00d4aa;--accent2:#0ea5e9;--accent3:#f59e0b;--danger:#ef4444;
  --text:#e2e8f0;--text2:#94a3b8;--green:#22c55e;--sidebar-w:260px;}
*{margin:0;padding:0;box-sizing:border-box;}
body{background:#080c18;color:var(--text);font-family:'DM Sans',sans-serif;display:flex;min-height:100vh;overflow-x:hidden;}
body::before{content:'';position:fixed;inset:0;z-index:0;
  background:radial-gradient(ellipse 70% 50% at 10% 30%, rgba(0,212,170,0.08) 0%, transparent 60%),
             radial-gradient(ellipse 50% 40% at 90% 70%, rgba(14,165,233,0.07) 0%, transparent 60%);pointer-events:none;}
body::after{content:'';position:fixed;inset:0;z-index:0;
  background-image:linear-gradient(rgba(0,212,170,0.025) 1px, transparent 1px),
    linear-gradient(90deg,rgba(0,212,170,0.025) 1px, transparent 1px);background-size:60px 60px;pointer-events:none;}
.sidebar{width:var(--sidebar-w);background:rgba(17,24,39,0.92);backdrop-filter:blur(24px);
  border-right:1px solid rgba(255,255,255,0.07);display:flex;flex-direction:column;
  position:fixed;height:100vh;overflow:hidden;z-index:100;box-shadow:4px 0 32px rgba(0,0,0,0.4);}
.sidebar-nav{padding:8px 0;flex:1;overflow-y:auto;overflow-x:hidden;scrollbar-width:none;}
.sidebar-nav::-webkit-scrollbar{display:none;}
.sidebar-logo{padding:20px 20px 16px;border-bottom:1px solid rgba(255,255,255,0.07);flex-shrink:0;}
.sidebar-logo h1{font-family:'Syne',sans-serif;font-size:20px;font-weight:800;
  background:linear-gradient(135deg,#00d4aa,#0ea5e9);-webkit-background-clip:text;-webkit-text-fill-color:transparent;}
.sidebar-logo span{font-size:11px;color:#475569;display:block;margin-top:2px;}
.nav-group{padding:12px 20px 4px;font-size:9px;font-weight:700;color:#334155;letter-spacing:2px;text-transform:uppercase;}
.nav-item{display:flex;align-items:center;gap:11px;padding:10px 20px;color:#64748b;text-decoration:none;
  font-size:13px;font-weight:500;transition:all 0.18s;cursor:pointer;border:none;background:none;
  width:100%;text-align:left;border-left:2px solid transparent;}
.nav-item:hover{color:#e2e8f0;background:rgba(255,255,255,0.04);border-left-color:rgba(0,212,170,0.4);}
.nav-item.active{color:#e2e8f0;background:rgba(0,212,170,0.08);border-left-color:#00d4aa;}
.nav-item .icon{font-size:15px;width:22px;text-align:center;flex-shrink:0;}
.nav-badge{margin-left:auto;background:linear-gradient(135deg,#ef4444,#f59e0b);color:#fff;font-size:10px;
  padding:2px 8px;border-radius:20px;font-weight:700;}
.sidebar-footer{padding:16px 20px;border-top:1px solid rgba(255,255,255,0.07);font-size:11px;color:#475569;background:rgba(0,0,0,0.2);}
.admin-info{display:flex;align-items:center;gap:8px;background:rgba(0,212,170,0.06);border:1px solid rgba(0,212,170,0.15);
  border-radius:10px;padding:8px 12px;margin-bottom:8px;}
.admin-avatar{width:28px;height:28px;background:linear-gradient(135deg,#00d4aa,#0ea5e9);border-radius:8px;
  display:flex;align-items:center;justify-content:center;font-size:13px;flex-shrink:0;}
.admin-name{font-size:12px;color:#94a3b8;font-weight:500;}
.admin-role{font-size:10px;color:#00d4aa;}
.sidebar-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,0.6);backdrop-filter:blur(4px);z-index:99;}
.sidebar-overlay.show{display:block;}
.main{margin-left:var(--sidebar-w);flex:1;display:flex;flex-direction:column;min-height:100vh;position:relative;z-index:1;}
.topbar{background:rgba(17,24,39,0.85);backdrop-filter:blur(20px);border-bottom:1px solid rgba(255,255,255,0.07);
  padding:13px 24px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:50;}
.topbar-title{font-family:'Syne',sans-serif;font-size:18px;font-weight:700;}
.topbar-right{display:flex;align-items:center;gap:10px;}
.live-badge{display:flex;align-items:center;gap:6px;background:rgba(34,197,94,0.1);border:1px solid rgba(34,197,94,0.25);
  padding:5px 12px;border-radius:20px;font-size:12px;color:var(--green);}
.live-dot{width:7px;height:7px;background:var(--green);border-radius:50%;animation:pulse 1.5s infinite;}
@keyframes pulse{0%,100%{opacity:1;}50%{opacity:0.3;}}
.logout-btn{background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.25);color:var(--danger);
  padding:6px 14px;border-radius:8px;font-size:12px;cursor:pointer;text-decoration:none;font-weight:500;}
#menu-btn{display:none;}
.menu-btn-inner{background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.1);color:var(--text);
  font-size:20px;cursor:pointer;padding:6px 10px;border-radius:10px;line-height:1;}
.content{padding:22px 24px;flex:1;}
.section-page{display:none;}
.section-page.active{display:block;}
.stats-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:14px;margin-bottom:24px;}
.stat-card{background:rgba(17,24,39,0.8);backdrop-filter:blur(12px);border:1px solid rgba(255,255,255,0.07);
  border-radius:16px;padding:18px;position:relative;overflow:hidden;transition:transform 0.2s,border-color 0.2s;}
.stat-card:hover{transform:translateY(-3px);border-color:rgba(0,212,170,0.3);}
.stat-card::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,var(--c1,#00d4aa),var(--c2,#0ea5e9));}
.stat-icon{font-size:26px;margin-bottom:10px;}
.stat-value{font-family:'Syne',sans-serif;font-size:26px;font-weight:800;}
.stat-label{font-size:12px;color:var(--text2);margin-top:3px;}
.stat-sub{font-size:11px;color:var(--text2);margin-top:5px;}
.card{background:rgba(17,24,39,0.8);backdrop-filter:blur(12px);border:1px solid rgba(255,255,255,0.07);border-radius:16px;overflow:hidden;margin-bottom:18px;}
.card-header{padding:14px 18px;border-bottom:1px solid rgba(255,255,255,0.07);display:flex;align-items:center;justify-content:space-between;}
.card-header h3{font-family:'Syne',sans-serif;font-size:14px;font-weight:700;}
table{width:100%;border-collapse:collapse;font-size:13px;}
thead tr{background:rgba(26,34,53,0.8);}
th{padding:10px 14px;text-align:left;font-size:10px;font-weight:600;color:var(--text2);text-transform:uppercase;letter-spacing:0.8px;}
td{padding:10px 14px;border-top:1px solid rgba(255,255,255,0.05);vertical-align:middle;}
tr:hover td{background:rgba(0,212,170,0.03);}
.badge{display:inline-block;padding:3px 9px;border-radius:20px;font-size:11px;font-weight:600;}
.badge-green{background:rgba(34,197,94,0.15);color:#22c55e;}
.badge-yellow{background:rgba(245,158,11,0.15);color:#f59e0b;}
.badge-red{background:rgba(239,68,68,0.15);color:#ef4444;}
.badge-blue{background:rgba(14,165,233,0.15);color:#0ea5e9;}
.badge-gray{background:rgba(148,163,184,0.15);color:#94a3b8;}
.btn{display:inline-flex;align-items:center;gap:6px;padding:7px 14px;border-radius:8px;font-size:12px;font-weight:500;cursor:pointer;border:none;text-decoration:none;transition:all 0.15s;}
.btn-primary{background:linear-gradient(135deg,#00d4aa,#0ea5e9);color:#000;font-weight:600;}
.btn-primary:hover{opacity:0.88;transform:translateY(-1px);}
.btn-danger{background:rgba(239,68,68,0.1);color:var(--danger);border:1px solid rgba(239,68,68,0.3);}
.btn-ghost{background:rgba(255,255,255,0.05);color:var(--text2);border:1px solid rgba(255,255,255,0.1);}
.btn-success{background:rgba(34,197,94,0.1);color:#22c55e;border:1px solid rgba(34,197,94,0.3);}
.btn-info{background:rgba(14,165,233,0.1);color:#0ea5e9;border:1px solid rgba(14,165,233,0.3);}
.btn-sm{padding:4px 10px;font-size:11px;}
.search-row{display:flex;gap:10px;margin-bottom:18px;align-items:center;flex-wrap:wrap;}
.inp{background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);border-radius:10px;
  padding:9px 14px;color:var(--text);font-size:13px;outline:none;transition:all 0.2s;}
.inp:focus{border-color:#00d4aa;background:rgba(0,212,170,0.05);}
.two-col{display:grid;grid-template-columns:1fr 1fr;gap:18px;}
.scrollable-table{overflow-x:auto;}
.empty-state{text-align:center;padding:40px;color:var(--text2);}

/* MODAL */
.modal-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,0.75);backdrop-filter:blur(6px);z-index:200;align-items:center;justify-content:center;}
.modal-overlay.open{display:flex;}
.modal{background:rgba(17,24,39,0.98);backdrop-filter:blur(24px);border:1px solid rgba(255,255,255,0.1);
  border-radius:18px;padding:26px;max-width:680px;width:92%;max-height:90vh;overflow-y:auto;box-shadow:0 24px 80px rgba(0,0,0,0.6);}
.modal h2{font-family:'Syne',sans-serif;font-size:17px;margin-bottom:18px;}
.modal-close{float:right;background:none;border:none;color:var(--text2);font-size:20px;cursor:pointer;margin-top:-4px;}
.form-group{margin-bottom:14px;}
.form-label{display:block;font-size:11px;color:var(--text2);margin-bottom:5px;font-weight:500;}
.form-control{width:100%;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);
  border-radius:10px;padding:9px 13px;color:var(--text);font-size:13px;outline:none;transition:all 0.2s;}
.form-control:focus{border-color:#00d4aa;}
.form-row{display:grid;grid-template-columns:1fr 1fr;gap:12px;}
.detail-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px 20px;margin-bottom:16px;}
.detail-item .dl{font-size:11px;color:var(--text2);margin-bottom:3px;}
.detail-item .dv{font-size:13px;font-weight:500;}
.info-section{margin-bottom:16px;padding-bottom:16px;border-bottom:1px solid rgba(255,255,255,0.07);}
.info-section:last-child{border-bottom:none;margin-bottom:0;}
.info-section h4{font-size:12px;font-weight:700;color:var(--accent);margin-bottom:10px;text-transform:uppercase;letter-spacing:0.8px;}

/* AI CHAT */
.ai-chat-btn{position:fixed;bottom:24px;right:24px;width:56px;height:56px;
  background:linear-gradient(135deg,#00d4aa,#0ea5e9);border-radius:50%;display:flex;align-items:center;justify-content:center;
  font-size:24px;cursor:pointer;box-shadow:0 8px 32px rgba(0,212,170,0.4);z-index:150;border:none;transition:all 0.2s;}
.ai-chat-btn:hover{transform:scale(1.1);}
.ai-chat-panel{display:none;position:fixed;bottom:92px;right:24px;width:380px;height:520px;
  background:rgba(17,24,39,0.98);border:1px solid rgba(255,255,255,0.1);border-radius:18px;
  box-shadow:0 24px 80px rgba(0,0,0,0.6);z-index:149;flex-direction:column;overflow:hidden;}
.ai-chat-panel.open{display:flex;}
.ai-chat-header{padding:16px 18px;border-bottom:1px solid rgba(255,255,255,0.07);display:flex;align-items:center;gap:10px;flex-shrink:0;}
.ai-chat-header .ai-icon{width:32px;height:32px;background:linear-gradient(135deg,#00d4aa,#0ea5e9);border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:16px;}
.ai-chat-header .ai-name{font-weight:600;font-size:14px;}
.ai-chat-header .ai-status{font-size:11px;color:var(--green);}
.ai-chat-close{margin-left:auto;background:none;border:none;color:var(--text2);cursor:pointer;font-size:18px;}
.ai-messages{flex:1;overflow-y:auto;padding:14px;display:flex;flex-direction:column;gap:10px;}
.ai-msg{padding:10px 14px;border-radius:12px;max-width:88%;font-size:13px;line-height:1.5;}
.ai-msg.user{background:rgba(0,212,170,0.15);align-self:flex-end;border-bottom-right-radius:4px;}
.ai-msg.ai{background:rgba(255,255,255,0.06);align-self:flex-start;border-bottom-left-radius:4px;}
.ai-msg.ai .ai-label{font-size:10px;color:var(--accent);margin-bottom:4px;font-weight:600;}
.ai-input-row{padding:14px;border-top:1px solid rgba(255,255,255,0.07);display:flex;gap:8px;flex-shrink:0;}
.ai-input{flex:1;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);border-radius:10px;
  padding:9px 12px;color:var(--text);font-size:13px;outline:none;resize:none;}
.ai-input:focus{border-color:#00d4aa;}
.ai-send{background:linear-gradient(135deg,#00d4aa,#0ea5e9);color:#000;border:none;border-radius:8px;
  padding:9px 14px;cursor:pointer;font-weight:600;font-size:13px;}
.ai-typing{display:flex;gap:4px;align-items:center;padding:10px 14px;}
.ai-typing span{width:6px;height:6px;background:var(--text2);border-radius:50%;animation:typing 1.2s infinite;}
.ai-typing span:nth-child(2){animation-delay:0.2s;}
.ai-typing span:nth-child(3){animation-delay:0.4s;}
@keyframes typing{0%,100%{opacity:0.3;transform:translateY(0);}50%{opacity:1;transform:translateY(-4px);}}

/* MONITOR */
.monitor-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:12px;margin-bottom:20px;}
.monitor-card{background:rgba(26,34,53,0.7);border:1px solid rgba(255,255,255,0.07);border-radius:12px;padding:16px;text-align:center;}
.monitor-num{font-family:'Syne',sans-serif;font-size:32px;font-weight:800;margin-bottom:4px;}
.monitor-lbl{font-size:12px;color:var(--text2);}

/* CHAT */
.chat-bubble{padding:10px 14px;border-radius:10px;margin-bottom:8px;max-width:75%;}
.chat-bubble.out{background:rgba(0,212,170,0.1);margin-left:auto;text-align:right;}
.chat-bubble.in{background:rgba(255,255,255,0.05);}
.chat-meta{font-size:10px;color:var(--text2);margin-bottom:3px;}

/* MOBILE */
@media(max-width:768px){
  #menu-btn{display:block !important;}
  .sidebar{transform:translateX(-100%);transition:transform 0.3s;z-index:9999 !important;position:fixed !important;width:280px;}
  .sidebar.open{transform:translateX(0);}
  .main{margin-left:0 !important;}
  .two-col{grid-template-columns:1fr;}
  .stats-grid{grid-template-columns:repeat(2,1fr);}
  .content{padding:12px;}
  table{min-width:600px;}
  .ai-chat-panel{width:calc(100vw - 32px);right:16px;bottom:80px;}
  .form-row{grid-template-columns:1fr;}
  .detail-grid{grid-template-columns:1fr;}
}
</style>
</head>
<body>
<div class="sidebar-overlay" id="sidebar-overlay" onclick="closeSidebar()"></div>
<div class="sidebar" id="sidebar">
  <div class="sidebar-logo">
    <h1>⚡ OLIMBEK SAVDO</h1>
    <span>Admin Panel v3.0</span>
  </div>
  <div class="sidebar-nav">
    <div class="nav-group">ASOSIY</div>
    <button class="nav-item active" onclick="showSection('dashboard','Dashboard')">
      <span class="icon">📊</span> Dashboard
    </button>
    <button class="nav-item" onclick="showSection('monitoring','Monitoring')">
      <span class="icon">👁️</span> Monitoring
      <span class="nav-badge" id="pending-badge">0</span>
    </button>

    <div class="nav-group">BOSHQARUV</div>
    <button class="nav-item" onclick="showSection('orders','Buyurtmalar')">
      <span class="icon">📦</span> Buyurtmalar
    </button>
    <button class="nav-item" onclick="showSection('pending-orders','Kutilayotgan')">
      <span class="icon">⏳</span> Kutilayotgan
    </button>
    <button class="nav-item" onclick="showSection('users','Mijozlar')">
      <span class="icon">👥</span> Mijozlar
    </button>
    <button class="nav-item" onclick="showSection('couriers','Kuryerlar')">
      <span class="icon">🚚</span> Kuryerlar
    </button>
    <button class="nav-item" onclick="showSection('shops','Do\'konlar')">
      <span class="icon">🏪</span> Do'konlar
    </button>

    <div class="nav-group">MOLIYA</div>
    <button class="nav-item" onclick="showSection('finance','Moliya')">
      <span class="icon">💰</span> Moliya
    </button>
    <button class="nav-item" onclick="showSection('monthly-report','Oylik hisobot')">
      <span class="icon">📅</span> Oylik hisobot
    </button>
    <button class="nav-item" onclick="showSection('weekly','Haftalik hisobot')">
      <span class="icon">📈</span> Haftalik hisobot
    </button>
    <button class="nav-item" onclick="showSection('promo','Promo kodlar')">
      <span class="icon">🎟️</span> Promo kodlar
    </button>

    <div class="nav-group">QIDIRUV VA TAHLIL</div>
    <button class="nav-item" onclick="showSection('search','Qidiruv')">
      <span class="icon">🔍</span> Qidiruv
    </button>
    <button class="nav-item" onclick="showSection('problems','Muammoli')">
      <span class="icon">⚠️</span> Muammoli
    </button>
    <button class="nav-item" onclick="showSection('chats','Chatlar')">
      <span class="icon">💬</span> Chatlar
    </button>
    <button class="nav-item" onclick="showSection('top','Top mijozlar')">
      <span class="icon">🏆</span> Top mijozlar
    </button>
    <button class="nav-item" onclick="showSection('blocked','Bloklangan')">
      <span class="icon">🚫</span> Bloklangan
    </button>
    <button class="nav-item" onclick="showSection('admin-orders','Admin buyurtmalari')">
      <span class="icon">📱</span> Admin buyurtmalari
    </button>
  </div>
  <div class="sidebar-footer">
    <div class="admin-info">
      <div class="admin-avatar">👤</div>
      <div>
        <div class="admin-name">{{ username }}</div>
        <div class="admin-role">● Administrator</div>
      </div>
    </div>
    <span id="clock" style="font-size:11px;color:#334155;"></span>
  </div>
</div>

<div class="main">
  <div class="topbar">
    <div style="display:flex;align-items:center;gap:14px;">
      <button onclick="document.getElementById('sidebar').classList.contains('open')?closeSidebar():openSidebar()" class="menu-btn-inner" id="menu-btn">☰</button>
      <div class="topbar-title" id="page-title">Dashboard</div>
    </div>
    <div class="topbar-right">
      <div class="live-badge"><div class="live-dot"></div> JONLI</div>
      <a href="/admin/logout" class="logout-btn">🚪 Chiqish</a>
    </div>
  </div>

  <div class="content">

    <!-- DASHBOARD -->
    <div class="section-page active" id="sec-dashboard">
      <div class="stats-grid" id="stats-grid">
        <div class="stat-card" style="--c1:#00d4aa;--c2:#0ea5e9;"><div class="stat-icon">👥</div><div class="stat-value" id="s-users">—</div><div class="stat-label">Jami mijozlar</div></div>
        <div class="stat-card" style="--c1:#f59e0b;--c2:#ef4444;"><div class="stat-icon">🏪</div><div class="stat-value" id="s-shops">—</div><div class="stat-label">Do'konlar</div><div class="stat-sub" id="s-shops-open"></div></div>
        <div class="stat-card" style="--c1:#8b5cf6;--c2:#ec4899;"><div class="stat-icon">🚚</div><div class="stat-value" id="s-couriers">—</div><div class="stat-label">Kuryerlar</div></div>
        <div class="stat-card" style="--c1:#22c55e;--c2:#00d4aa;"><div class="stat-icon">📦</div><div class="stat-value" id="s-orders">—</div><div class="stat-label">Jami buyurtmalar</div></div>
        <div class="stat-card" style="--c1:#0ea5e9;--c2:#8b5cf6;"><div class="stat-icon">💰</div><div class="stat-value" id="s-income">—</div><div class="stat-label">Jami daromad</div></div>
        <div class="stat-card" style="--c1:#f59e0b;--c2:#22c55e;"><div class="stat-icon">📅</div><div class="stat-value" id="s-today">—</div><div class="stat-label">Bugungi daromad</div></div>
        <div class="stat-card" style="--c1:#ef4444;--c2:#f59e0b;"><div class="stat-icon">⏳</div><div class="stat-value" id="s-pending">—</div><div class="stat-label">Kutilayotgan</div></div>
        <div class="stat-card" style="--c1:#00d4aa;--c2:#22c55e;"><div class="stat-icon">🚗</div><div class="stat-value" id="s-onway">—</div><div class="stat-label">Yo'lda</div></div>
      </div>
      <div class="two-col">
        <div class="card">
          <div class="card-header"><h3>📦 Oxirgi buyurtmalar</h3></div>
          <div class="scrollable-table"><table><thead><tr><th>ID</th><th>Do'kon</th><th>Summa</th><th>Holat</th><th>Vaqt</th></tr></thead><tbody id="recent-orders"></tbody></table></div>
        </div>
        <div class="card">
          <div class="card-header"><h3>🏪 Do'konlar holati</h3></div>
          <div class="scrollable-table"><table><thead><tr><th>Do'kon</th><th>Bugun</th><th>Holat</th><th>Reyting</th></tr></thead><tbody id="shops-status"></tbody></table></div>
        </div>
      </div>
    </div>

    <!-- MONITORING -->
    <div class="section-page" id="sec-monitoring">
      <div class="monitor-grid" id="monitor-cards"></div>
      <div class="two-col">
        <div class="card">
          <div class="card-header"><h3>⏳ Kutilayotgan buyurtmalar</h3><button class="btn btn-ghost" onclick="loadMonitoring()">🔄</button></div>
          <div class="scrollable-table"><table><thead><tr><th>ID</th><th>Do'kon</th><th>Summa</th><th>Kutish</th><th>Status</th><th></th></tr></thead><tbody id="pending-orders-list"></tbody></table></div>
        </div>
        <div class="card">
          <div class="card-header"><h3>🟢 Bo'sh kuryerlar</h3></div>
          <div class="scrollable-table"><table><thead><tr><th>Ism</th><th>Tel</th><th>Do'kon</th></tr></thead><tbody id="free-couriers-list"></tbody></table></div>
        </div>
      </div>
    </div>

    <!-- ORDERS -->
    <div class="section-page" id="sec-orders">
      <div class="search-row">
        <select class="inp" id="order-status-filter" onchange="loadOrders()">
          <option value="">Barcha statuslar</option>
          <option value="pending">⏳ Kutilmoqda</option>
          <option value="confirmed">✅ Tasdiqlandi</option>
          <option value="on_way">🚗 Yo'lda</option>
          <option value="delivered">✅ Yetkazildi</option>
          <option value="rejected">❌ Rad etildi</option>
        </select>
        <input class="inp" style="flex:1;" type="text" id="order-search" placeholder="🔍 ID yoki manzil..." oninput="loadOrders()">
        <button class="btn btn-ghost" onclick="loadOrders()">🔄</button>
      </div>
      <div class="card">
        <div class="card-header"><h3>📦 Buyurtmalar</h3><span id="orders-count" style="color:var(--text2);font-size:12px;"></span></div>
        <div class="scrollable-table"><table><thead><tr><th>ID</th><th>Mijoz</th><th>Do'kon</th><th>Summa</th><th>To'lov</th><th>Holat</th><th>Vaqt</th><th></th></tr></thead><tbody id="orders-table"></tbody></table></div>
      </div>
    </div>

    <!-- PENDING ORDERS -->
    <div class="section-page" id="sec-pending-orders">
      <div class="card">
        <div class="card-header"><h3>⏳ Kutilayotgan buyurtmalar</h3><button class="btn btn-ghost" onclick="loadPendingOrders()">🔄</button></div>
        <div class="scrollable-table"><table><thead><tr><th>ID</th><th>Mijoz</th><th>Do'kon</th><th>Summa</th><th>Kutish</th><th>Vaqt</th><th></th></tr></thead><tbody id="pending-full-table"></tbody></table></div>
      </div>
    </div>

    <!-- USERS -->
    <div class="section-page" id="sec-users">
      <div class="search-row">
        <input class="inp" style="flex:1;" type="text" id="user-search" placeholder="🔍 Ism, telefon, ID..." oninput="loadUsers()">
        <button class="btn btn-ghost" onclick="loadUsers()">🔄</button>
      </div>
      <div class="card">
        <div class="card-header"><h3>👥 Mijozlar</h3><span id="users-count" style="color:var(--text2);font-size:12px;"></span></div>
        <div class="scrollable-table"><table><thead><tr><th>ID</th><th>Ism</th><th>Telefon</th><th>Buyurtmalar</th><th>Xarid</th><th>Holat</th><th></th></tr></thead><tbody id="users-table"></tbody></table></div>
      </div>
    </div>

    <!-- COURIERS -->
    <div class="section-page" id="sec-couriers">
      <div class="search-row">
        <input class="inp" style="flex:1;" type="text" id="courier-search" placeholder="🔍 Ism, telefon..." oninput="loadCouriers()">
        <button class="btn btn-ghost" onclick="loadCouriers()">🔄</button>
      </div>
      <div class="card">
        <div class="card-header"><h3>🚚 Kuryerlar</h3><span id="couriers-count" style="color:var(--text2);font-size:12px;"></span></div>
        <div class="scrollable-table"><table><thead><tr><th>ID</th><th>Ism</th><th>Telefon</th><th>Do'kon</th><th>Yetkazgan</th><th>Band</th><th>Holat</th><th></th></tr></thead><tbody id="couriers-table"></tbody></table></div>
      </div>
    </div>

    <!-- SHOPS -->
    <div class="section-page" id="sec-shops">
      <div class="search-row">
        <input class="inp" style="flex:1;" type="text" id="shop-search" placeholder="🔍 Do'kon nomi..." oninput="loadShops()">
        <button class="btn btn-ghost" onclick="loadShops()">🔄</button>
      </div>
      <div class="card">
        <div class="card-header"><h3>🏪 Do'konlar</h3></div>
        <div class="scrollable-table"><table><thead><tr><th>ID</th><th>Nom</th><th>Tel</th><th>Reyting</th><th>Buyurtmalar</th><th>Daromad</th><th>Admin %</th><th>Holat</th><th></th></tr></thead><tbody id="shops-table"></tbody></table></div>
      </div>
    </div>

    <!-- FINANCE -->
    <div class="section-page" id="sec-finance">
      <div class="stats-grid">
        <div class="stat-card" style="--c1:#22c55e;--c2:#00d4aa;"><div class="stat-icon">💵</div><div class="stat-value" id="f-cash">—</div><div class="stat-label">Naqd to'lovlar</div></div>
        <div class="stat-card" style="--c1:#0ea5e9;--c2:#8b5cf6;"><div class="stat-icon">💳</div><div class="stat-value" id="f-card">—</div><div class="stat-label">Karta to'lovlari</div></div>
        <div class="stat-card" style="--c1:#f59e0b;--c2:#ef4444;"><div class="stat-icon">📊</div><div class="stat-value" id="f-admin">—</div><div class="stat-label">Admin ulushi</div></div>
        <div class="stat-card" style="--c1:#8b5cf6;--c2:#ec4899;"><div class="stat-icon">💰</div><div class="stat-value" id="f-total">—</div><div class="stat-label">Umumiy daromad</div></div>
      </div>
      <div class="card">
        <div class="card-header"><h3>🏪 Do'konlar bo'yicha moliya</h3></div>
        <div class="scrollable-table"><table><thead><tr><th>Do'kon</th><th>Buyurtmalar</th><th>Daromad</th><th>Admin %</th><th>Admin ulushi</th></tr></thead><tbody id="finance-table"></tbody></table></div>
      </div>
    </div>

    <!-- MONTHLY REPORT -->
    <div class="section-page" id="sec-monthly-report">
      <div class="search-row">
        <input class="inp" type="text" id="monthly-search" placeholder="🔍 Do'kon nomi yoki ID..." oninput="loadMonthly()" style="flex:1;">
        <input class="inp" type="number" id="monthly-percent" placeholder="Foyiz % (masalan 10)" min="0" max="100" style="width:180px;">
        <button class="btn btn-ghost" onclick="loadMonthly()">🔄</button>
      </div>
      <div class="card">
        <div class="card-header"><h3>📅 Oylik hisobot (30 kun)</h3></div>
        <div class="scrollable-table"><table><thead><tr><th>ID</th><th>Do'kon nomi</th><th>Buyurtmalar</th><th>30 kunlik daromad</th><th>Bugungi daromad</th><th>Admin %</th><th>Menga keladi</th><th></th></tr></thead><tbody id="monthly-table"></tbody></table></div>
      </div>
    </div>

    <!-- PROMO -->
    <div class="section-page" id="sec-promo">
      <div class="search-row">
        <button class="btn btn-primary" onclick="openModal('promo-modal')">➕ Promo kod qo'shish</button>
        <button class="btn btn-ghost" onclick="loadPromo()">🔄</button>
      </div>
      <div class="card">
        <div class="card-header"><h3>🎟️ Promo kodlar</h3></div>
        <div class="scrollable-table"><table><thead><tr><th>Kod</th><th>Chegirma</th><th>Min summa</th><th>Muddat</th><th>Limit</th><th>Ishlatilgan</th><th>Holat</th><th>Amal</th></tr></thead><tbody id="promo-table"></tbody></table></div>
      </div>
    </div>

    <!-- SEARCH -->
    <div class="section-page" id="sec-search">
      <div class="search-row">
        <select class="inp" id="search-type">
          <option value="all">🔍 Hammasi</option>
          <option value="users">👥 Mijozlar</option>
          <option value="couriers">🚚 Kuryerlar</option>
          <option value="shops">🏪 Do'konlar</option>
          <option value="orders">📦 Buyurtmalar</option>
        </select>
        <input class="inp" style="flex:1;" type="text" id="global-search" placeholder="Ism, telefon, ID, buyurtma raqami..." onkeyup="if(event.key==='Enter')doSearch()">
        <button class="btn btn-primary" onclick="doSearch()">🔍 Qidirish</button>
      </div>
      <div id="search-results"></div>
    </div>

    <!-- PROBLEMS -->
    <div class="section-page" id="sec-problems">
      <div class="card">
        <div class="card-header"><h3>⚠️ Muammoli buyurtmalar</h3><button class="btn btn-ghost" onclick="loadProblems()">🔄</button></div>
        <div class="scrollable-table"><table><thead><tr><th>Muammo ID</th><th>Do'kon</th><th>Kim yozgan</th><th>Muammo</th><th>Kutish</th><th>Vaqt</th><th></th></tr></thead><tbody id="problems-table"></tbody></table></div>
      </div>
    </div>

    <!-- CHATS -->
    <div class="section-page" id="sec-chats">
      <div class="two-col">
        <div class="card">
          <div class="card-header"><h3>💬 Chat ro'yxati</h3><button class="btn btn-ghost" onclick="loadChats()">🔄</button></div>
          <div id="chat-list" style="max-height:500px;overflow-y:auto;"></div>
        </div>
        <div class="card">
          <div class="card-header"><h3>💬 Chat tafsiloti</h3></div>
          <div id="chat-detail" style="padding:14px;max-height:500px;overflow-y:auto;"><div class="empty-state"><p>Chatni tanlang</p></div></div>
        </div>
      </div>
    </div>

    <!-- TOP -->
    <div class="section-page" id="sec-top">
      <div class="card">
        <div class="card-header"><h3>🏆 Top 20 mijozlar</h3></div>
        <div class="scrollable-table"><table><thead><tr><th>#</th><th>Ism</th><th>Telefon</th><th>Buyurtmalar</th><th>Jami xarid</th></tr></thead><tbody id="top-table"></tbody></table></div>
      </div>
    </div>

    <!-- BLOCKED -->
    <div class="section-page" id="sec-blocked">
      <div class="two-col">
        <div class="card">
          <div class="card-header"><h3>🚫 Bloklangan mijozlar</h3></div>
          <div class="scrollable-table"><table><thead><tr><th>Ism</th><th>Telefon</th><th>ID</th><th>Amal</th></tr></thead><tbody id="blocked-users-table"></tbody></table></div>
        </div>
        <div class="card">
          <div class="card-header"><h3>🚫 Bloklangan kuryerlar</h3></div>
          <div class="scrollable-table"><table><thead><tr><th>Ism</th><th>Telefon</th><th>ID</th><th>Amal</th></tr></thead><tbody id="blocked-couriers-table"></tbody></table></div>
        </div>
      </div>
    </div>

    <!-- WEEKLY -->
    <div class="section-page" id="sec-weekly">
      <div class="stats-grid" id="weekly-stats"></div>
      <div class="card">
        <div class="card-header"><h3>📈 Kunlik statistika (7 kun)</h3></div>
        <div class="scrollable-table"><table><thead><tr><th>Kun</th><th>Buyurtmalar</th><th>Daromad</th><th>Yangi mijozlar</th></tr></thead><tbody id="weekly-table"></tbody></table></div>
      </div>
    </div>

    <!-- ADMIN ORDERS -->
    <div class="section-page" id="sec-admin-orders">
      <div class="card">
        <div class="card-header"><h3>📱 Admin buyurtmalari</h3></div>
        <div class="scrollable-table"><table><thead><tr><th>ID</th><th>Do'kon</th><th>Manzil</th><th>Summa</th><th>Holat</th><th>Vaqt</th></tr></thead><tbody id="admin-orders-table"></tbody></table></div>
      </div>
    </div>

  </div><!-- /content -->
</div><!-- /main -->

<!-- AI CHAT BUTTON & PANEL -->
<button class="ai-chat-btn" onclick="toggleAiChat()" title="AI Yordamchi">🤖</button>
<div class="ai-chat-panel" id="ai-chat-panel">
  <div class="ai-chat-header">
    <div class="ai-icon">🤖</div>
    <div><div class="ai-name">AI Yordamchi</div><div class="ai-status">● Faol</div></div>
    <button class="ai-chat-close" onclick="toggleAiChat()">✕</button>
  </div>
  <div class="ai-messages" id="ai-messages">
    <div class="ai-msg ai"><div class="ai-label">AI</div>Salom! Men sizning yordamchingizman. "Tong supermarket bugungi holatini ayt" yoki "bugun nechta buyurtma bo'ldi?" deb so'rang.</div>
  </div>
  <div class="ai-input-row">
    <textarea class="ai-input" id="ai-input" placeholder="Savol yozing..." rows="1" onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();sendAiMsg();}"></textarea>
    <button class="ai-send" onclick="sendAiMsg()">➤</button>
  </div>
</div>

<!-- PROMO MODAL -->
<div class="modal-overlay" id="promo-modal">
  <div class="modal" onclick="event.stopPropagation()">
    <button class="modal-close" onclick="closeModal('promo-modal')">✕</button>
    <h2>🎟️ Yangi Promo Kod</h2>
    <div class="form-row">
      <div class="form-group"><label class="form-label">Kod</label><input class="form-control" id="pm-code" placeholder="SALE20"></div>
      <div class="form-group"><label class="form-label">Tur</label><select class="form-control" id="pm-type"><option value="percent">Foiz %</option><option value="fixed">Belgilangan so'm</option></select></div>
    </div>
    <div class="form-row">
      <div class="form-group"><label class="form-label">Miqdor</label><input class="form-control" id="pm-value" type="number" placeholder="20"></div>
      <div class="form-group"><label class="form-label">Min summa (so'm)</label><input class="form-control" id="pm-min" type="number" placeholder="50000"></div>
    </div>
    <div class="form-row">
      <div class="form-group"><label class="form-label">Kun (0=cheksiz)</label><input class="form-control" id="pm-days" type="number" placeholder="30"></div>
      <div class="form-group"><label class="form-label">Limit (0=cheksiz)</label><input class="form-control" id="pm-limit" type="number" placeholder="100"></div>
    </div>
    <button class="btn btn-primary" onclick="createPromo()">✅ Yaratish</button>
  </div>
</div>

<!-- DETAIL MODAL (universal) -->
<div class="modal-overlay" id="detail-modal">
  <div class="modal" onclick="event.stopPropagation()">
    <button class="modal-close" onclick="closeModal('detail-modal')">✕</button>
    <h2 id="detail-modal-title">Ma'lumotlar</h2>
    <div id="detail-modal-body"></div>
  </div>
</div>

<script>
const fmtNum = n => Number(n||0).toLocaleString('uz-UZ');
const api = async (url, opts={}) => {
  try {
    const r = await fetch(url, {headers:{'Content-Type':'application/json'},...opts});
    return r.json();
  } catch(e){ console.error(e); return {}; }
};

function statusBadge(s){
  const m = {pending:'<span class="badge badge-yellow">⏳ Kutilmoqda</span>',confirmed:'<span class="badge badge-blue">✅ Tasdiqlandi</span>',on_way:'<span class="badge badge-blue">🚗 Yo\'lda</span>',delivered:'<span class="badge badge-green">✅ Yetkazildi</span>',rejected:'<span class="badge badge-red">❌ Rad etildi</span>'};
  return m[s]||`<span class="badge badge-gray">${s}</span>`;
}

let activeSec = 'dashboard';
function showSection(id, title){
  document.querySelectorAll('.section-page').forEach(e=>e.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(e=>e.classList.remove('active'));
  document.getElementById('sec-'+id).classList.add('active');
  document.getElementById('page-title').textContent = title||id;
  event && event.currentTarget && event.currentTarget.classList.add('active');
  activeSec = id;
  const loaders = {dashboard:loadDashboard,monitoring:loadMonitoring,orders:loadOrders,
    'pending-orders':loadPendingOrders,users:loadUsers,couriers:loadCouriers,
    shops:loadShops,finance:loadFinance,'monthly-report':loadMonthly,promo:loadPromo,
    search:()=>{},problems:loadProblems,chats:loadChats,top:loadTop,
    blocked:loadBlocked,weekly:loadWeekly,'admin-orders':loadAdminOrders};
  if(loaders[id]) loaders[id]();
}

// CLOCK
setInterval(()=>{
  const el=document.getElementById('clock');
  if(el) el.textContent = new Date().toLocaleString('uz-UZ');
},1000);

// OPEN/CLOSE SIDEBAR
function closeSidebar(){document.getElementById('sidebar').classList.remove('open');document.getElementById('sidebar-overlay').classList.remove('show');}
function openSidebar(){document.getElementById('sidebar').classList.add('open');document.getElementById('sidebar-overlay').classList.add('show');}

// MODAL
function openModal(id){document.getElementById(id).classList.add('open');}
function closeModal(id){document.getElementById(id).classList.remove('open');}
document.querySelectorAll('.modal-overlay').forEach(m=>m.addEventListener('click',e=>{if(e.target===m)m.classList.remove('open');}));

function showDetail(title, html){
  document.getElementById('detail-modal-title').textContent = title;
  document.getElementById('detail-modal-body').innerHTML = html;
  openModal('detail-modal');
}

// ===== DASHBOARD =====
async function loadDashboard(){
  const d = await api('/admin/api/dashboard');
  document.getElementById('s-users').textContent = d.users||0;
  document.getElementById('s-shops').textContent = d.shops||0;
  document.getElementById('s-shops-open').textContent = `${d.shops_open||0} ta ochiq`;
  document.getElementById('s-couriers').textContent = d.couriers||0;
  document.getElementById('s-orders').textContent = d.total_orders||0;
  document.getElementById('s-income').textContent = fmtNum(d.total_income)+' so\'m';
  document.getElementById('s-today').textContent = fmtNum(d.today_income)+' so\'m';
  document.getElementById('s-pending').textContent = d.pending||0;
  document.getElementById('s-onway').textContent = d.on_way||0;
  document.getElementById('pending-badge').textContent = d.pending||0;

  document.getElementById('recent-orders').innerHTML = (d.recent_orders||[]).map(o=>`<tr>
    <td><code>#${o.order_uid}</code></td><td>${o.shop_name||'—'}</td>
    <td>${fmtNum(o.total_sum)} so'm</td><td>${statusBadge(o.status)}</td>
    <td style="font-size:11px;">${o.created_at}</td>
  </tr>`).join('');

  document.getElementById('shops-status').innerHTML = (d.shops_info||[]).map(s=>`<tr>
    <td>${s.name}</td><td>${s.today_count} ta</td>
    <td>${s.is_open?'<span class="badge badge-green">🟢 Ochiq</span>':'<span class="badge badge-red">🔴 Yopiq</span>'}</td>
    <td>⭐${Number(s.rating||0).toFixed(1)}</td>
  </tr>`).join('');
}

// ===== MONITORING =====
async function loadMonitoring(){
  const d = await api('/admin/api/monitoring');
  document.getElementById('monitor-cards').innerHTML = `
    <div class="monitor-card"><div class="monitor-num" style="color:#f59e0b;">${d.pending}</div><div class="monitor-lbl">⏳ Kutilayotgan</div></div>
    <div class="monitor-card"><div class="monitor-num" style="color:#0ea5e9;">${d.on_way}</div><div class="monitor-lbl">🚗 Yo'lda</div></div>
    <div class="monitor-card"><div class="monitor-num" style="color:#22c55e;">${d.free_couriers}</div><div class="monitor-lbl">🟢 Bo'sh kuryer</div></div>
    <div class="monitor-card"><div class="monitor-num" style="color:#ef4444;">${d.busy_couriers}</div><div class="monitor-lbl">🔴 Band kuryer</div></div>
    <div class="monitor-card"><div class="monitor-num" style="color:#00d4aa;">${d.open_shops}</div><div class="monitor-lbl">🏪 Ochiq do'kon</div></div>
    <div class="monitor-card"><div class="monitor-num" style="color:#8b5cf6;">${d.last_hour}</div><div class="monitor-lbl">🕐 Oxirgi 1 soat</div></div>
  `;
  document.getElementById('pending-orders-list').innerHTML = (d.pending_orders||[]).map(o=>`<tr>
    <td><code>#${o.order_uid}</code></td><td>${o.shop_name||'—'}</td>
    <td>${fmtNum(o.total_sum)} so'm</td>
    <td>${o.wait_min} daq${o.wait_min>=10?' <span style="color:var(--danger);">🔴</span>':''}</td>
    <td>${statusBadge(o.status)}</td>
    <td><button class="btn btn-info btn-sm" onclick="showOrderDetail('${o.order_uid}')">👁️</button></td>
  </tr>`).join('') || "<tr><td colspan='6' class='empty-state'>✅ Muammo yo'q</td></tr>";
  document.getElementById('free-couriers-list').innerHTML = (d.free_couriers_list||[]).map(c=>`<tr>
    <td>${c.full_name}</td><td>${c.phone}</td><td>${c.shop_name||'—'}</td>
  </tr>`).join('') || "<tr><td colspan='3' class='empty-state'>Bo'sh kuryer yo'q</td></tr>";
}

// ===== ORDERS =====
async function loadOrders(){
  const status = document.getElementById('order-status-filter').value;
  const search = document.getElementById('order-search').value;
  const d = await api(`/admin/api/orders?status=${status}&search=${encodeURIComponent(search)}`);
  document.getElementById('orders-count').textContent = (d.total||0)+' ta';
  document.getElementById('orders-table').innerHTML = (d.orders||[]).map(o=>`<tr>
    <td><code>#${o.order_uid}</code></td>
    <td>${o.user_name||'Tel buyurtma'}<br><small style="color:var(--text2);">${o.user_phone||''}</small></td>
    <td>${o.shop_name||'—'}</td>
    <td>${fmtNum(o.total_sum)} so'm</td>
    <td>${o.payment_type}</td>
    <td>${statusBadge(o.status)}</td>
    <td style="font-size:11px;">${o.created_at}</td>
    <td><button class="btn btn-info btn-sm" onclick="showOrderDetail('${o.order_uid}')">👁️ Ko'rish</button></td>
  </tr>`).join('') || "<tr><td colspan='8' class='empty-state'>Buyurtma yo'q</td></tr>";
}

// ===== PENDING ORDERS =====
async function loadPendingOrders(){
  const d = await api('/admin/api/monitoring');
  document.getElementById('pending-full-table').innerHTML = (d.pending_orders||[]).map(o=>`<tr>
    <td><code>#${o.order_uid}</code></td>
    <td>${o.user_name||'Tel buyurtma'}</td>
    <td>${o.shop_name||'—'}</td>
    <td>${fmtNum(o.total_sum)} so'm</td>
    <td style="${o.wait_min>=10?'color:var(--danger);font-weight:700;':''}">${o.wait_min} daqiqa</td>
    <td style="font-size:11px;">${o.created_at}</td>
    <td><button class="btn btn-info btn-sm" onclick="showOrderDetail('${o.order_uid}')">👁️ Ko'rish</button></td>
  </tr>`).join('') || "<tr><td colspan='7' class='empty-state'>✅ Kutilayotgan yo'q</td></tr>";
}

// ===== SHOW ORDER DETAIL =====
async function showOrderDetail(uid){
  const d = await api(`/admin/api/order-detail?uid=${uid}`);
  if(!d.order){ showDetail('Buyurtma', '<p>Topilmadi</p>'); return; }
  const o = d.order;
  const statusMap = {pending:'⏳ Kutilmoqda',confirmed:'✅ Tasdiqlandi',on_way:'🚗 Yo\'lda',delivered:'✅ Yetkazildi',rejected:'❌ Rad etildi'};
  let html = `
  <div class="info-section">
    <h4>📦 Buyurtma ma'lumotlari</h4>
    <div class="detail-grid">
      <div class="detail-item"><div class="dl">Buyurtma ID</div><div class="dv"><code>#${o.order_uid}</code></div></div>
      <div class="detail-item"><div class="dl">Holat</div><div class="dv">${statusMap[o.status]||o.status}</div></div>
      <div class="detail-item"><div class="dl">Do'kon</div><div class="dv">${o.shop_name||'—'}</div></div>
      <div class="detail-item"><div class="dl">Summa</div><div class="dv">${fmtNum(o.total_sum)} so'm</div></div>
      <div class="detail-item"><div class="dl">To'lov turi</div><div class="dv">${o.payment_type}</div></div>
      <div class="detail-item"><div class="dl">Manzil</div><div class="dv">${o.address}</div></div>
      <div class="detail-item"><div class="dl">Qabul qilgan</div><div class="dv">${o.created_at||'—'}</div></div>
      <div class="detail-item"><div class="dl">Yo'lda bosgan</div><div class="dv">${o.confirmed_at||'—'}</div></div>
      <div class="detail-item"><div class="dl">Yetib borgan</div><div class="dv">${o.delivered_at||'—'}</div></div>
      <div class="detail-item"><div class="dl">Mahsulotlar</div><div class="dv">${o.products}</div></div>
    </div>
  </div>`;
  if(d.user){
    html += `<div class="info-section"><h4>👤 Mijoz</h4><div class="detail-grid">
      <div class="detail-item"><div class="dl">Ism</div><div class="dv">${d.user.full_name}</div></div>
      <div class="detail-item"><div class="dl">ID</div><div class="dv">${d.user.id}</div></div>
      <div class="detail-item"><div class="dl">Familya</div><div class="dv">${d.user.full_name}</div></div>
      <div class="detail-item"><div class="dl">Telefon</div><div class="dv">${d.user.phone}</div></div>
    </div></div>`;
  }
  if(d.courier){
    html += `<div class="info-section"><h4>🚚 Kuryer</h4><div class="detail-grid">
      <div class="detail-item"><div class="dl">Ism</div><div class="dv">${d.courier.full_name}</div></div>
      <div class="detail-item"><div class="dl">Telefon</div><div class="dv">${d.courier.phone}</div></div>
      <div class="detail-item"><div class="dl">ID</div><div class="dv">${d.courier.id}</div></div>
      <div class="detail-item"><div class="dl">Do'kon</div><div class="dv">${d.courier.shop_name||'—'}</div></div>
    </div></div>`;
  }
  if(o.payment_type === 'karta' && o.check_photo){
    html += `<div class="info-section"><h4>💳 Karta cheki</h4><img src="${o.check_photo}" style="max-width:100%;border-radius:8px;" onerror="this.style.display='none'"></div>`;
  }
  showDetail(`Buyurtma #${o.order_uid}`, html);
}

// ===== USERS =====
async function loadUsers(){
  const search = document.getElementById('user-search').value;
  const d = await api(`/admin/api/users?search=${encodeURIComponent(search)}`);
  document.getElementById('users-count').textContent = (d.total||0)+' ta';
  document.getElementById('users-table').innerHTML = (d.users||[]).map(u=>`<tr>
    <td>${u.id}</td><td>${u.full_name}</td><td>${u.phone}</td>
    <td>${u.order_count}</td><td>${fmtNum(u.total_spent)} so'm</td>
    <td>${u.is_blocked?'<span class="badge badge-red">🚫</span>':'<span class="badge badge-green">✅</span>'}</td>
    <td style="display:flex;gap:4px;">
      <button class="btn btn-info btn-sm" onclick="showUserDetail(${u.tg_id})">👁️</button>
      ${u.is_blocked
        ? `<button class="btn btn-success btn-sm" onclick="toggleUser(${u.tg_id},0)">✅</button>`
        : `<button class="btn btn-danger btn-sm" onclick="toggleUser(${u.tg_id},1)">🚫</button>`}
    </td>
  </tr>`).join('');
}

async function showUserDetail(tg_id){
  const d = await api(`/admin/api/user-detail?tg_id=${tg_id}`);
  if(!d.user){ showDetail('Mijoz', '<p>Topilmadi</p>'); return; }
  const u = d.user;
  let html = `<div class="info-section"><h4>👤 Mijoz ma'lumotlari</h4><div class="detail-grid">
    <div class="detail-item"><div class="dl">ID</div><div class="dv">${u.id}</div></div>
    <div class="detail-item"><div class="dl">TG ID</div><div class="dv">${u.tg_id}</div></div>
    <div class="detail-item"><div class="dl">Ism Familya</div><div class="dv">${u.full_name}</div></div>
    <div class="detail-item"><div class="dl">Telefon</div><div class="dv">${u.phone}</div></div>
    <div class="detail-item"><div class="dl">Username</div><div class="dv">${u.username?'@'+u.username:'—'}</div></div>
    <div class="detail-item"><div class="dl">Ro'yxat sanasi</div><div class="dv">${u.registered_at}</div></div>
    <div class="detail-item"><div class="dl">Holat</div><div class="dv">${u.is_blocked?'🚫 Bloklangan':'✅ Faol'}</div></div>
    <div class="detail-item"><div class="dl">Jami buyurtmalar</div><div class="dv">${d.order_count}</div></div>
    <div class="detail-item"><div class="dl">Jami xarid</div><div class="dv">${fmtNum(d.total_spent)} so'm</div></div>
  </div></div>`;
  if(d.orders && d.orders.length){
    html += `<div class="info-section"><h4>📦 Buyurtmalar tarixi</h4><div class="scrollable-table"><table style="font-size:12px;">
      <thead><tr><th>ID</th><th>Do'kon</th><th>Summa</th><th>Holat</th><th>Vaqt</th><th></th></tr></thead><tbody>
      ${d.orders.map(o=>`<tr>
        <td><code>#${o.order_uid}</code></td><td>${o.shop_name||'—'}</td>
        <td>${fmtNum(o.total_sum)} so'm</td><td>${statusBadge(o.status)}</td>
        <td style="font-size:10px;">${o.created_at}</td>
        <td><button class="btn btn-info btn-sm" onclick="closeModal('detail-modal');showOrderDetail('${o.order_uid}')">👁️</button></td>
      </tr>`).join('')}</tbody></table></div></div>`;
  }
  showDetail(`Mijoz — ${u.full_name}`, html);
}

async function toggleUser(tg_id, block){
  if(!confirm(block?'Bloklashni tasdiqlaysizmi?':'Blokdan chiqarishni tasdiqlaysizmi?')) return;
  await api('/admin/api/user/block',{method:'POST',body:JSON.stringify({tg_id,block})});
  loadUsers();
}

// ===== COURIERS =====
async function loadCouriers(){
  const search = document.getElementById('courier-search').value;
  const d = await api(`/admin/api/couriers?search=${encodeURIComponent(search)}`);
  document.getElementById('couriers-count').textContent = (d.total||0)+' ta';
  document.getElementById('couriers-table').innerHTML = (d.couriers||[]).map(c=>`<tr>
    <td>${c.id}</td><td>${c.full_name}</td><td>${c.phone}</td>
    <td>${c.shop_name||'—'}</td><td>${c.delivered_count}</td>
    <td>${c.is_busy?'<span class="badge badge-yellow">🔴 Band</span>':"<span class='badge badge-green'>🟢 Bo'sh</span>"}</td>
    <td>${c.is_blocked?'<span class="badge badge-red">🚫</span>':'<span class="badge badge-green">✅</span>'}</td>
    <td style="display:flex;gap:4px;">
      <button class="btn btn-info btn-sm" onclick="showCourierDetail(${c.tg_id})">👁️</button>
      ${c.is_blocked
        ?`<button class="btn btn-success btn-sm" onclick="toggleCourier(${c.tg_id},0)">✅</button>`
        :`<button class="btn btn-danger btn-sm" onclick="toggleCourier(${c.tg_id},1)">🚫</button>`}
      <button class="btn btn-danger btn-sm" onclick="deleteCourier(${c.tg_id})">🗑️</button>
    </td>
  </tr>`).join('');
}

async function showCourierDetail(tg_id){
  const d = await api(`/admin/api/courier-detail?tg_id=${tg_id}`);
  if(!d.courier){ showDetail('Kuryer', '<p>Topilmadi</p>'); return; }
  const c = d.courier;
  let html = `<div class="info-section"><h4>🚚 Kuryer ma'lumotlari</h4><div class="detail-grid">
    <div class="detail-item"><div class="dl">ID</div><div class="dv">${c.id}</div></div>
    <div class="detail-item"><div class="dl">TG ID</div><div class="dv">${c.tg_id}</div></div>
    <div class="detail-item"><div class="dl">Ism</div><div class="dv">${c.full_name}</div></div>
    <div class="detail-item"><div class="dl">Telefon</div><div class="dv">${c.phone}</div></div>
    <div class="detail-item"><div class="dl">Do'kon</div><div class="dv">${c.shop_name||'—'} (ID: ${c.shop_id||'—'})</div></div>
    <div class="detail-item"><div class="dl">Ishga kirgan</div><div class="dv">${c.registered_at||'—'}</div></div>
    <div class="detail-item"><div class="dl">Holat</div><div class="dv">${c.is_busy?'🔴 Band':'🟢 Bo\'sh'}</div></div>
    <div class="detail-item"><div class="dl">Yetkazgan</div><div class="dv">${d.delivered_count} ta buyurtma</div></div>
  </div></div>`;
  showDetail(`Kuryer — ${c.full_name}`, html);
}

async function toggleCourier(tg_id, block){
  if(!confirm(block?'Bloklashni tasdiqlaysizmi?':'Blokdan chiqarishni tasdiqlaysizmi?')) return;
  await api('/admin/api/courier/block',{method:'POST',body:JSON.stringify({tg_id,block})});
  loadCouriers();
}
async function deleteCourier(tg_id){
  if(!confirm("O'chirishni tasdiqlaysizmi?")) return;
  await api('/admin/api/courier/delete',{method:'POST',body:JSON.stringify({tg_id})});
  loadCouriers();
}

// ===== SHOPS =====
async function loadShops(){
  const search = document.getElementById('shop-search').value;
  const d = await api(`/admin/api/shops?search=${encodeURIComponent(search)}`);
  document.getElementById('shops-table').innerHTML = (d.shops||[]).map(s=>`<tr>
    <td>${s.id}</td><td>${s.name}</td><td>${s.phone||'—'}</td>
    <td>⭐${Number(s.rating||0).toFixed(1)}</td>
    <td>${s.order_count}</td><td>${fmtNum(s.total_income)} so'm</td>
    <td>${s.admin_percent}%</td>
    <td>${s.is_open?'<span class="badge badge-green">🟢 Ochiq</span>':'<span class="badge badge-red">🔴 Yopiq</span>'}</td>
    <td><button class="btn btn-info btn-sm" onclick="showShopDetail(${s.id})">👁️ Ko'rish</button></td>
  </tr>`).join('');
}

async function showShopDetail(shop_id){
  const d = await api(`/admin/api/shop-detail?id=${shop_id}`);
  if(!d.shop){ showDetail("Do'kon", '<p>Topilmadi</p>'); return; }
  const s = d.shop;
  let html = `<div class="info-section"><h4>🏪 Do'kon ma'lumotlari</h4><div class="detail-grid">
    <div class="detail-item"><div class="dl">ID</div><div class="dv">${s.id}</div></div>
    <div class="detail-item"><div class="dl">Nom</div><div class="dv">${s.name}</div></div>
    <div class="detail-item"><div class="dl">Do'kon egasi TG ID</div><div class="dv">${s.owner_tg_id}</div></div>
    <div class="detail-item"><div class="dl">Egasi ismi</div><div class="dv">${d.owner_name||'—'}</div></div>
    <div class="detail-item"><div class="dl">Telefon</div><div class="dv">${s.phone||'—'}</div></div>
    <div class="detail-item"><div class="dl">Ish vaqti</div><div class="dv">${s.work_time||'—'}</div></div>
    <div class="detail-item"><div class="dl">Karta raqami</div><div class="dv">${s.card_number||'—'}</div></div>
    <div class="detail-item"><div class="dl">Ochilgan sana</div><div class="dv">${s.created_at||'—'}</div></div>
    <div class="detail-item"><div class="dl">Admin foizi</div><div class="dv">${s.admin_percent}%</div></div>
    <div class="detail-item"><div class="dl">Reyting</div><div class="dv">⭐${Number(s.rating||0).toFixed(1)} (${s.rating_count} ovoz)</div></div>
    <div class="detail-item"><div class="dl">Holat</div><div class="dv">${s.is_open?'🟢 Ochiq':'🔴 Yopiq'}</div></div>
    <div class="detail-item"><div class="dl">Mahsulotlar soni</div><div class="dv">${d.product_count} ta</div></div>
  </div></div>
  <div class="info-section"><h4>📊 Statistika</h4><div class="detail-grid">
    <div class="detail-item"><div class="dl">Jami buyurtmalar</div><div class="dv">${d.total_orders}</div></div>
    <div class="detail-item"><div class="dl">Jami daromad</div><div class="dv">${fmtNum(d.total_income)} so'm</div></div>
    <div class="detail-item"><div class="dl">Bugungi buyurtmalar</div><div class="dv">${d.today_orders}</div></div>
    <div class="detail-item"><div class="dl">Bugungi daromad</div><div class="dv">${fmtNum(d.today_income)} so'm</div></div>
    <div class="detail-item"><div class="dl">Naqd to'lovlar</div><div class="dv">${d.cash_count} ta</div></div>
    <div class="detail-item"><div class="dl">Karta to'lovlar</div><div class="dv">${d.card_count} ta</div></div>
  </div></div>`;

  if(d.couriers && d.couriers.length){
    html += `<div class="info-section"><h4>🚚 Kuryerlar</h4><table style="font-size:12px;"><thead><tr><th>Ism</th><th>Tel</th><th>Holat</th><th>Yetkazgan</th></tr></thead><tbody>
    ${d.couriers.map(c=>`<tr><td>${c.full_name}</td><td>${c.phone}</td><td>${c.is_busy?'🔴 Band':'🟢 Bo\'sh'}</td><td>${c.delivered||0}</td></tr>`).join('')}</tbody></table></div>`;
  }
  if(d.orders && d.orders.length){
    html += `<div class="info-section"><h4>📦 Buyurtmalar</h4><div class="scrollable-table"><table style="font-size:12px;"><thead><tr><th>ID</th><th>Summa</th><th>Holat</th><th>Vaqt</th><th></th></tr></thead><tbody>
    ${d.orders.map(o=>`<tr><td><code>#${o.order_uid}</code></td><td>${fmtNum(o.total_sum)} so'm</td><td>${statusBadge(o.status)}</td><td style="font-size:10px;">${o.created_at}</td>
    <td><button class="btn btn-info btn-sm" onclick="closeModal('detail-modal');showOrderDetail('${o.order_uid}')">👁️</button></td></tr>`).join('')}
    </tbody></table></div></div>`;
  }
  showDetail(`Do'kon — ${s.name}`, html);
}

// ===== FINANCE =====
async function loadFinance(){
  const d = await api('/admin/api/finance');
  document.getElementById('f-cash').textContent = fmtNum(d.cash_total)+' so\'m';
  document.getElementById('f-card').textContent = fmtNum(d.card_total)+' so\'m';
  document.getElementById('f-admin').textContent = fmtNum(d.admin_share)+' so\'m';
  document.getElementById('f-total').textContent = fmtNum(d.total)+' so\'m';
  document.getElementById('finance-table').innerHTML = (d.shops||[]).map(s=>`<tr>
    <td>${s.name}</td><td>${s.order_count}</td>
    <td>${fmtNum(s.total_income)} so'm</td><td>${s.admin_percent}%</td>
    <td>${fmtNum(s.total_income*s.admin_percent/100)} so'm</td>
  </tr>`).join('');
}

// ===== MONTHLY REPORT =====
async function loadMonthly(){
  const search = document.getElementById('monthly-search').value;
  const pct = document.getElementById('monthly-percent').value;
  const d = await api(`/admin/api/monthly?search=${encodeURIComponent(search)}&percent=${pct||''}`);
  document.getElementById('monthly-table').innerHTML = (d.shops||[]).map(s=>{
    const myShare = pct ? s.income_30 * parseFloat(pct) / 100 : s.admin_share;
    return `<tr>
      <td>${s.id}</td><td><strong>${s.name}</strong></td>
      <td>${s.orders_30} ta</td>
      <td>${fmtNum(s.income_30)} so'm</td>
      <td>${fmtNum(s.today_income)} so'm</td>
      <td>${pct||s.admin_percent}%</td>
      <td style="color:var(--accent);font-weight:700;">${fmtNum(myShare)} so'm</td>
      <td><button class="btn btn-info btn-sm" onclick="showShopDetail(${s.id})">👁️</button></td>
    </tr>`;
  }).join('') || "<tr><td colspan='8' class='empty-state'>Ma'lumot yo'q</td></tr>";
}

// ===== PROMO =====
async function loadPromo(){
  const d = await api('/admin/api/promo');
  document.getElementById('promo-table').innerHTML = (d.promos||[]).map(p=>{
    const active = (p.max_uses===0||p.used_count<p.max_uses)&&(!p.expires_at||new Date(p.expires_at)>=new Date());
    return `<tr>
      <td><code>${p.code}</code></td>
      <td>${p.discount_type==='percent'?p.discount_value+'%':fmtNum(p.discount_value)+' so\'m'}</td>
      <td>${fmtNum(p.min_sum)} so'm</td>
      <td>${p.expires_at||'Cheksiz'}</td>
      <td>${p.max_uses||'Cheksiz'}</td><td>${p.used_count}</td>
      <td>${active?'<span class="badge badge-green">✅ Faol</span>':'<span class="badge badge-red">❌ Tugagan</span>'}</td>
      <td><button class="btn btn-danger btn-sm" onclick="deletePromo(${p.id})">🗑️</button></td>
    </tr>`;
  }).join('');
}
async function createPromo(){
  const data={code:document.getElementById('pm-code').value.toUpperCase(),discount_type:document.getElementById('pm-type').value,discount_value:parseFloat(document.getElementById('pm-value').value)||0,min_sum:parseFloat(document.getElementById('pm-min').value)||0,days:parseInt(document.getElementById('pm-days').value)||0,max_uses:parseInt(document.getElementById('pm-limit').value)||0};
  const r = await api('/admin/api/promo/create',{method:'POST',body:JSON.stringify(data)});
  if(r.ok){closeModal('promo-modal');loadPromo();alert('✅ Promo kod yaratildi!');}
  else alert('❌ Xatolik: '+r.error);
}
async function deletePromo(id){
  if(!confirm("O'chirishni tasdiqlaysizmi?")) return;
  await api('/admin/api/promo/delete',{method:'POST',body:JSON.stringify({id})});
  loadPromo();
}

// ===== SEARCH =====
async function doSearch(){
  const q = document.getElementById('global-search').value.trim();
  const type = document.getElementById('search-type').value;
  if(!q) return;
  const d = await api(`/admin/api/search?q=${encodeURIComponent(q)}&type=${type}`);
  let html = '';
  if(d.users&&d.users.length){
    html += `<div class="card"><div class="card-header"><h3>👥 Mijozlar (${d.users.length})</h3></div><div class="scrollable-table"><table><thead><tr><th>ID</th><th>Ism Familya</th><th>Telefon</th><th>Username</th><th>TG ID</th><th>Kuryer</th><th>Buyurtmalar</th><th></th></tr></thead><tbody>
    ${d.users.map(u=>`<tr><td>${u.id}</td><td>${u.full_name}</td><td>${u.phone}</td><td>${u.username?'@'+u.username:'—'}</td><td>${u.tg_id}</td><td>${u.courier_info||'—'}</td><td>${u.order_count}</td>
    <td><button class="btn btn-info btn-sm" onclick="showUserDetail(${u.tg_id})">👁️</button></td></tr>`).join('')}
    </tbody></table></div></div>`;
  }
  if(d.couriers&&d.couriers.length){
    html += `<div class="card"><div class="card-header"><h3>🚚 Kuryerlar (${d.couriers.length})</h3></div><div class="scrollable-table"><table><thead><tr><th>ID</th><th>Ism</th><th>Telefon</th><th>TG ID</th><th>Do'kon</th><th></th></tr></thead><tbody>
    ${d.couriers.map(c=>`<tr><td>${c.id}</td><td>${c.full_name}</td><td>${c.phone}</td><td>${c.tg_id}</td><td>${c.shop_name||'—'}</td>
    <td><button class="btn btn-info btn-sm" onclick="showCourierDetail(${c.tg_id})">👁️</button></td></tr>`).join('')}
    </tbody></table></div></div>`;
  }
  if(d.shops&&d.shops.length){
    html += `<div class="card"><div class="card-header"><h3>🏪 Do'konlar (${d.shops.length})</h3></div><div class="scrollable-table"><table><thead><tr><th>ID</th><th>Nom</th><th>Egasi ismi</th><th>Telefon</th><th>Karta</th><th>Mahsulotlar</th><th>Ish vaqti</th><th>Naqd</th><th>Karta to'lov</th><th>Jami</th><th></th></tr></thead><tbody>
    ${d.shops.map(s=>`<tr><td>${s.id}</td><td>${s.name}</td><td>${s.owner_name||'—'}</td><td>${s.phone||'—'}</td><td>${s.card_number||'—'}</td><td>${s.product_count}</td><td>${s.work_time||'—'}</td><td>${s.cash_count}</td><td>${s.card_count}</td><td>${s.order_count}</td>
    <td><button class="btn btn-info btn-sm" onclick="showShopDetail(${s.id})">👁️</button></td></tr>`).join('')}
    </tbody></table></div></div>`;
  }
  if(d.orders&&d.orders.length){
    html += `<div class="card"><div class="card-header"><h3>📦 Buyurtmalar (${d.orders.length})</h3></div><div class="scrollable-table"><table><thead><tr><th>ID</th><th>Do'kon</th><th>Summa</th><th>To'lov</th><th>Holat</th><th>Vaqt</th><th></th></tr></thead><tbody>
    ${d.orders.map(o=>`<tr><td>#${o.order_uid}</td><td>${o.shop_name||'—'}</td><td>${fmtNum(o.total_sum)} so'm</td><td>${o.payment_type}</td><td>${statusBadge(o.status)}</td><td>${o.created_at}</td>
    <td><button class="btn btn-info btn-sm" onclick="showOrderDetail('${o.order_uid}')">👁️</button></td></tr>`).join('')}
    </tbody></table></div></div>`;
  }
  if(!html) html = '<div class="card"><div class="empty-state"><p>Hech narsa topilmadi</p></div></div>';
  document.getElementById('search-results').innerHTML = html;
}

// ===== PROBLEMS =====
async function loadProblems(){
  const d = await api('/admin/api/problems');
  document.getElementById('problems-table').innerHTML = (d.orders||[]).map(o=>`<tr style="${o.wait_min>=10?'background:rgba(239,68,68,0.05);':''}">
    <td><code>${o.order_uid}</code></td>
    <td>${o.shop_name||'—'}</td>
    <td>${o.user_name||'Tel buyurtma'} ${o.user_phone?'<br><small>'+o.user_phone+'</small>':''}</td>
    <td>${o.products}</td>
    <td style="${o.wait_min>=10?'color:var(--danger);font-weight:700;':''}">${o.wait_min} daqiqa${o.wait_min>=10?' 🔴':''}</td>
    <td style="font-size:11px;">${o.created_at}</td>
    <td><button class="btn btn-info btn-sm" onclick="showOrderDetail('${o.order_uid}')">👁️</button></td>
  </tr>`).join('') || '<tr><td colspan="7" class="empty-state">✅ Muammo yo\'q</td></tr>';
}

// ===== CHATS =====
async function loadChats(){
  const d = await api('/admin/api/chats');
  document.getElementById('chat-list').innerHTML = (d.chats||[]).map(c=>`
    <div onclick="loadChatDetail(${c.from_tg_id},${c.to_tg_id})" style="padding:12px 16px;border-bottom:1px solid rgba(255,255,255,0.05);cursor:pointer;" onmouseover="this.style.background='rgba(0,212,170,0.05)'" onmouseout="this.style.background=''">
      <div style="display:flex;justify-content:space-between;"><span style="font-size:13px;font-weight:500;">${c.from_tg_id}</span><span style="font-size:10px;color:var(--text2);">${c.chat_type}</span></div>
      <div style="font-size:11px;color:var(--text2);margin-top:2px;">${c.last_msg||''}</div>
      <div style="font-size:10px;color:var(--text2);">${c.last_time||''}</div>
    </div>`).join('') || '<div class="empty-state"><p>Chat yo\'q</p></div>';
}
async function loadChatDetail(from_id, to_id){
  const d = await api(`/admin/api/chat-detail?from=${from_id}&to=${to_id}`);
  const detail = document.getElementById('chat-detail');
  detail.innerHTML = (d.messages||[]).map(m=>`
    <div class="chat-bubble ${m.from_tg_id==from_id?'out':'in'}">
      <div class="chat-meta">${m.from_tg_id} • ${m.created_at}</div>
      <div>${m.message}</div>
    </div>`).join('') || '<div class="empty-state"><p>Xabar yo\'q</p></div>';
  detail.scrollTop = detail.scrollHeight;
}

// ===== TOP =====
async function loadTop(){
  const d = await api('/admin/api/top');
  const medals = ['🥇','🥈','🥉'];
  document.getElementById('top-table').innerHTML = (d.users||[]).map((u,i)=>`<tr>
    <td>${medals[i]||i+1}</td><td>${u.full_name||'Noma\'lum'}</td>
    <td>${u.phone||'—'}</td><td>${u.order_count}</td>
    <td>${fmtNum(u.total_spent)} so'm</td>
  </tr>`).join('');
}

// ===== BLOCKED =====
async function loadBlocked(){
  const d = await api('/admin/api/blocked');
  document.getElementById('blocked-users-table').innerHTML = (d.users||[]).map(u=>`<tr>
    <td>${u.full_name}</td><td>${u.phone}</td><td>${u.id}</td>
    <td><button class="btn btn-success btn-sm" onclick="toggleUser(${u.tg_id},0)">✅ Ochish</button></td>
  </tr>`).join('') || "<tr><td colspan='4' class='empty-state'>Yo'q</td></tr>";
  document.getElementById('blocked-couriers-table').innerHTML = (d.couriers||[]).map(c=>`<tr>
    <td>${c.full_name}</td><td>${c.phone}</td><td>${c.id}</td>
    <td><button class="btn btn-success btn-sm" onclick="toggleCourier(${c.tg_id},0)">✅ Ochish</button></td>
  </tr>`).join('') || "<tr><td colspan='4' class='empty-state'>Yo'q</td></tr>";
}

// ===== WEEKLY =====
async function loadWeekly(){
  const d = await api('/admin/api/weekly');
  document.getElementById('weekly-stats').innerHTML = `
    <div class="stat-card" style="--c1:#00d4aa;--c2:#0ea5e9;"><div class="stat-icon">📦</div><div class="stat-value">${d.total_orders}</div><div class="stat-label">Haftalik buyurtmalar</div></div>
    <div class="stat-card" style="--c1:#22c55e;--c2:#00d4aa;"><div class="stat-icon">💰</div><div class="stat-value">${fmtNum(d.total_income)} so'm</div><div class="stat-label">Haftalik daromad</div></div>
    <div class="stat-card" style="--c1:#8b5cf6;--c2:#ec4899;"><div class="stat-icon">👥</div><div class="stat-value">${d.new_users}</div><div class="stat-label">Yangi mijozlar</div></div>`;
  document.getElementById('weekly-table').innerHTML = (d.days||[]).map(day=>`<tr>
    <td>${day.date}</td><td>${day.orders}</td>
    <td>${fmtNum(day.income)} so'm</td><td>${day.new_users}</td>
  </tr>`).join('');
}

// ===== ADMIN ORDERS =====
async function loadAdminOrders(){
  const d = await api('/admin/api/admin-orders');
  document.getElementById('admin-orders-table').innerHTML = (d.orders||[]).map(o=>`<tr>
    <td><code>#${o.order_uid}</code></td><td>${o.shop_name||'—'}</td>
    <td style="max-width:140px;overflow:hidden;text-overflow:ellipsis;">${o.address}</td>
    <td>${fmtNum(o.total_sum)} so'm</td><td>${statusBadge(o.status)}</td>
    <td style="font-size:11px;">${o.created_at}</td>
  </tr>`).join('');
}

// ===== AI CHAT =====
let aiHistory = [];
function toggleAiChat(){
  document.getElementById('ai-chat-panel').classList.toggle('open');
}
async function sendAiMsg(){
  const input = document.getElementById('ai-input');
  const msg = input.value.trim();
  if(!msg) return;
  input.value = '';
  appendAiMsg('user', msg);
  showTyping();
  try {
    const r = await fetch('/admin/api/ai-chat', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({message: msg, history: aiHistory})
    });
    const d = await r.json();
    hideTyping();
    const reply = d.reply || 'Xatolik yuz berdi';
    appendAiMsg('ai', reply);
    aiHistory.push({role:'user',content:msg});
    aiHistory.push({role:'assistant',content:reply});
    if(aiHistory.length > 20) aiHistory = aiHistory.slice(-20);
  } catch(e) {
    hideTyping();
    appendAiMsg('ai', '❌ Tarmoq xatosi');
  }
}
function appendAiMsg(role, text){
  const div = document.createElement('div');
  div.className = 'ai-msg '+role;
  if(role==='ai') div.innerHTML = '<div class="ai-label">🤖 AI</div>'+text.replace(/\n/g,'<br>');
  else div.textContent = text;
  const msgs = document.getElementById('ai-messages');
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
}
let typingEl = null;
function showTyping(){
  typingEl = document.createElement('div');
  typingEl.className = 'ai-msg ai';
  typingEl.innerHTML = '<div class="ai-typing"><span></span><span></span><span></span></div>';
  document.getElementById('ai-messages').appendChild(typingEl);
  document.getElementById('ai-messages').scrollTop = 99999;
}
function hideTyping(){if(typingEl){typingEl.remove();typingEl=null;}}

// AUTO REFRESH
setInterval(()=>{
  api('/admin/api/dashboard').then(d=>{if(d&&!d.error){document.getElementById('pending-badge').textContent=d.pending||0;}});
  if(document.getElementById('sec-monitoring').classList.contains('active')) loadMonitoring();
},30000);

loadDashboard();
</script>
</body>
</html>'''


# ===================== SHOP DASHBOARD HTML =====================
SHOP_DASHBOARD_HTML = '''<!DOCTYPE html>
<html lang="uz">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Do'kon Paneli — {{ shop_name }}</title>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<style>
:root{--bg:#0a0e1a;--surface:#111827;--surface2:#1a2235;--border:#1e2d45;
  --accent:#00d4aa;--accent2:#0ea5e9;--danger:#ef4444;--text:#e2e8f0;--text2:#94a3b8;--green:#22c55e;}
*{margin:0;padding:0;box-sizing:border-box;}
body{background:#080c18;color:var(--text);font-family:'DM Sans',sans-serif;min-height:100vh;}
body::before{content:'';position:fixed;inset:0;z-index:0;background:radial-gradient(ellipse 70% 50% at 10% 30%, rgba(0,212,170,0.06) 0%, transparent 60%);pointer-events:none;}
.topbar{background:rgba(17,24,39,0.9);backdrop-filter:blur(20px);border-bottom:1px solid rgba(255,255,255,0.07);padding:14px 24px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:50;}
.topbar-logo{font-family:'Syne',sans-serif;font-size:18px;font-weight:800;background:linear-gradient(135deg,#00d4aa,#0ea5e9);-webkit-background-clip:text;-webkit-text-fill-color:transparent;}
.topbar-right{display:flex;align-items:center;gap:12px;}
.shop-badge{background:rgba(0,212,170,0.1);border:1px solid rgba(0,212,170,0.25);padding:5px 12px;border-radius:20px;font-size:12px;color:var(--accent);}
.logout-btn{background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.25);color:var(--danger);padding:6px 14px;border-radius:8px;font-size:12px;text-decoration:none;}
.content{padding:24px;position:relative;z-index:1;}
.tabs{display:flex;gap:8px;margin-bottom:24px;flex-wrap:wrap;}
.tab{padding:8px 18px;border-radius:10px;border:1px solid rgba(255,255,255,0.1);background:rgba(255,255,255,0.04);color:var(--text2);font-size:13px;cursor:pointer;transition:all 0.15s;}
.tab.active{background:rgba(0,212,170,0.15);border-color:rgba(0,212,170,0.4);color:var(--accent);}
.tab-content{display:none;}
.tab-content.active{display:block;}
.stats-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:14px;margin-bottom:24px;}
.stat-card{background:rgba(17,24,39,0.8);border:1px solid rgba(255,255,255,0.07);border-radius:14px;padding:18px;position:relative;overflow:hidden;}
.stat-card::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,var(--c1,#00d4aa),var(--c2,#0ea5e9));}
.stat-icon{font-size:24px;margin-bottom:8px;}
.stat-value{font-family:'Syne',sans-serif;font-size:24px;font-weight:800;}
.stat-label{font-size:12px;color:var(--text2);margin-top:3px;}
.card{background:rgba(17,24,39,0.8);border:1px solid rgba(255,255,255,0.07);border-radius:14px;overflow:hidden;margin-bottom:16px;}
.card-header{padding:14px 18px;border-bottom:1px solid rgba(255,255,255,0.07);font-family:'Syne',sans-serif;font-size:14px;font-weight:700;}
table{width:100%;border-collapse:collapse;font-size:13px;}
thead tr{background:rgba(26,34,53,0.8);}
th{padding:10px 14px;text-align:left;font-size:10px;font-weight:600;color:var(--text2);text-transform:uppercase;}
td{padding:10px 14px;border-top:1px solid rgba(255,255,255,0.05);}
.badge{display:inline-block;padding:3px 9px;border-radius:20px;font-size:11px;font-weight:600;}
.badge-green{background:rgba(34,197,94,0.15);color:#22c55e;}
.badge-yellow{background:rgba(245,158,11,0.15);color:#f59e0b;}
.badge-red{background:rgba(239,68,68,0.15);color:#ef4444;}
.badge-blue{background:rgba(14,165,233,0.15);color:#0ea5e9;}
.scrollable-table{overflow-x:auto;}
.empty-state{text-align:center;padding:32px;color:var(--text2);}

/* AI CHAT (same as admin) */
.ai-chat-btn{position:fixed;bottom:24px;right:24px;width:56px;height:56px;background:linear-gradient(135deg,#00d4aa,#0ea5e9);border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:24px;cursor:pointer;box-shadow:0 8px 32px rgba(0,212,170,0.4);z-index:150;border:none;}
.ai-chat-panel{display:none;position:fixed;bottom:92px;right:24px;width:370px;height:500px;background:rgba(17,24,39,0.98);border:1px solid rgba(255,255,255,0.1);border-radius:18px;box-shadow:0 24px 80px rgba(0,0,0,0.6);z-index:149;flex-direction:column;overflow:hidden;}
.ai-chat-panel.open{display:flex;}
.ai-chat-header{padding:14px 16px;border-bottom:1px solid rgba(255,255,255,0.07);display:flex;align-items:center;gap:10px;flex-shrink:0;}
.ai-icon{width:30px;height:30px;background:linear-gradient(135deg,#00d4aa,#0ea5e9);border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:15px;}
.ai-chat-close{margin-left:auto;background:none;border:none;color:var(--text2);cursor:pointer;font-size:18px;}
.ai-messages{flex:1;overflow-y:auto;padding:12px;display:flex;flex-direction:column;gap:8px;}
.ai-msg{padding:10px 13px;border-radius:10px;max-width:88%;font-size:13px;line-height:1.5;}
.ai-msg.user{background:rgba(0,212,170,0.15);align-self:flex-end;}
.ai-msg.ai{background:rgba(255,255,255,0.06);align-self:flex-start;}
.ai-label{font-size:10px;color:var(--accent);margin-bottom:3px;font-weight:600;}
.ai-input-row{padding:12px;border-top:1px solid rgba(255,255,255,0.07);display:flex;gap:8px;flex-shrink:0;}
.ai-input{flex:1;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);border-radius:10px;padding:9px 12px;color:var(--text);font-size:13px;outline:none;resize:none;}
.ai-input:focus{border-color:#00d4aa;}
.ai-send{background:linear-gradient(135deg,#00d4aa,#0ea5e9);color:#000;border:none;border-radius:8px;padding:9px 14px;cursor:pointer;font-weight:600;}
.ai-typing{display:flex;gap:4px;align-items:center;}
.ai-typing span{width:6px;height:6px;background:var(--text2);border-radius:50%;animation:typing 1.2s infinite;}
.ai-typing span:nth-child(2){animation-delay:0.2s;}
.ai-typing span:nth-child(3){animation-delay:0.4s;}
@keyframes typing{0%,100%{opacity:0.3;}50%{opacity:1;}}
@media(max-width:768px){.content{padding:12px;}.stats-grid{grid-template-columns:repeat(2,1fr);}.ai-chat-panel{width:calc(100vw - 32px);right:16px;}}
</style>
</head>
<body>
<div class="topbar">
  <div class="topbar-logo">🏪 {{ shop_name }}</div>
  <div class="topbar-right">
    <div class="shop-badge">Do'kon ID: {{ shop_id }}</div>
    <a href="/shop/logout" class="logout-btn">🚪 Chiqish</a>
  </div>
</div>
<div class="content">
  <div class="tabs">
    <div class="tab active" onclick="switchTab('overview','this')">📊 Umumiy</div>
    <div class="tab" onclick="switchTab('orders','this')">📦 Buyurtmalar</div>
    <div class="tab" onclick="switchTab('couriers','this')">🚚 Kuryerlar</div>
    <div class="tab" onclick="switchTab('report30','this')">📅 30 kunlik</div>
    <div class="tab" onclick="switchTab('today','this')">📅 Bugungi</div>
  </div>

  <!-- OVERVIEW -->
  <div class="tab-content active" id="tab-overview">
    <div class="stats-grid" id="shop-stats"></div>
    <div class="card">
      <div class="card-header">📦 Oxirgi buyurtmalar</div>
      <div class="scrollable-table"><table><thead><tr><th>ID</th><th>Summa</th><th>To'lov</th><th>Holat</th><th>Vaqt</th></tr></thead><tbody id="shop-recent-orders"></tbody></table></div>
    </div>
  </div>

  <!-- ORDERS -->
  <div class="tab-content" id="tab-orders">
    <div class="card">
      <div class="card-header" style="display:flex;justify-content:space-between;align-items:center;">📦 Barcha buyurtmalar <button onclick="loadShopOrders()" style="background:none;border:1px solid rgba(255,255,255,0.1);color:var(--text2);padding:5px 10px;border-radius:6px;cursor:pointer;font-size:12px;">🔄</button></div>
      <div class="scrollable-table"><table><thead><tr><th>ID</th><th>Summa</th><th>To'lov</th><th>Manzil</th><th>Holat</th><th>Kuryer</th><th>Vaqt</th></tr></thead><tbody id="shop-orders-table"></tbody></table></div>
    </div>
  </div>

  <!-- COURIERS -->
  <div class="tab-content" id="tab-couriers">
    <div class="card">
      <div class="card-header">🚚 Kuryerlar</div>
      <div class="scrollable-table"><table><thead><tr><th>Ism</th><th>Telefon</th><th>ID</th><th>Holat</th><th>Yetkazgan</th><th>Ishga kirgan</th></tr></thead><tbody id="shop-couriers-table"></tbody></table></div>
    </div>
  </div>

  <!-- REPORT 30 -->
  <div class="tab-content" id="tab-report30">
    <div class="stats-grid" id="report30-stats"></div>
    <div class="card">
      <div class="card-header">📅 30 kunlik statistika</div>
      <div class="scrollable-table"><table><thead><tr><th>Kun</th><th>Buyurtmalar</th><th>Daromad</th></tr></thead><tbody id="report30-table"></tbody></table></div>
    </div>
  </div>

  <!-- TODAY -->
  <div class="tab-content" id="tab-today">
    <div class="stats-grid" id="today-stats"></div>
    <div class="card">
      <div class="card-header">📅 Bugungi buyurtmalar</div>
      <div class="scrollable-table"><table><thead><tr><th>ID</th><th>Summa</th><th>To'lov</th><th>Holat</th><th>Vaqt</th></tr></thead><tbody id="today-orders-table"></tbody></table></div>
    </div>
  </div>
</div>

<!-- AI CHAT -->
<button class="ai-chat-btn" onclick="toggleAiChat()" title="AI Yordamchi">🤖</button>
<div class="ai-chat-panel" id="ai-chat-panel">
  <div class="ai-chat-header">
    <div class="ai-icon">🤖</div>
    <div style="flex:1;"><div style="font-weight:600;font-size:13px;">AI Yordamchi</div><div style="font-size:11px;color:var(--green);">● Faol</div></div>
    <button class="ai-chat-close" onclick="toggleAiChat()">✕</button>
  </div>
  <div class="ai-messages" id="ai-messages">
    <div class="ai-msg ai"><div class="ai-label">🤖 AI</div>Salom! Do'koningiz haqida savol bering. "7 kunlik hisobot", "bosh kuryer bor yo'q?", "bugun nechta buyurtma?" kabi.</div>
  </div>
  <div class="ai-input-row">
    <textarea class="ai-input" id="ai-input" placeholder="Savol yozing..." rows="1" onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();sendAiMsg();}"></textarea>
    <button class="ai-send" onclick="sendAiMsg()">➤</button>
  </div>
</div>

<script>
const SHOP_ID = {{ shop_id }};
const fmtNum = n => Number(n||0).toLocaleString('uz-UZ');
const api = async (url, opts={}) => {
  const r = await fetch(url, {headers:{'Content-Type':'application/json'},...opts});
  return r.json();
};
function statusBadge(s){const m={pending:'<span class="badge badge-yellow">⏳</span>',confirmed:'<span class="badge badge-blue">✅</span>',on_way:'<span class="badge badge-blue">🚗</span>',delivered:'<span class="badge badge-green">✅</span>',rejected:'<span class="badge badge-red">❌</span>'};return m[s]||s;}

function switchTab(id, el){
  document.querySelectorAll('.tab-content').forEach(t=>t.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  document.getElementById('tab-'+id).classList.add('active');
  if(el && el!='this'){
    if(typeof el === 'object') el.classList.add('active');
  } else {
    document.querySelector(`[onclick*="${id}"]`) && document.querySelector(`[onclick*="${id}"]`).classList.add('active');
  }
  const loaders = {orders:loadShopOrders, couriers:loadShopCouriers, report30:loadReport30, today:loadToday};
  if(loaders[id]) loaders[id]();
}
document.querySelectorAll('.tab').forEach(t => t.addEventListener('click', function(){
  document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));
  this.classList.add('active');
}));

async function loadOverview(){
  const d = await api(`/shop/api/overview?shop_id=${SHOP_ID}`);
  document.getElementById('shop-stats').innerHTML = `
    <div class="stat-card" style="--c1:#00d4aa;--c2:#0ea5e9;"><div class="stat-icon">📦</div><div class="stat-value">${d.total_orders}</div><div class="stat-label">Jami buyurtmalar</div></div>
    <div class="stat-card" style="--c1:#22c55e;--c2:#00d4aa;"><div class="stat-icon">💰</div><div class="stat-value">${fmtNum(d.total_income)} so'm</div><div class="stat-label">Jami daromad</div></div>
    <div class="stat-card" style="--c1:#f59e0b;--c2:#ef4444;"><div class="stat-icon">📅</div><div class="stat-value">${d.today_orders}</div><div class="stat-label">Bugun buyurtmalar</div></div>
    <div class="stat-card" style="--c1:#0ea5e9;--c2:#8b5cf6;"><div class="stat-icon">💵</div><div class="stat-value">${fmtNum(d.today_income)} so'm</div><div class="stat-label">Bugungi daromad</div></div>
    <div class="stat-card" style="--c1:#8b5cf6;--c2:#ec4899;"><div class="stat-icon">⏳</div><div class="stat-value">${d.pending}</div><div class="stat-label">Kutilayotgan</div></div>
    <div class="stat-card" style="--c1:#ef4444;--c2:#f59e0b;"><div class="stat-icon">🚚</div><div class="stat-value">${d.free_couriers} / ${d.total_couriers}</div><div class="stat-label">Bo'sh / Jami kuryer</div></div>`;
  document.getElementById('shop-recent-orders').innerHTML = (d.recent_orders||[]).map(o=>`<tr>
    <td><code>#${o.order_uid}</code></td><td>${fmtNum(o.total_sum)} so'm</td>
    <td>${o.payment_type}</td><td>${statusBadge(o.status)}</td>
    <td style="font-size:11px;">${o.created_at}</td>
  </tr>`).join('') || "<tr><td colspan='5' class='empty-state'>Yo'q</td></tr>";
}

async function loadShopOrders(){
  const d = await api(`/shop/api/orders?shop_id=${SHOP_ID}`);
  document.getElementById('shop-orders-table').innerHTML = (d.orders||[]).map(o=>`<tr>
    <td><code>#${o.order_uid}</code></td><td>${fmtNum(o.total_sum)} so'm</td>
    <td>${o.payment_type}</td><td style="max-width:120px;overflow:hidden;text-overflow:ellipsis;">${o.address}</td>
    <td>${statusBadge(o.status)}</td><td>${o.courier_name||'—'}</td>
    <td style="font-size:11px;">${o.created_at}</td>
  </tr>`).join('') || "<tr><td colspan='7' class='empty-state'>Buyurtma yo'q</td></tr>";
}

async function loadShopCouriers(){
  const d = await api(`/shop/api/couriers?shop_id=${SHOP_ID}`);
  document.getElementById('shop-couriers-table').innerHTML = (d.couriers||[]).map(c=>`<tr>
    <td>${c.full_name}</td><td>${c.phone}</td><td>${c.id}</td>
    <td>${c.is_busy?'<span class="badge badge-yellow">🔴 Band</span>':"<span class='badge badge-green'>🟢 Bo'sh</span>"}</td>
    <td>${c.delivered} ta</td><td style="font-size:11px;">${c.registered_at||'—'}</td>
  </tr>`).join('') || "<tr><td colspan='6' class='empty-state'>Kuryer yo'q</td></tr>";
}

async function loadReport30(){
  const d = await api(`/shop/api/report30?shop_id=${SHOP_ID}`);
  document.getElementById('report30-stats').innerHTML = `
    <div class="stat-card" style="--c1:#00d4aa;--c2:#0ea5e9;"><div class="stat-icon">📦</div><div class="stat-value">${d.total_orders}</div><div class="stat-label">30 kunlik buyurtmalar</div></div>
    <div class="stat-card" style="--c1:#22c55e;--c2:#00d4aa;"><div class="stat-icon">💰</div><div class="stat-value">${fmtNum(d.total_income)} so'm</div><div class="stat-label">30 kunlik daromad</div></div>`;
  document.getElementById('report30-table').innerHTML = (d.days||[]).map(day=>`<tr>
    <td>${day.date}</td><td>${day.orders}</td><td>${fmtNum(day.income)} so'm</td>
  </tr>`).join('');
}

async function loadToday(){
  const d = await api(`/shop/api/today?shop_id=${SHOP_ID}`);
  document.getElementById('today-stats').innerHTML = `
    <div class="stat-card" style="--c1:#00d4aa;--c2:#0ea5e9;"><div class="stat-icon">📦</div><div class="stat-value">${d.count}</div><div class="stat-label">Bugungi buyurtmalar</div></div>
    <div class="stat-card" style="--c1:#22c55e;--c2:#00d4aa;"><div class="stat-icon">💰</div><div class="stat-value">${fmtNum(d.income)} so'm</div><div class="stat-label">Bugungi daromad</div></div>`;
  document.getElementById('today-orders-table').innerHTML = (d.orders||[]).map(o=>`<tr>
    <td><code>#${o.order_uid}</code></td><td>${fmtNum(o.total_sum)} so'm</td>
    <td>${o.payment_type}</td><td>${statusBadge(o.status)}</td>
    <td style="font-size:11px;">${o.created_at}</td>
  </tr>`).join('') || "<tr><td colspan='5' class='empty-state'>Bugun buyurtma yo'q</td></tr>";
}

// AI CHAT for shop
let aiHistory = [];
function toggleAiChat(){document.getElementById('ai-chat-panel').classList.toggle('open');}
async function sendAiMsg(){
  const input = document.getElementById('ai-input');
  const msg = input.value.trim();
  if(!msg) return;
  input.value = '';
  appendAiMsg('user', msg);
  showTyping();
  try {
    const r = await fetch('/shop/api/ai-chat', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({message: msg, history: aiHistory, shop_id: SHOP_ID})
    });
    const d = await r.json();
    hideTyping();
    const reply = d.reply || 'Xatolik';
    appendAiMsg('ai', reply);
    aiHistory.push({role:'user',content:msg});
    aiHistory.push({role:'assistant',content:reply});
    if(aiHistory.length > 16) aiHistory = aiHistory.slice(-16);
  } catch(e){hideTyping();appendAiMsg('ai','❌ Xatolik');}
}
function appendAiMsg(role, text){
  const div = document.createElement('div');
  div.className = 'ai-msg '+role;
  if(role==='ai') div.innerHTML = '<div class="ai-label">🤖 AI</div>'+text.replace(/\n/g,'<br>');
  else div.textContent = text;
  const msgs = document.getElementById('ai-messages');
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
}
let typingEl=null;
function showTyping(){typingEl=document.createElement('div');typingEl.className='ai-msg ai';typingEl.innerHTML='<div class="ai-typing"><span></span><span></span><span></span></div>';document.getElementById('ai-messages').appendChild(typingEl);document.getElementById('ai-messages').scrollTop=99999;}
function hideTyping(){if(typingEl){typingEl.remove();typingEl=null;}}

loadOverview();
setInterval(loadOverview, 30000);
</script>
</body>
</html>'''


# ===================== ROUTES — LOGIN =====================
@app.route('/admin/login', methods=['GET','POST'])
def admin_login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username','')
        password = request.form.get('password','')
        if username == ADMIN_WEB_USER and password == ADMIN_WEB_PASS:
            session['admin_logged_in'] = True
            session['admin_username'] = username
            return redirect('/admin')
        error = "Noto'g'ri username yoki parol!"
    return render_template_string(LOGIN_HTML, error=error)

@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect('/admin/login')

@app.route('/admin')
@login_required
def admin_index():
    return render_template_string(DASHBOARD_HTML, username=session.get('admin_username','admin'))

# SHOP LOGIN
@app.route('/shop/login', methods=['GET','POST'])
def shop_login():
    error = None
    if request.method == 'POST':
        shop_id_str = request.form.get('shop_id','')
        password = request.form.get('password','')
        try:
            shop_id = int(shop_id_str)
        except:
            error = "Do'kon ID noto'g'ri"
            return render_template_string(SHOP_LOGIN_HTML, error=error)
        try:
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT * FROM shops WHERE id=%s", (shop_id,))
            shop = c.fetchone()
            conn.close()
            if not shop:
                error = "Do'kon topilmadi"
            else:
                # Check password from shop_passwords table or use shop_id as default
                try:
                    conn2 = get_db()
                    c2 = conn2.cursor()
                    # Try to create table if not exists
                    c2.execute("""CREATE TABLE IF NOT EXISTS shop_passwords (
                        shop_id BIGINT PRIMARY KEY,
                        password TEXT
                    )""")
                    conn2.commit()
                    c2.execute("SELECT password FROM shop_passwords WHERE shop_id=%s", (shop_id,))
                    row = c2.fetchone()
                    conn2.close()
                    stored_pass = row['password'] if row else str(shop_id)
                except:
                    stored_pass = str(shop_id)

                if password == stored_pass:
                    session['shop_logged_in'] = True
                    session['shop_id'] = shop_id
                    session['shop_name'] = shop['name']
                    return redirect('/shop')
                else:
                    error = "Noto'g'ri parol"
        except Exception as e:
            error = f"Xatolik: {str(e)}"
    return render_template_string(SHOP_LOGIN_HTML, error=error)

@app.route('/shop/logout')
def shop_logout():
    session.clear()
    return redirect('/shop/login')

@app.route('/shop')
@shop_login_required
def shop_index():
    return render_template_string(SHOP_DASHBOARD_HTML,
        shop_id=session.get('shop_id'),
        shop_name=session.get('shop_name','Do\'kon'))

# ===================== ADMIN API ENDPOINTS =====================
@app.route('/admin/api/login-stats')
def api_login_stats():
    try:
        conn = get_db()
        c = conn.cursor()
        today = datetime.now().strftime("%d.%m.%Y")
        c.execute("SELECT COUNT(*) as cnt FROM orders WHERE created_at LIKE %s", (f"{today}%",))
        orders = c.fetchone()['cnt']
        c.execute("SELECT COALESCE(SUM(total_sum),0) as t FROM orders WHERE status='delivered' AND created_at LIKE %s", (f"{today}%",))
        income = c.fetchone()['t']
        conn.close()
        return jsonify({'orders': orders, 'income': float(income)})
    except:
        return jsonify({'orders': 0, 'income': 0})

@app.route('/admin/api/dashboard')
@login_required
def api_dashboard():
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) as cnt FROM users")
        users = c.fetchone()['cnt']
        c.execute("SELECT COUNT(*) as cnt FROM shops")
        shops = c.fetchone()['cnt']
        c.execute("SELECT COUNT(*) as cnt FROM shops WHERE is_open=1")
        shops_open = c.fetchone()['cnt']
        c.execute("SELECT COUNT(*) as cnt FROM couriers")
        couriers = c.fetchone()['cnt']
        c.execute("SELECT COUNT(*) as cnt FROM orders")
        total_orders = c.fetchone()['cnt']
        c.execute("SELECT COALESCE(SUM(total_sum),0) as t FROM orders WHERE status='delivered'")
        total_income = c.fetchone()['t']
        today = datetime.now().strftime("%d.%m.%Y")
        c.execute("SELECT COALESCE(SUM(total_sum),0) as t FROM orders WHERE status='delivered' AND created_at LIKE %s", (f"{today}%",))
        today_income = c.fetchone()['t']
        c.execute("SELECT COUNT(*) as cnt FROM orders WHERE status='pending'")
        pending = c.fetchone()['cnt']
        c.execute("SELECT COUNT(*) as cnt FROM orders WHERE status='on_way'")
        on_way = c.fetchone()['cnt']
        c.execute("""SELECT o.id, o.order_uid, o.total_sum, o.status, o.created_at, s.name as shop_name
                     FROM orders o LEFT JOIN shops s ON o.shop_id=s.id ORDER BY o.id DESC LIMIT 10""")
        recent_orders = [dict(r) for r in c.fetchall()]
        c.execute("""SELECT s.id, s.name, s.is_open, COALESCE(s.rating,0) as rating,
                     COUNT(CASE WHEN o.created_at LIKE %s THEN 1 END) as today_count
                     FROM shops s LEFT JOIN orders o ON s.id=o.shop_id GROUP BY s.id,s.name,s.is_open,s.rating ORDER BY s.name""",
                  (f"{today}%",))
        shops_info = [dict(r) for r in c.fetchall()]
        conn.close()
        return jsonify({'users':users,'shops':shops,'shops_open':shops_open,'couriers':couriers,
                        'total_orders':total_orders,'total_income':float(total_income),'today_income':float(today_income),
                        'pending':pending,'on_way':on_way,'recent_orders':recent_orders,'shops_info':shops_info})
    except Exception as e:
        return jsonify({'error':str(e)}), 500

@app.route('/admin/api/monitoring')
@login_required
def api_monitoring():
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) as cnt FROM orders WHERE status='pending'")
        pending = c.fetchone()['cnt']
        c.execute("SELECT COUNT(*) as cnt FROM orders WHERE status='on_way'")
        on_way = c.fetchone()['cnt']
        c.execute("SELECT COUNT(*) as cnt FROM couriers WHERE is_busy=1 AND is_blocked=0")
        busy_couriers = c.fetchone()['cnt']
        c.execute("SELECT COUNT(*) as cnt FROM couriers WHERE is_busy=0 AND is_blocked=0 AND is_available=1")
        free_couriers = c.fetchone()['cnt']
        c.execute("SELECT COUNT(*) as cnt FROM shops WHERE is_open=1")
        open_shops = c.fetchone()['cnt']
        one_hour_ago = (datetime.now() - timedelta(hours=1)).strftime("%d.%m.%Y %H:%M")
        c.execute("SELECT COUNT(*) as cnt FROM orders WHERE created_at >= %s", (one_hour_ago,))
        last_hour = c.fetchone()['cnt']
        c.execute("""SELECT o.*, s.name as shop_name, u.full_name as user_name, u.phone as user_phone
                     FROM orders o LEFT JOIN shops s ON o.shop_id=s.id
                     LEFT JOIN users u ON o.user_tg_id=u.tg_id
                     WHERE o.status IN ('pending','confirmed') ORDER BY o.created_at ASC LIMIT 30""")
        pending_orders = []
        for o in c.fetchall():
            o = dict(o)
            try:
                created = datetime.strptime(o['created_at'], "%d.%m.%Y %H:%M")
                o['wait_min'] = int((datetime.now() - created).total_seconds() / 60)
            except:
                o['wait_min'] = 0
            pending_orders.append(o)
        c.execute("""SELECT cu.*, s.name as shop_name FROM couriers cu
                     LEFT JOIN shops s ON cu.shop_id=s.id
                     WHERE cu.is_busy=0 AND cu.is_blocked=0 AND cu.is_available=1""")
        free_couriers_list = [dict(r) for r in c.fetchall()]
        conn.close()
        return jsonify({'pending':pending,'on_way':on_way,'busy_couriers':busy_couriers,
                        'free_couriers':free_couriers,'open_shops':open_shops,'last_hour':last_hour,
                        'pending_orders':pending_orders,'free_couriers_list':free_couriers_list})
    except Exception as e:
        return jsonify({'error':str(e)}), 500

@app.route('/admin/api/orders')
@login_required
def api_orders():
    try:
        status = request.args.get('status','')
        search = request.args.get('search','')
        conn = get_db()
        c = conn.cursor()
        sql = """SELECT o.*, s.name as shop_name, u.full_name as user_name, u.phone as user_phone,
                        cu.full_name as courier_name
                 FROM orders o LEFT JOIN shops s ON o.shop_id=s.id
                 LEFT JOIN users u ON o.user_tg_id=u.tg_id
                 LEFT JOIN couriers cu ON o.courier_tg_id=cu.tg_id
                 WHERE 1=1"""
        params = []
        if status:
            sql += " AND o.status=%s"; params.append(status)
        if search:
            sql += " AND (o.order_uid ILIKE %s OR o.address ILIKE %s)"; params.extend([f"%{search}%"]*2)
        sql += " ORDER BY o.id DESC LIMIT 100"
        c.execute(sql, params)
        orders = [dict(r) for r in c.fetchall()]
        c.execute("SELECT COUNT(*) as cnt FROM orders")
        total = c.fetchone()['cnt']
        conn.close()
        return jsonify({'orders':orders,'total':total})
    except Exception as e:
        return jsonify({'error':str(e)}), 500

@app.route('/admin/api/order-detail')
@login_required
def api_order_detail():
    try:
        uid = request.args.get('uid','')
        conn = get_db()
        c = conn.cursor()
        c.execute("""SELECT o.*, s.name as shop_name FROM orders o LEFT JOIN shops s ON o.shop_id=s.id
                     WHERE o.order_uid=%s""", (uid,))
        order = c.fetchone()
        if not order:
            conn.close()
            return jsonify({'order': None})
        order = dict(order)
        user = None
        if order['user_tg_id']:
            c.execute("SELECT * FROM users WHERE tg_id=%s", (order['user_tg_id'],))
            u = c.fetchone()
            if u: user = dict(u)
        courier = None
        if order['courier_tg_id']:
            c.execute("""SELECT cu.*, s.name as shop_name FROM couriers cu LEFT JOIN shops s ON cu.shop_id=s.id WHERE cu.tg_id=%s""", (order['courier_tg_id'],))
            cu = c.fetchone()
            if cu: courier = dict(cu)
        conn.close()
        return jsonify({'order':order,'user':user,'courier':courier})
    except Exception as e:
        return jsonify({'error':str(e)}), 500

@app.route('/admin/api/users')
@login_required
def api_users():
    try:
        search = request.args.get('search','')
        conn = get_db()
        c = conn.cursor()
        sql = """SELECT u.*, COUNT(o.id) as order_count, COALESCE(SUM(o.total_sum),0) as total_spent
                 FROM users u LEFT JOIN orders o ON u.tg_id=o.user_tg_id AND o.status='delivered'
                 WHERE 1=1"""
        params = []
        if search:
            sql += " AND (u.full_name ILIKE %s OR u.phone ILIKE %s OR CAST(u.id AS TEXT) ILIKE %s OR CAST(u.tg_id AS TEXT) ILIKE %s)"
            params.extend([f"%{search}%"]*4)
        sql += " GROUP BY u.id,u.tg_id,u.username,u.full_name,u.phone,u.registered_at,u.is_blocked ORDER BY u.id DESC LIMIT 100"
        c.execute(sql, params)
        users = [dict(r) for r in c.fetchall()]
        c.execute("SELECT COUNT(*) as cnt FROM users")
        total = c.fetchone()['cnt']
        conn.close()
        return jsonify({'users':users,'total':total})
    except Exception as e:
        return jsonify({'error':str(e)}), 500

@app.route('/admin/api/user-detail')
@login_required
def api_user_detail():
    try:
        tg_id = request.args.get('tg_id')
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE tg_id=%s", (tg_id,))
        user = c.fetchone()
        if not user:
            conn.close()
            return jsonify({'user': None})
        user = dict(user)
        c.execute("SELECT COUNT(*) as cnt FROM orders WHERE user_tg_id=%s", (tg_id,))
        order_count = c.fetchone()['cnt']
        c.execute("SELECT COALESCE(SUM(total_sum),0) as t FROM orders WHERE user_tg_id=%s AND status='delivered'", (tg_id,))
        total_spent = c.fetchone()['t']
        c.execute("""SELECT o.*, s.name as shop_name FROM orders o LEFT JOIN shops s ON o.shop_id=s.id
                     WHERE o.user_tg_id=%s ORDER BY o.id DESC LIMIT 20""", (tg_id,))
        orders = [dict(r) for r in c.fetchall()]
        conn.close()
        return jsonify({'user':user,'order_count':order_count,'total_spent':float(total_spent),'orders':orders})
    except Exception as e:
        return jsonify({'error':str(e)}), 500

@app.route('/admin/api/user/block', methods=['POST'])
@login_required
def api_user_block():
    try:
        data = request.json
        db_query("UPDATE users SET is_blocked=%s WHERE tg_id=%s", (data['block'], data['tg_id']), commit=True)
        return jsonify({'ok':True})
    except Exception as e:
        return jsonify({'error':str(e)}), 500

@app.route('/admin/api/couriers')
@login_required
def api_couriers():
    try:
        search = request.args.get('search','')
        conn = get_db()
        c = conn.cursor()
        sql = """SELECT cu.*, s.name as shop_name,
                 (SELECT COUNT(*) FROM orders WHERE courier_tg_id=cu.tg_id AND status='delivered') as delivered_count
                 FROM couriers cu LEFT JOIN shops s ON cu.shop_id=s.id WHERE 1=1"""
        params = []
        if search:
            sql += " AND (cu.full_name ILIKE %s OR cu.phone ILIKE %s OR CAST(cu.tg_id AS TEXT) ILIKE %s)"
            params.extend([f"%{search}%"]*3)
        sql += " ORDER BY cu.id DESC LIMIT 100"
        c.execute(sql, params)
        couriers = [dict(r) for r in c.fetchall()]
        c.execute("SELECT COUNT(*) as cnt FROM couriers")
        total = c.fetchone()['cnt']
        conn.close()
        return jsonify({'couriers':couriers,'total':total})
    except Exception as e:
        return jsonify({'error':str(e)}), 500

@app.route('/admin/api/courier-detail')
@login_required
def api_courier_detail():
    try:
        tg_id = request.args.get('tg_id')
        conn = get_db()
        c = conn.cursor()
        c.execute("""SELECT cu.*, s.name as shop_name FROM couriers cu LEFT JOIN shops s ON cu.shop_id=s.id WHERE cu.tg_id=%s""", (tg_id,))
        courier = c.fetchone()
        if not courier:
            conn.close()
            return jsonify({'courier': None})
        courier = dict(courier)
        c.execute("SELECT COUNT(*) as cnt FROM orders WHERE courier_tg_id=%s AND status='delivered'", (tg_id,))
        delivered_count = c.fetchone()['cnt']
        conn.close()
        return jsonify({'courier':courier,'delivered_count':delivered_count})
    except Exception as e:
        return jsonify({'error':str(e)}), 500

@app.route('/admin/api/courier/block', methods=['POST'])
@login_required
def api_courier_block():
    try:
        data = request.json
        db_query("UPDATE couriers SET is_blocked=%s WHERE tg_id=%s", (data['block'], data['tg_id']), commit=True)
        return jsonify({'ok':True})
    except Exception as e:
        return jsonify({'error':str(e)}), 500

@app.route('/admin/api/courier/delete', methods=['POST'])
@login_required
def api_courier_delete():
    try:
        data = request.json
        db_query("DELETE FROM couriers WHERE tg_id=%s", (data['tg_id'],), commit=True)
        return jsonify({'ok':True})
    except Exception as e:
        return jsonify({'error':str(e)}), 500

@app.route('/admin/api/shops')
@login_required
def api_shops():
    try:
        search = request.args.get('search','')
        conn = get_db()
        c = conn.cursor()
        sql = """SELECT s.*,
                 (SELECT COUNT(*) FROM orders WHERE shop_id=s.id AND status='delivered') as order_count,
                 (SELECT COALESCE(SUM(total_sum),0) FROM orders WHERE shop_id=s.id AND status='delivered') as total_income
                 FROM shops s WHERE 1=1"""
        params = []
        if search:
            sql += " AND (s.name ILIKE %s OR CAST(s.id AS TEXT) ILIKE %s)"
            params.extend([f"%{search}%"]*2)
        sql += " ORDER BY s.id"
        c.execute(sql, params)
        shops = [dict(r) for r in c.fetchall()]
        conn.close()
        return jsonify({'shops':shops})
    except Exception as e:
        return jsonify({'error':str(e)}), 500

@app.route('/admin/api/shop-detail')
@login_required
def api_shop_detail():
    try:
        shop_id = request.args.get('id')
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM shops WHERE id=%s", (shop_id,))
        shop = c.fetchone()
        if not shop:
            conn.close()
            return jsonify({'shop': None})
        shop = dict(shop)
        # Owner name
        c.execute("SELECT full_name FROM users WHERE tg_id=%s", (shop['owner_tg_id'],))
        owner_row = c.fetchone()
        owner_name = owner_row['full_name'] if owner_row else None
        # Stats
        today = datetime.now().strftime("%d.%m.%Y")
        c.execute("SELECT COUNT(*) as cnt, COALESCE(SUM(total_sum),0) as inc FROM orders WHERE shop_id=%s AND status='delivered'", (shop_id,))
        r = c.fetchone(); total_orders = r['cnt']; total_income = r['inc']
        c.execute("SELECT COUNT(*) as cnt, COALESCE(SUM(total_sum),0) as inc FROM orders WHERE shop_id=%s AND status='delivered' AND created_at LIKE %s", (shop_id, f"{today}%"))
        r = c.fetchone(); today_orders = r['cnt']; today_income = r['inc']
        c.execute("SELECT COUNT(*) as cnt FROM orders WHERE shop_id=%s AND payment_type='naqt' AND status='delivered'", (shop_id,))
        cash_count = c.fetchone()['cnt']
        c.execute("SELECT COUNT(*) as cnt FROM orders WHERE shop_id=%s AND payment_type='karta' AND status='delivered'", (shop_id,))
        card_count = c.fetchone()['cnt']
        c.execute("SELECT COUNT(*) as cnt FROM products WHERE shop_id=%s AND (is_available IS NULL OR is_available=1)", (shop_id,))
        product_count = c.fetchone()['cnt']
        # Couriers
        c.execute("""SELECT cu.*, (SELECT COUNT(*) FROM orders WHERE courier_tg_id=cu.tg_id AND status='delivered') as delivered
                     FROM couriers cu WHERE cu.shop_id=%s AND cu.is_blocked=0""", (shop_id,))
        couriers = [dict(r) for r in c.fetchall()]
        # Recent orders
        c.execute("SELECT * FROM orders WHERE shop_id=%s ORDER BY id DESC LIMIT 20", (shop_id,))
        orders = [dict(r) for r in c.fetchall()]
        conn.close()
        return jsonify({'shop':shop,'owner_name':owner_name,'total_orders':total_orders,'total_income':float(total_income),
                        'today_orders':today_orders,'today_income':float(today_income),'cash_count':cash_count,
                        'card_count':card_count,'product_count':product_count,'couriers':couriers,'orders':orders})
    except Exception as e:
        return jsonify({'error':str(e)}), 500

@app.route('/admin/api/finance')
@login_required
def api_finance():
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT COALESCE(SUM(total_sum),0) as t FROM orders WHERE payment_type='naqt' AND status='delivered'")
        cash_total = c.fetchone()['t']
        c.execute("SELECT COALESCE(SUM(total_sum),0) as t FROM orders WHERE payment_type='karta' AND status='delivered'")
        card_total = c.fetchone()['t']
        c.execute("""SELECT s.name, s.admin_percent, COUNT(o.id) as order_count,
                            COALESCE(SUM(o.total_sum),0) as total_income
                     FROM shops s LEFT JOIN orders o ON s.id=o.shop_id AND o.status='delivered'
                     GROUP BY s.id, s.name, s.admin_percent""")
        shops = [dict(r) for r in c.fetchall()]
        admin_share = sum(s['total_income'] * s['admin_percent'] / 100 for s in shops)
        total = cash_total + card_total
        conn.close()
        return jsonify({'cash_total':float(cash_total),'card_total':float(card_total),
                        'admin_share':float(admin_share),'total':float(total),'shops':shops})
    except Exception as e:
        return jsonify({'error':str(e)}), 500

@app.route('/admin/api/monthly')
@login_required
def api_monthly():
    try:
        search = request.args.get('search','')
        pct_override = request.args.get('percent','')
        conn = get_db()
        c = conn.cursor()
        thirty_ago = (datetime.now() - timedelta(days=30)).strftime("%d.%m.%Y")
        today = datetime.now().strftime("%d.%m.%Y")
        sql = "SELECT * FROM shops WHERE 1=1"
        params = []
        if search:
            sql += " AND (name ILIKE %s OR CAST(id AS TEXT) ILIKE %s)"
            params.extend([f"%{search}%"]*2)
        c.execute(sql, params)
        shops = c.fetchall()
        result = []
        for s in shops:
            c.execute("SELECT COUNT(*) as cnt, COALESCE(SUM(total_sum),0) as inc FROM orders WHERE shop_id=%s AND status='delivered' AND created_at>=%s", (s['id'], thirty_ago))
            r30 = c.fetchone()
            c.execute("SELECT COALESCE(SUM(total_sum),0) as t FROM orders WHERE shop_id=%s AND status='delivered' AND created_at LIKE %s", (s['id'], f"{today}%"))
            today_inc = c.fetchone()['t']
            pct = float(pct_override) if pct_override else s['admin_percent']
            result.append({
                'id': s['id'], 'name': s['name'],
                'orders_30': r30['cnt'], 'income_30': float(r30['inc']),
                'today_income': float(today_inc),
                'admin_percent': s['admin_percent'],
                'admin_share': float(r30['inc']) * pct / 100
            })
        conn.close()
        return jsonify({'shops': result})
    except Exception as e:
        return jsonify({'error':str(e)}), 500

@app.route('/admin/api/promo')
@login_required
def api_promo():
    try:
        rows = db_query("SELECT * FROM promo_codes ORDER BY id DESC", fetchall=True)
        return jsonify({'promos': [dict(r) for r in rows] if rows else []})
    except Exception as e:
        return jsonify({'error':str(e)}), 500

@app.route('/admin/api/promo/create', methods=['POST'])
@login_required
def api_promo_create():
    try:
        import random
        data = request.json
        uid = random.randint(100000, 999999)
        now_s = datetime.now().strftime("%d.%m.%Y %H:%M")
        expires_at = None
        if data.get('days', 0) > 0:
            expires_at = (datetime.now() + timedelta(days=data['days'])).strftime("%d.%m.%Y")
        db_query("INSERT INTO promo_codes (id,code,discount_type,discount_value,min_sum,days,max_uses,used_count,created_at,expires_at) VALUES (%s,%s,%s,%s,%s,%s,%s,0,%s,%s)",
                 (uid,data['code'],data['discount_type'],data['discount_value'],data.get('min_sum',0),data.get('days',0),data.get('max_uses',0),now_s,expires_at), commit=True)
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})

@app.route('/admin/api/promo/delete', methods=['POST'])
@login_required
def api_promo_delete():
    try:
        db_query("DELETE FROM promo_codes WHERE id=%s", (request.json['id'],), commit=True)
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error':str(e)}), 500

@app.route('/admin/api/search')
@login_required
def api_search():
    try:
        q = request.args.get('q','')
        stype = request.args.get('type','all')
        if not q:
            return jsonify({})
        conn = get_db()
        c = conn.cursor()
        result = {}
        if stype in ('all','users'):
            c.execute("""SELECT u.*, COUNT(o.id) as order_count,
                                (SELECT full_name FROM couriers WHERE tg_id=u.tg_id LIMIT 1) as courier_info
                         FROM users u LEFT JOIN orders o ON u.tg_id=o.user_tg_id
                         WHERE u.full_name ILIKE %s OR u.phone ILIKE %s OR CAST(u.id AS TEXT) ILIKE %s OR CAST(u.tg_id AS TEXT) ILIKE %s
                         GROUP BY u.id,u.tg_id,u.username,u.full_name,u.phone,u.registered_at,u.is_blocked
                         LIMIT 20""", [f"%{q}%"]*4)
            result['users'] = [dict(r) for r in c.fetchall()]
        if stype in ('all','couriers'):
            c.execute("""SELECT cu.*, s.name as shop_name FROM couriers cu LEFT JOIN shops s ON cu.shop_id=s.id
                         WHERE cu.full_name ILIKE %s OR cu.phone ILIKE %s OR CAST(cu.tg_id AS TEXT) ILIKE %s
                         LIMIT 20""", [f"%{q}%"]*3)
            result['couriers'] = [dict(r) for r in c.fetchall()]
        if stype in ('all','shops'):
            c.execute("""SELECT s.*,
                         (SELECT full_name FROM users WHERE tg_id=s.owner_tg_id LIMIT 1) as owner_name,
                         (SELECT COUNT(*) FROM products WHERE shop_id=s.id) as product_count,
                         (SELECT COUNT(*) FROM orders WHERE shop_id=s.id AND payment_type='naqt' AND status='delivered') as cash_count,
                         (SELECT COUNT(*) FROM orders WHERE shop_id=s.id AND payment_type='karta' AND status='delivered') as card_count,
                         (SELECT COUNT(*) FROM orders WHERE shop_id=s.id AND status='delivered') as order_count
                         FROM shops s WHERE s.name ILIKE %s OR CAST(s.id AS TEXT) ILIKE %s LIMIT 20""", [f"%{q}%"]*2)
            result['shops'] = [dict(r) for r in c.fetchall()]
        if stype in ('all','orders'):
            c.execute("""SELECT o.*, s.name as shop_name FROM orders o LEFT JOIN shops s ON o.shop_id=s.id
                         WHERE o.order_uid ILIKE %s OR o.address ILIKE %s LIMIT 20""", [f"%{q}%"]*2)
            result['orders'] = [dict(r) for r in c.fetchall()]
        conn.close()
        return jsonify(result)
    except Exception as e:
        return jsonify({'error':str(e)}), 500

@app.route('/admin/api/problems')
@login_required
def api_problems():
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("""SELECT o.*, s.name as shop_name, u.full_name as user_name, u.phone as user_phone
                     FROM orders o LEFT JOIN shops s ON o.shop_id=s.id LEFT JOIN users u ON o.user_tg_id=u.tg_id
                     WHERE o.status='pending' ORDER BY o.created_at ASC""")
        orders = []
        for o in c.fetchall():
            o = dict(o)
            try:
                created = datetime.strptime(o['created_at'], "%d.%m.%Y %H:%M")
                o['wait_min'] = int((datetime.now() - created).total_seconds() / 60)
            except:
                o['wait_min'] = 0
            orders.append(o)
        conn.close()
        return jsonify({'orders': orders})
    except Exception as e:
        return jsonify({'error':str(e)}), 500

@app.route('/admin/api/chats')
@login_required
def api_chats():
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("""SELECT DISTINCT ON (from_tg_id, to_tg_id) from_tg_id, to_tg_id, chat_type, message as last_msg, created_at as last_time
                     FROM chats ORDER BY from_tg_id, to_tg_id, created_at DESC LIMIT 30""")
        chats = [dict(r) for r in c.fetchall()]
        conn.close()
        return jsonify({'chats': chats})
    except Exception as e:
        return jsonify({'error':str(e)}), 500

@app.route('/admin/api/chat-detail')
@login_required
def api_chat_detail():
    try:
        from_id = request.args.get('from')
        to_id = request.args.get('to')
        conn = get_db()
        c = conn.cursor()
        c.execute("""SELECT * FROM chats WHERE (from_tg_id=%s AND to_tg_id=%s) OR (from_tg_id=%s AND to_tg_id=%s)
                     ORDER BY created_at ASC LIMIT 50""", (from_id, to_id, to_id, from_id))
        messages = [dict(r) for r in c.fetchall()]
        conn.close()
        return jsonify({'messages': messages})
    except Exception as e:
        return jsonify({'error':str(e)}), 500

@app.route('/admin/api/blocked')
@login_required
def api_blocked():
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE is_blocked=1")
        users = [dict(r) for r in c.fetchall()]
        c.execute("SELECT * FROM couriers WHERE is_blocked=1")
        couriers = [dict(r) for r in c.fetchall()]
        conn.close()
        return jsonify({'users':users,'couriers':couriers})
    except Exception as e:
        return jsonify({'error':str(e)}), 500

@app.route('/admin/api/top')
@login_required
def api_top():
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("""SELECT o.user_tg_id, u.full_name, u.phone, COUNT(o.id) as order_count,
                            COALESCE(SUM(o.total_sum),0) as total_spent
                     FROM orders o LEFT JOIN users u ON u.tg_id=o.user_tg_id
                     WHERE o.status='delivered' GROUP BY o.user_tg_id,u.full_name,u.phone
                     ORDER BY order_count DESC LIMIT 20""")
        users = [dict(r) for r in c.fetchall()]
        conn.close()
        return jsonify({'users': users})
    except Exception as e:
        return jsonify({'error':str(e)}), 500

@app.route('/admin/api/weekly')
@login_required
def api_weekly():
    try:
        conn = get_db()
        c = conn.cursor()
        week_ago = (datetime.now() - timedelta(days=7)).strftime("%d.%m.%Y")
        c.execute("SELECT COUNT(*) as cnt FROM orders WHERE status='delivered' AND created_at>=%s", (week_ago,))
        total_orders = c.fetchone()['cnt']
        c.execute("SELECT COALESCE(SUM(total_sum),0) as t FROM orders WHERE status='delivered' AND created_at>=%s", (week_ago,))
        total_income = c.fetchone()['t']
        c.execute("SELECT COUNT(*) as cnt FROM users WHERE registered_at>=%s", (week_ago,))
        new_users = c.fetchone()['cnt']
        days = []
        for i in range(6,-1,-1):
            d = (datetime.now() - timedelta(days=i)).strftime("%d.%m.%Y")
            c.execute("SELECT COUNT(*) as cnt, COALESCE(SUM(total_sum),0) as income FROM orders WHERE status='delivered' AND created_at LIKE %s", (f"{d}%",))
            row = c.fetchone()
            c.execute("SELECT COUNT(*) as cnt FROM users WHERE registered_at LIKE %s", (f"{d}%",))
            nu = c.fetchone()['cnt']
            days.append({'date':d,'orders':row['cnt'],'income':float(row['income']),'new_users':nu})
        conn.close()
        return jsonify({'total_orders':total_orders,'total_income':float(total_income),'new_users':new_users,'days':days})
    except Exception as e:
        return jsonify({'error':str(e)}), 500

@app.route('/admin/api/admin-orders')
@login_required
def api_admin_orders():
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("""SELECT o.*, s.name as shop_name FROM orders o LEFT JOIN shops s ON o.shop_id=s.id
                     WHERE o.source='admin' OR o.user_tg_id=0 ORDER BY o.created_at DESC LIMIT 50""")
        orders = [dict(r) for r in c.fetchall()]
        conn.close()
        return jsonify({'orders': orders})
    except Exception as e:
        return jsonify({'error':str(e)}), 500

@app.route('/admin/api/ai-chat', methods=['POST'])
@login_required
def api_ai_chat():
    try:
        data = request.json
        msg = data.get('message','')
        history = data.get('history',[])
        stats = get_system_stats_text()
        system_prompt = f"""Sen "Olimbek SAVDO" yetkazib berish tizimining AI yordamchisisisan.
Sana: {datetime.now().strftime('%d.%m.%Y %H:%M')}

Hozirgi tizim holati:
{stats}

Administratorning savollariga qisqa, aniq va foydali javob ber. 
Raqamlarni fonetik o'qimay, to'g'ridan-to'g'ri yoz.
O'zbek tilida javob ber."""
        reply = call_ai(system_prompt, msg, history)
        return jsonify({'reply': reply})
    except Exception as e:
        return jsonify({'reply': f'Xatolik: {str(e)}'}), 500

# ===================== SHOP API ENDPOINTS =====================
@app.route('/shop/api/overview')
@shop_login_required
def shop_api_overview():
    try:
        shop_id = request.args.get('shop_id') or session.get('shop_id')
        conn = get_db()
        c = conn.cursor()
        today = datetime.now().strftime("%d.%m.%Y")
        c.execute("SELECT COUNT(*) as cnt, COALESCE(SUM(total_sum),0) as inc FROM orders WHERE shop_id=%s AND status='delivered'", (shop_id,))
        r = c.fetchone(); total_orders = r['cnt']; total_income = r['inc']
        c.execute("SELECT COUNT(*) as cnt, COALESCE(SUM(total_sum),0) as inc FROM orders WHERE shop_id=%s AND status='delivered' AND created_at LIKE %s", (shop_id, f"{today}%"))
        r = c.fetchone(); today_orders = r['cnt']; today_income = r['inc']
        c.execute("SELECT COUNT(*) as cnt FROM orders WHERE shop_id=%s AND status='pending'", (shop_id,))
        pending = c.fetchone()['cnt']
        c.execute("SELECT COUNT(*) as cnt FROM couriers WHERE shop_id=%s AND is_busy=0 AND is_blocked=0", (shop_id,))
        free_couriers = c.fetchone()['cnt']
        c.execute("SELECT COUNT(*) as cnt FROM couriers WHERE shop_id=%s AND is_blocked=0", (shop_id,))
        total_couriers = c.fetchone()['cnt']
        c.execute("""SELECT o.* FROM orders o WHERE o.shop_id=%s ORDER BY o.id DESC LIMIT 10""", (shop_id,))
        recent_orders = [dict(r) for r in c.fetchall()]
        conn.close()
        return jsonify({'total_orders':total_orders,'total_income':float(total_income),'today_orders':today_orders,
                        'today_income':float(today_income),'pending':pending,'free_couriers':free_couriers,
                        'total_couriers':total_couriers,'recent_orders':recent_orders})
    except Exception as e:
        return jsonify({'error':str(e)}), 500

@app.route('/shop/api/orders')
@shop_login_required
def shop_api_orders():
    try:
        shop_id = request.args.get('shop_id') or session.get('shop_id')
        conn = get_db()
        c = conn.cursor()
        c.execute("""SELECT o.*, cu.full_name as courier_name FROM orders o
                     LEFT JOIN couriers cu ON o.courier_tg_id=cu.tg_id
                     WHERE o.shop_id=%s ORDER BY o.id DESC LIMIT 100""", (shop_id,))
        orders = [dict(r) for r in c.fetchall()]
        conn.close()
        return jsonify({'orders': orders})
    except Exception as e:
        return jsonify({'error':str(e)}), 500

@app.route('/shop/api/couriers')
@shop_login_required
def shop_api_couriers():
    try:
        shop_id = request.args.get('shop_id') or session.get('shop_id')
        conn = get_db()
        c = conn.cursor()
        c.execute("""SELECT cu.*,
                     (SELECT COUNT(*) FROM orders WHERE courier_tg_id=cu.tg_id AND status='delivered') as delivered
                     FROM couriers cu WHERE cu.shop_id=%s ORDER BY cu.id""", (shop_id,))
        couriers = [dict(r) for r in c.fetchall()]
        conn.close()
        return jsonify({'couriers': couriers})
    except Exception as e:
        return jsonify({'error':str(e)}), 500

@app.route('/shop/api/report30')
@shop_login_required
def shop_api_report30():
    try:
        shop_id = request.args.get('shop_id') or session.get('shop_id')
        conn = get_db()
        c = conn.cursor()
        thirty_ago = (datetime.now() - timedelta(days=30)).strftime("%d.%m.%Y")
        c.execute("SELECT COUNT(*) as cnt, COALESCE(SUM(total_sum),0) as inc FROM orders WHERE shop_id=%s AND status='delivered' AND created_at>=%s", (shop_id, thirty_ago))
        r = c.fetchone()
        days = []
        for i in range(29, -1, -1):
            d = (datetime.now() - timedelta(days=i)).strftime("%d.%m.%Y")
            c.execute("SELECT COUNT(*) as cnt, COALESCE(SUM(total_sum),0) as inc FROM orders WHERE shop_id=%s AND status='delivered' AND created_at LIKE %s", (shop_id, f"{d}%"))
            row = c.fetchone()
            days.append({'date':d,'orders':row['cnt'],'income':float(row['inc'])})
        conn.close()
        return jsonify({'total_orders':r['cnt'],'total_income':float(r['inc']),'days':days})
    except Exception as e:
        return jsonify({'error':str(e)}), 500

@app.route('/shop/api/today')
@shop_login_required
def shop_api_today():
    try:
        shop_id = request.args.get('shop_id') or session.get('shop_id')
        today = datetime.now().strftime("%d.%m.%Y")
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) as cnt, COALESCE(SUM(total_sum),0) as inc FROM orders WHERE shop_id=%s AND status='delivered' AND created_at LIKE %s", (shop_id, f"{today}%"))
        r = c.fetchone()
        c.execute("SELECT * FROM orders WHERE shop_id=%s AND created_at LIKE %s ORDER BY id DESC", (shop_id, f"{today}%"))
        orders = [dict(row) for row in c.fetchall()]
        conn.close()
        return jsonify({'count':r['cnt'],'income':float(r['inc']),'orders':orders})
    except Exception as e:
        return jsonify({'error':str(e)}), 500

@app.route('/shop/api/ai-chat', methods=['POST'])
@shop_login_required
def shop_api_ai_chat():
    try:
        data = request.json
        msg = data.get('message','')
        history = data.get('history',[])
        shop_id = data.get('shop_id') or session.get('shop_id')
        stats = get_system_stats_text(shop_id=shop_id)
        shop_name = session.get('shop_name', 'Do\'kon')
        system_prompt = f"""Sen "{shop_name}" do'konining AI yordamchisisisan.
Sana: {datetime.now().strftime('%d.%m.%Y %H:%M')}

Do'kon holati:
{stats}

Do'kon egasining savollariga qisqa va aniq javob ber.
Faqat ushbu do'kon haqida javob ber.
O'zbek tilida yoz."""
        reply = call_ai(system_prompt, msg, history)
        return jsonify({'reply': reply})
    except Exception as e:
        return jsonify({'reply': f'Xatolik: {str(e)}'}), 500

# ===================== SHOP PASSWORD MANAGEMENT =====================
@app.route('/admin/api/shop/set-password', methods=['POST'])
@login_required
def api_shop_set_password():
    try:
        data = request.json
        shop_id = data['shop_id']
        password = data['password']
        conn = get_db()
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS shop_passwords (shop_id BIGINT PRIMARY KEY, password TEXT)""")
        c.execute("INSERT INTO shop_passwords (shop_id, password) VALUES (%s,%s) ON CONFLICT (shop_id) DO UPDATE SET password=EXCLUDED.password",
                  (shop_id, password))
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error':str(e)}), 500

# ===================== RUN =====================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
