"""
OLIMBEK SAVDO - Admin Web Panel
================================
Bu faylni asosiy bot faylingizga QO'SHING (import qiling)
yoki alohida ishga tushirishingiz mumkin.

Railway da ishlatish:
1. Ushbu kodni main bot fayliga qo'shing
2. Environment variables qo'shing:
   ADMIN_WEB_USER=admin
   ADMIN_WEB_PASS=sizning_parolingiz
3. Deploy qiling
"""

import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template_string, request, session, redirect, url_for, jsonify


# ===================== CONFIG =====================
DATABASE_URL = os.environ.get("DATABASE_URL")
ADMIN_WEB_USER = os.environ.get("ADMIN_WEB_USER", "admin")
ADMIN_WEB_PASS = os.environ.get("ADMIN_WEB_PASS", "admin123")
SECRET_KEY = os.environ.get("SECRET_KEY", "olimbek-savdo-secret-2024")

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

# ===================== HTML TEMPLATE =====================
BASE_HTML = '''<!DOCTYPE html>
<html lang="uz">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{% block title %}Admin Panel{% endblock %} — Olimbek SAVDO</title>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #0a0e1a;
    --surface: #111827;
    --surface2: #1a2235;
    --border: #1e2d45;
    --accent: #00d4aa;
    --accent2: #0ea5e9;
    --accent3: #f59e0b;
    --danger: #ef4444;
    --text: #e2e8f0;
    --text2: #94a3b8;
    --green: #22c55e;
    --sidebar-w: 260px;
  }
  * { margin:0; padding:0; box-sizing:border-box; }
  body { background:var(--bg); color:var(--text); font-family:'DM Sans',sans-serif; display:flex; min-height:100vh; }

  /* SIDEBAR */
  .sidebar {
    width:var(--sidebar-w); background:var(--surface);
    border-right:1px solid var(--border); display:flex;
    flex-direction:column; position:fixed; height:100vh;
    overflow-y:auto; z-index:100;
  }
  .sidebar-logo {
    padding:24px 20px 16px; border-bottom:1px solid var(--border);
  }
  .sidebar-logo h1 {
    font-family:'Syne',sans-serif; font-size:18px; font-weight:800;
    color:var(--accent); letter-spacing:-0.5px;
  }
  .sidebar-logo span { font-size:11px; color:var(--text2); }
  .sidebar-nav { padding:12px 0; flex:1; }
  .nav-group { padding:8px 16px 4px; font-size:10px; font-weight:600;
    color:var(--text2); letter-spacing:1.5px; text-transform:uppercase; }
  .nav-item {
    display:flex; align-items:center; gap:10px; padding:10px 20px;
    color:var(--text2); text-decoration:none; font-size:13.5px;
    font-weight:500; transition:all 0.15s; cursor:pointer; border:none;
    background:none; width:100%; text-align:left;
  }
  .nav-item:hover, .nav-item.active {
    color:var(--text); background:var(--surface2);
    border-left:3px solid var(--accent);
    padding-left:17px;
  }
  .nav-item .icon { font-size:16px; width:20px; text-align:center; }
  .nav-badge {
    margin-left:auto; background:var(--danger); color:#fff;
    font-size:10px; padding:2px 7px; border-radius:20px; font-weight:700;
  }
  .sidebar-footer {
    padding:16px 20px; border-top:1px solid var(--border);
    font-size:12px; color:var(--text2);
  }

  /* MAIN */
  .main { margin-left:var(--sidebar-w); flex:1; display:flex; flex-direction:column; min-height:100vh; }
  .topbar {
    background:var(--surface); border-bottom:1px solid var(--border);
    padding:14px 28px; display:flex; align-items:center;
    justify-content:space-between; position:sticky; top:0; z-index:50;
  }
  .topbar-title { font-family:'Syne',sans-serif; font-size:20px; font-weight:700; }
  .topbar-right { display:flex; align-items:center; gap:16px; }
  .live-badge {
    display:flex; align-items:center; gap:6px;
    background:rgba(34,197,94,0.1); border:1px solid rgba(34,197,94,0.3);
    padding:5px 12px; border-radius:20px; font-size:12px; color:var(--green);
  }
  .live-dot { width:7px; height:7px; background:var(--green); border-radius:50%;
    animation:pulse 1.5s infinite; }
  @keyframes pulse { 0%,100%{opacity:1;} 50%{opacity:0.3;} }
  .logout-btn {
    background:rgba(239,68,68,0.1); border:1px solid rgba(239,68,68,0.3);
    color:var(--danger); padding:6px 14px; border-radius:8px;
    font-size:12px; cursor:pointer; text-decoration:none; font-weight:500;
  }

  /* CONTENT */
  .content { padding:28px; flex:1; }

  /* STATS GRID */
  .stats-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(200px,1fr)); gap:16px; margin-bottom:28px; }
  .stat-card {
    background:var(--surface); border:1px solid var(--border);
    border-radius:14px; padding:20px; position:relative; overflow:hidden;
    transition:transform 0.2s, border-color 0.2s;
  }
  .stat-card:hover { transform:translateY(-2px); border-color:var(--accent); }
  .stat-card::before {
    content:''; position:absolute; top:0; left:0; right:0; height:3px;
    background:linear-gradient(90deg,var(--c1),var(--c2));
  }
  .stat-card .stat-icon { font-size:28px; margin-bottom:12px; }
  .stat-card .stat-value { font-family:'Syne',sans-serif; font-size:28px; font-weight:800; color:var(--text); }
  .stat-card .stat-label { font-size:12px; color:var(--text2); margin-top:4px; font-weight:500; }
  .stat-card .stat-sub { font-size:11px; color:var(--text2); margin-top:6px; }

  /* TABLE */
  .card {
    background:var(--surface); border:1px solid var(--border);
    border-radius:14px; overflow:hidden; margin-bottom:20px;
  }
  .card-header {
    padding:16px 20px; border-bottom:1px solid var(--border);
    display:flex; align-items:center; justify-content:space-between;
  }
  .card-header h3 { font-family:'Syne',sans-serif; font-size:15px; font-weight:700; }
  .card-body { padding:0; }
  table { width:100%; border-collapse:collapse; font-size:13px; }
  thead tr { background:var(--surface2); }
  th { padding:12px 16px; text-align:left; font-size:11px; font-weight:600;
    color:var(--text2); text-transform:uppercase; letter-spacing:0.8px; }
  td { padding:12px 16px; border-top:1px solid var(--border); color:var(--text); vertical-align:middle; }
  tr:hover td { background:rgba(255,255,255,0.02); }
  .td-wrap { max-width:220px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }

  /* BADGES */
  .badge {
    display:inline-block; padding:3px 10px; border-radius:20px;
    font-size:11px; font-weight:600;
  }
  .badge-green { background:rgba(34,197,94,0.15); color:var(--green); }
  .badge-yellow { background:rgba(245,158,11,0.15); color:var(--accent3); }
  .badge-red { background:rgba(239,68,68,0.15); color:var(--danger); }
  .badge-blue { background:rgba(14,165,233,0.15); color:var(--accent2); }
  .badge-gray { background:rgba(148,163,184,0.15); color:var(--text2); }

  /* BUTTONS */
  .btn {
    display:inline-flex; align-items:center; gap:6px;
    padding:8px 16px; border-radius:8px; font-size:13px;
    font-weight:500; cursor:pointer; border:none; text-decoration:none;
    transition:all 0.15s;
  }
  .btn-primary { background:var(--accent); color:#000; }
  .btn-primary:hover { opacity:0.85; }
  .btn-danger { background:rgba(239,68,68,0.15); color:var(--danger); border:1px solid rgba(239,68,68,0.3); }
  .btn-danger:hover { background:rgba(239,68,68,0.25); }
  .btn-sm { padding:5px 11px; font-size:12px; }
  .btn-ghost { background:var(--surface2); color:var(--text2); border:1px solid var(--border); }
  .btn-ghost:hover { color:var(--text); }

  /* SEARCH */
  .search-bar {
    display:flex; gap:10px; margin-bottom:20px; align-items:center;
  }
  .search-input {
    flex:1; background:var(--surface); border:1px solid var(--border);
    border-radius:10px; padding:10px 16px; color:var(--text);
    font-size:13px; outline:none; font-family:'DM Sans',sans-serif;
  }
  .search-input:focus { border-color:var(--accent); }
  .search-select {
    background:var(--surface); border:1px solid var(--border);
    border-radius:10px; padding:10px 14px; color:var(--text);
    font-size:13px; outline:none;
  }

  /* MODAL */
  .modal-overlay {
    display:none; position:fixed; inset:0;
    background:rgba(0,0,0,0.7); z-index:200; align-items:center; justify-content:center;
  }
  .modal-overlay.open { display:flex; }
  .modal {
    background:var(--surface); border:1px solid var(--border);
    border-radius:16px; padding:28px; max-width:560px; width:90%;
    max-height:85vh; overflow-y:auto;
  }
  .modal h2 { font-family:'Syne',sans-serif; font-size:18px; margin-bottom:20px; }
  .form-group { margin-bottom:16px; }
  .form-label { display:block; font-size:12px; color:var(--text2); margin-bottom:6px; font-weight:500; }
  .form-control {
    width:100%; background:var(--surface2); border:1px solid var(--border);
    border-radius:10px; padding:10px 14px; color:var(--text);
    font-size:13px; outline:none; font-family:'DM Sans',sans-serif;
  }
  .form-control:focus { border-color:var(--accent); }
  .form-row { display:grid; grid-template-columns:1fr 1fr; gap:12px; }

  /* LOGIN PAGE */
  .login-page {
    display:flex; align-items:center; justify-content:center;
    min-height:100vh; background:var(--bg);
    background-image:radial-gradient(ellipse at 20% 50%, rgba(0,212,170,0.05) 0%, transparent 50%),
                     radial-gradient(ellipse at 80% 20%, rgba(14,165,233,0.05) 0%, transparent 50%);
  }
  .login-box {
    background:var(--surface); border:1px solid var(--border);
    border-radius:20px; padding:40px; width:380px;
  }
  .login-logo { font-family:'Syne',sans-serif; font-size:24px; font-weight:800;
    color:var(--accent); margin-bottom:6px; }
  .login-sub { font-size:13px; color:var(--text2); margin-bottom:28px; }
  .error-msg { background:rgba(239,68,68,0.1); border:1px solid rgba(239,68,68,0.3);
    color:var(--danger); padding:10px 14px; border-radius:8px; font-size:13px; margin-bottom:16px; }

  /* MISC */
  .section-page { display:none; }
  .section-page.active { display:block; }
  .empty-state { text-align:center; padding:48px; color:var(--text2); }
  .empty-state .empty-icon { font-size:48px; margin-bottom:12px; }
  .two-col { display:grid; grid-template-columns:1fr 1fr; gap:20px; }
  .scrollable-table { overflow-x:auto; }
  .chat-msg { padding:10px 14px; border-radius:10px; margin-bottom:8px; max-width:80%; }
  .chat-msg.out { background:rgba(0,212,170,0.1); margin-left:auto; }
  .chat-msg.in { background:var(--surface2); }
  .chat-msg .meta { font-size:10px; color:var(--text2); margin-bottom:3px; }

  @media(max-width:768px) {
    .sidebar { transform:translateX(-100%); transition:transform 0.3s; }
    .sidebar.open { transform:translateX(0); }
    .main { margin-left:0; }
    .two-col { grid-template-columns:1fr; }
    .form-row { grid-template-columns:1fr; }
  }
</style>
</head>
<body>
{% block body %}{% endblock %}
</body>
</html>'''

# ===================== LOGIN =====================
LOGIN_HTML = '''<!DOCTYPE html>
<html lang="uz">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Kirish — Olimbek SAVDO Admin</title>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@600;700;800&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box;}
body{
  min-height:100vh;
  background:#080c18;
  font-family:'DM Sans',sans-serif;
  display:flex;
  overflow:hidden;
}

/* Animated background */
.bg-animated{
  position:fixed;inset:0;z-index:0;
  background:
    radial-gradient(ellipse 80% 60% at 20% 40%, rgba(0,212,170,0.12) 0%, transparent 60%),
    radial-gradient(ellipse 60% 50% at 80% 60%, rgba(14,165,233,0.10) 0%, transparent 60%),
    radial-gradient(ellipse 40% 40% at 60% 20%, rgba(139,92,246,0.08) 0%, transparent 50%);
  animation: bgmove 8s ease-in-out infinite alternate;
}
@keyframes bgmove{
  0%{background-position:0% 0%;}
  100%{background-position:100% 100%;}
}

/* Grid overlay */
.grid-overlay{
  position:fixed;inset:0;z-index:0;
  background-image:
    linear-gradient(rgba(0,212,170,0.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0,212,170,0.04) 1px, transparent 1px);
  background-size:60px 60px;
}

/* Left branding panel */
.left-panel{
  flex:1;
  display:flex;
  flex-direction:column;
  justify-content:center;
  padding:80px;
  position:relative;
  z-index:1;
}
.brand-badge{
  display:inline-flex;align-items:center;gap:8px;
  background:rgba(0,212,170,0.1);border:1px solid rgba(0,212,170,0.25);
  padding:6px 14px;border-radius:20px;
  font-size:12px;color:#00d4aa;font-weight:600;letter-spacing:1px;
  margin-bottom:32px;width:fit-content;
}
.brand-dot{width:6px;height:6px;background:#00d4aa;border-radius:50%;animation:pulse2 2s infinite;}
@keyframes pulse2{0%,100%{opacity:1;transform:scale(1);}50%{opacity:0.5;transform:scale(0.8);}}

.brand-title{
  font-family:'Syne',sans-serif;
  font-size:64px;font-weight:800;
  line-height:1.05;
  margin-bottom:20px;
}
.brand-title span.green{color:#00d4aa;}
.brand-title span.white{color:#e2e8f0;}

.brand-desc{
  font-size:17px;color:#64748b;font-weight:300;
  line-height:1.7;max-width:420px;margin-bottom:48px;
}

.stats-row{display:flex;gap:24px;flex-wrap:wrap;}
.stat-pill{
  background:rgba(255,255,255,0.04);
  border:1px solid rgba(255,255,255,0.08);
  border-radius:12px;padding:14px 20px;
}
.stat-pill .num{font-family:'Syne',sans-serif;font-size:24px;font-weight:700;color:#e2e8f0;}
.stat-pill .lbl{font-size:11px;color:#475569;margin-top:2px;}

/* Right login panel */
.right-panel{
  width:480px;min-height:100vh;
  display:flex;align-items:center;justify-content:center;
  background:rgba(17,24,39,0.85);
  backdrop-filter:blur(20px);
  border-left:1px solid rgba(255,255,255,0.06);
  position:relative;z-index:1;
  padding:40px;
}

.login-box{width:100%;max-width:380px;}

.login-header{margin-bottom:40px;}
.login-icon{
  width:56px;height:56px;
  background:linear-gradient(135deg,#00d4aa,#0ea5e9);
  border-radius:16px;
  display:flex;align-items:center;justify-content:center;
  font-size:26px;margin-bottom:24px;
  box-shadow:0 8px 32px rgba(0,212,170,0.3);
}
.login-title{
  font-family:'Syne',sans-serif;
  font-size:28px;font-weight:800;color:#f1f5f9;
  margin-bottom:8px;
}
.login-sub{font-size:14px;color:#64748b;}

.error-box{
  background:rgba(239,68,68,0.1);
  border:1px solid rgba(239,68,68,0.25);
  border-radius:10px;padding:12px 16px;
  margin-bottom:20px;
  display:flex;align-items:center;gap:10px;
  font-size:13px;color:#f87171;
}

.field{margin-bottom:20px;}
.field label{
  display:block;font-size:12px;font-weight:600;
  color:#64748b;letter-spacing:0.5px;text-transform:uppercase;
  margin-bottom:8px;
}
.field-wrap{position:relative;}
.field-icon{
  position:absolute;left:14px;top:50%;transform:translateY(-50%);
  font-size:16px;pointer-events:none;
}
.field-icon-right{
  position:absolute;right:14px;top:50%;transform:translateY(-50%);
  font-size:16px;cursor:pointer;user-select:none;
  opacity:0.6;transition:opacity 0.2s;
}
.field-icon-right:hover{opacity:1;}
.field input{
  width:100%;
  background:rgba(255,255,255,0.05);
  border:1px solid rgba(255,255,255,0.1);
  border-radius:12px;
  padding:14px 44px 14px 44px;
  color:#e2e8f0;font-size:14px;
  outline:none;
  font-family:'DM Sans',sans-serif;
  transition:all 0.2s;
}
.field input:focus{
  border-color:#00d4aa;
  background:rgba(0,212,170,0.05);
  box-shadow:0 0 0 3px rgba(0,212,170,0.1);
}
.field input::placeholder{color:#334155;}

.submit-btn{
  width:100%;padding:15px;
  background:linear-gradient(135deg,#00d4aa,#0ea5e9);
  border:none;border-radius:12px;
  font-size:15px;font-weight:700;
  color:#000;cursor:pointer;
  font-family:'Syne',sans-serif;letter-spacing:0.5px;
  transition:all 0.2s;
  margin-top:8px;
  position:relative;overflow:hidden;
}
.submit-btn:hover{
  transform:translateY(-1px);
  box-shadow:0 8px 24px rgba(0,212,170,0.4);
}
.submit-btn:active{transform:translateY(0);}

.login-footer{
  margin-top:32px;padding-top:24px;
  border-top:1px solid rgba(255,255,255,0.06);
  display:flex;align-items:center;justify-content:center;gap:8px;
  font-size:12px;color:#334155;
}
.login-footer span{color:#00d4aa;}

/* Floating cards decoration */
.float-card{
  position:absolute;
  background:rgba(17,24,39,0.8);
  border:1px solid rgba(255,255,255,0.08);
  border-radius:14px;padding:16px 20px;
  backdrop-filter:blur(10px);
}
.float-card-1{bottom:120px;left:80px;animation:float1 6s ease-in-out infinite;}
.float-card-2{top:140px;right:520px;animation:float2 7s ease-in-out infinite;}
@keyframes float1{0%,100%{transform:translateY(0);}50%{transform:translateY(-12px);}}
@keyframes float2{0%,100%{transform:translateY(-8px);}50%{transform:translateY(4px);}}

.fc-label{font-size:10px;color:#475569;margin-bottom:6px;font-weight:500;}
.fc-value{font-family:'Syne',sans-serif;font-size:20px;font-weight:700;color:#00d4aa;}
.fc-sub{font-size:10px;color:#22c55e;margin-top:2px;}

@media(max-width:900px){
  .left-panel{display:none;}
  .right-panel{width:100%;border-left:none;}
}
</style>
</head>
<body>
<div class="bg-animated"></div>
<div class="grid-overlay"></div>

<!-- LEFT BRANDING -->
<div class="left-panel">
  <div class="brand-badge">
    <span class="brand-dot"></span>
    JONLI TIZIM
  </div>

  <div class="brand-title">
    <span class="green">Olimbek</span><br>
    <span class="white">SAVDO</span>
  </div>

  <p class="brand-desc">
    Zamonaviy savdo boshqaruv tizimi. Do'konlar, kuryerlar va buyurtmalarni real vaqtda nazorat qiling.
  </p>

  <div class="stats-row">
    <div class="stat-pill">
      <div class="num">24/7</div>
      <div class="lbl">Ishlash vaqti</div>
    </div>
    <div class="stat-pill">
      <div class="num">100%</div>
      <div class="lbl">Ishonchlilik</div>
    </div>
    <div class="stat-pill">
      <div class="num">⚡</div>
      <div class="lbl">Real vaqt</div>
    </div>
  </div>

  <!-- Floating decoration cards -->
  <div class="float-card float-card-1">
    <div class="fc-label">Bugungi buyurtmalar</div>
    <div class="fc-value" id="fc-orders">— ta</div>
    <div class="fc-sub">↑ Faol</div>
  </div>
  <div class="float-card float-card-2">
    <div class="fc-label">Jonli daromad</div>
    <div class="fc-value" id="fc-income">— so'm</div>
    <div class="fc-sub">↑ O'sish</div>
  </div>
</div>

<!-- RIGHT LOGIN -->
<div class="right-panel">
  <div class="login-box">
    <div class="login-header">
      <div class="login-icon">🛒</div>
      <div class="login-title">Xush kelibsiz!</div>
      <div class="login-sub">Admin paneliga kirish uchun ma'lumotlaringizni kiriting</div>
    </div>

    {% if error %}
    <div class="error-box">
      ❌ {{ error }}
    </div>
    {% endif %}

    <form method="POST">
      <div class="field">
        <label>Username</label>
        <div class="field-wrap">
          <span class="field-icon">👤</span>
          <input type="text" name="username" placeholder="admin" required autofocus autocomplete="username">
        </div>
      </div>
      <div class="field">
        <label>Parol</label>
        <div class="field-wrap">
          <span class="field-icon">🔒</span>
          <input type="password" name="password" id="pass-input" placeholder="••••••••" required autocomplete="current-password">
          <span class="field-icon-right" id="pass-toggle" onclick="togglePass()" title="Parolni ko'rish">👁️</span>
        </div>
      </div>
      <button type="submit" class="submit-btn">🔐 Kirish</button>
    </form>

    <div class="login-footer">
      <span>🛡️</span> Olimbek SAVDO &nbsp;·&nbsp; <span>Admin Panel v2.0</span>
    </div>
  </div>
</div>

<script>
// Parolni ko'rish/yashirish
function togglePass(){
  var inp = document.getElementById('pass-input');
  var btn = document.getElementById('pass-toggle');
  if(inp.type === 'password'){
    inp.type = 'text';
    btn.textContent = '🙈';
    btn.title = 'Parolni yashirish';
  } else {
    inp.type = 'password';
    btn.textContent = '👁️';
    btn.title = "Parolni ko'rish";
  }
}

// Jonli statistika
async function loadStats(){
  try {
    const r = await fetch('/admin/api/login-stats');
    if(!r.ok) return;
    const d = await r.json();
    if(d.orders !== undefined) document.getElementById('fc-orders').textContent = d.orders + ' ta';
    if(d.income !== undefined) document.getElementById('fc-income').textContent = Number(d.income).toLocaleString('uz-UZ') + ' so\u2019m';
  } catch(e) {}
}
loadStats();
setInterval(loadStats, 30000);
</script>
</body>
</html>'''

# ===================== MAIN DASHBOARD =====================
DASHBOARD_HTML = '''<!DOCTYPE html>
<html lang="uz">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Admin Panel — Olimbek SAVDO</title>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<style>
  :root {
    --bg:#0a0e1a; --surface:#111827; --surface2:#1a2235;
    --border:#1e2d45; --accent:#00d4aa; --accent2:#0ea5e9;
    --accent3:#f59e0b; --danger:#ef4444; --text:#e2e8f0;
    --text2:#94a3b8; --green:#22c55e; --sidebar-w:260px;
  }
  /* ===== RESET & BASE ===== */
  *{margin:0;padding:0;box-sizing:border-box;}
  body{
    background:#080c18;
    color:var(--text);
    font-family:'DM Sans',sans-serif;
    display:flex;
    min-height:100vh;
    overflow-x:hidden;
  }

  /* ===== ANIMATED BG (login sahifasi uslubi) ===== */
  body::before{
    content:'';
    position:fixed;inset:0;z-index:0;
    background:
      radial-gradient(ellipse 70% 50% at 10% 30%, rgba(0,212,170,0.08) 0%, transparent 60%),
      radial-gradient(ellipse 50% 40% at 90% 70%, rgba(14,165,233,0.07) 0%, transparent 60%),
      radial-gradient(ellipse 40% 30% at 50% 10%, rgba(139,92,246,0.05) 0%, transparent 50%);
    pointer-events:none;
  }
  body::after{
    content:'';
    position:fixed;inset:0;z-index:0;
    background-image:
      linear-gradient(rgba(0,212,170,0.025) 1px, transparent 1px),
      linear-gradient(90deg, rgba(0,212,170,0.025) 1px, transparent 1px);
    background-size:60px 60px;
    pointer-events:none;
  }

  /* ===== SIDEBAR ===== */
  .sidebar{
    width:var(--sidebar-w);
    background:rgba(17,24,39,0.92);
    backdrop-filter:blur(24px);
    -webkit-backdrop-filter:blur(24px);
    border-right:1px solid rgba(255,255,255,0.07);
    display:flex;flex-direction:column;
    position:fixed;height:100vh;
    overflow:hidden;
    z-index:100;
    box-shadow:4px 0 32px rgba(0,0,0,0.4);
  }
  .sidebar-nav{
    padding:8px 0;
    flex:1;
    overflow-y:auto;
    overflow-x:hidden;
    scrollbar-width:none;
  }
  .sidebar-nav::-webkit-scrollbar{display:none;}

  /* Logo */
  .sidebar-logo{
    padding:20px 20px 16px;
    border-bottom:1px solid rgba(255,255,255,0.07);
    position:relative;
    flex-shrink:0;
  }
  .sidebar-logo::before{
    content:'';position:absolute;
    top:-20px;left:-20px;
    width:120px;height:120px;
    background:radial-gradient(circle, rgba(0,212,170,0.1) 0%, transparent 70%);
    pointer-events:none;
    z-index:0;
  }
  .logo-badge{
    display:inline-flex;align-items:center;gap:6px;
    background:rgba(0,212,170,0.1);
    border:1px solid rgba(0,212,170,0.25);
    padding:3px 10px;border-radius:20px;
    font-size:9px;color:#00d4aa;font-weight:700;letter-spacing:1.2px;
    text-transform:uppercase;margin-bottom:8px;
    position:relative;z-index:1;
  }
  .logo-dot{width:5px;height:5px;background:#00d4aa;border-radius:50%;animation:pulse 2s infinite;}
  .sidebar-logo h1{
    font-family:'Syne',sans-serif;font-size:22px;font-weight:800;
    line-height:1.15;
    background:linear-gradient(135deg,#00d4aa,#0ea5e9);
    -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
    position:relative;z-index:1;
  }
  .sidebar-logo span{font-size:11px;color:#475569;margin-top:3px;display:block;position:relative;z-index:1;}

  .nav-group{
    padding:12px 20px 4px;
    font-size:9px;font-weight:700;color:#334155;
    letter-spacing:2px;text-transform:uppercase;
  }
  .nav-item{
    display:flex;align-items:center;gap:11px;
    padding:10px 20px;
    color:#64748b;
    text-decoration:none;font-size:13px;font-weight:500;
    transition:all 0.18s;cursor:pointer;
    border:none;background:none;width:100%;text-align:left;
    border-left:2px solid transparent;
    position:relative;
  }
  .nav-item:hover{
    color:#e2e8f0;
    background:rgba(255,255,255,0.04);
    border-left-color:rgba(0,212,170,0.4);
  }
  .nav-item.active{
    color:#e2e8f0;
    background:rgba(0,212,170,0.08);
    border-left-color:#00d4aa;
  }
  .nav-item.active .icon{filter:drop-shadow(0 0 6px rgba(0,212,170,0.6));}
  .nav-item .icon{font-size:15px;width:22px;text-align:center;flex-shrink:0;}
  .nav-badge{
    margin-left:auto;
    background:linear-gradient(135deg,#ef4444,#f59e0b);
    color:#fff;font-size:10px;padding:2px 8px;
    border-radius:20px;font-weight:700;
    box-shadow:0 2px 8px rgba(239,68,68,0.4);
  }

  /* Footer */
  .sidebar-footer{
    padding:16px 20px;
    border-top:1px solid rgba(255,255,255,0.07);
    font-size:11px;color:#475569;
    background:rgba(0,0,0,0.2);
  }
  .sidebar-footer .admin-info{
    display:flex;align-items:center;gap:8px;
    background:rgba(0,212,170,0.06);
    border:1px solid rgba(0,212,170,0.15);
    border-radius:10px;padding:8px 12px;margin-bottom:8px;
  }
  .admin-avatar{
    width:28px;height:28px;
    background:linear-gradient(135deg,#00d4aa,#0ea5e9);
    border-radius:8px;display:flex;align-items:center;justify-content:center;
    font-size:13px;flex-shrink:0;
  }
  .admin-name{font-size:12px;color:#94a3b8;font-weight:500;}
  .admin-role{font-size:10px;color:#00d4aa;}

  /* ===== OVERLAY (mobile) ===== */
  .sidebar-overlay{
    display:none;position:fixed;inset:0;
    background:rgba(0,0,0,0.6);
    backdrop-filter:blur(4px);
    z-index:99;
  }
  .sidebar-overlay.show{display:block;}

  /* ===== MAIN ===== */
  .main{margin-left:var(--sidebar-w);flex:1;display:flex;flex-direction:column;min-height:100vh;position:relative;z-index:1;}

  /* ===== TOPBAR ===== */
  .topbar{
    background:rgba(17,24,39,0.85);
    backdrop-filter:blur(20px);
    -webkit-backdrop-filter:blur(20px);
    border-bottom:1px solid rgba(255,255,255,0.07);
    padding:13px 24px;
    display:flex;align-items:center;justify-content:space-between;
    position:sticky;top:0;z-index:50;
    box-shadow:0 4px 24px rgba(0,0,0,0.3);
  }
  .topbar-title{font-family:'Syne',sans-serif;font-size:18px;font-weight:700;}
  .topbar-right{display:flex;align-items:center;gap:10px;}
  .live-badge{
    display:flex;align-items:center;gap:6px;
    background:rgba(34,197,94,0.1);
    border:1px solid rgba(34,197,94,0.25);
    padding:5px 12px;border-radius:20px;font-size:12px;color:var(--green);
  }
  .live-dot{width:7px;height:7px;background:var(--green);border-radius:50%;animation:pulse 1.5s infinite;}
  @keyframes pulse{0%,100%{opacity:1;}50%{opacity:0.3;}}
  .logout-btn{
    background:rgba(239,68,68,0.1);
    border:1px solid rgba(239,68,68,0.25);
    color:var(--danger);padding:6px 14px;border-radius:8px;
    font-size:12px;cursor:pointer;text-decoration:none;font-weight:500;
    transition:all 0.15s;
  }
  .logout-btn:hover{background:rgba(239,68,68,0.2);}

  /* ===== MENU BTN ===== */
  #menu-btn{display:none;}
  .menu-btn-inner{
    background:rgba(255,255,255,0.06);
    border:1px solid rgba(255,255,255,0.1);
    color:var(--text);font-size:20px;cursor:pointer;
    padding:6px 10px;border-radius:10px;line-height:1;
    transition:all 0.15s;
  }
  .menu-btn-inner:hover{background:rgba(0,212,170,0.1);border-color:rgba(0,212,170,0.3);}

  /* ===== CONTENT ===== */
  .content{padding:22px 24px;flex:1;}
  .section-page{display:none;}
  .section-page.active{display:block;}

  /* ===== STAT CARDS ===== */
  .stats-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:14px;margin-bottom:24px;}
  .stat-card{
    background:rgba(17,24,39,0.8);
    backdrop-filter:blur(12px);
    border:1px solid rgba(255,255,255,0.07);
    border-radius:16px;padding:18px;
    position:relative;overflow:hidden;transition:transform 0.2s,border-color 0.2s,box-shadow 0.2s;
  }
  .stat-card:hover{transform:translateY(-3px);border-color:rgba(0,212,170,0.3);box-shadow:0 8px 32px rgba(0,212,170,0.1);}
  .stat-card::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;
    background:linear-gradient(90deg,var(--c1,#00d4aa),var(--c2,#0ea5e9));}
  .stat-card::after{
    content:'';position:absolute;top:-40px;right:-40px;
    width:100px;height:100px;
    background:radial-gradient(circle, var(--c1,rgba(0,212,170,0.08)) 0%, transparent 70%);
    pointer-events:none;
  }
  .stat-icon{font-size:26px;margin-bottom:10px;}
  .stat-value{font-family:'Syne',sans-serif;font-size:26px;font-weight:800;}
  .stat-label{font-size:12px;color:var(--text2);margin-top:3px;}
  .stat-sub{font-size:11px;color:var(--text2);margin-top:5px;}

  /* ===== CARDS / TABLES ===== */
  .card{
    background:rgba(17,24,39,0.8);
    backdrop-filter:blur(12px);
    border:1px solid rgba(255,255,255,0.07);
    border-radius:16px;overflow:hidden;margin-bottom:18px;
  }
  .card-header{padding:14px 18px;border-bottom:1px solid rgba(255,255,255,0.07);display:flex;align-items:center;justify-content:space-between;}
  .card-header h3{font-family:'Syne',sans-serif;font-size:14px;font-weight:700;}
  table{width:100%;border-collapse:collapse;font-size:13px;}
  thead tr{background:rgba(26,34,53,0.8);}
  th{padding:10px 14px;text-align:left;font-size:10px;font-weight:600;color:var(--text2);text-transform:uppercase;letter-spacing:0.8px;}
  td{padding:10px 14px;border-top:1px solid rgba(255,255,255,0.05);vertical-align:middle;}
  tr:hover td{background:rgba(0,212,170,0.03);}

  /* ===== BADGES ===== */
  .badge{display:inline-block;padding:3px 9px;border-radius:20px;font-size:11px;font-weight:600;}
  .badge-green{background:rgba(34,197,94,0.15);color:#22c55e;}
  .badge-yellow{background:rgba(245,158,11,0.15);color:#f59e0b;}
  .badge-red{background:rgba(239,68,68,0.15);color:#ef4444;}
  .badge-blue{background:rgba(14,165,233,0.15);color:#0ea5e9;}
  .badge-gray{background:rgba(148,163,184,0.15);color:#94a3b8;}

  /* ===== BUTTONS ===== */
  .btn{display:inline-flex;align-items:center;gap:6px;padding:7px 14px;border-radius:8px;
    font-size:12px;font-weight:500;cursor:pointer;border:none;text-decoration:none;transition:all 0.15s;}
  .btn-primary{background:linear-gradient(135deg,#00d4aa,#0ea5e9);color:#000;font-weight:600;}
  .btn-primary:hover{opacity:0.88;transform:translateY(-1px);}
  .btn-danger{background:rgba(239,68,68,0.1);color:var(--danger);border:1px solid rgba(239,68,68,0.3);}
  .btn-ghost{background:rgba(255,255,255,0.05);color:var(--text2);border:1px solid rgba(255,255,255,0.1);}
  .btn-success{background:rgba(34,197,94,0.1);color:#22c55e;border:1px solid rgba(34,197,94,0.3);}

  /* ===== INPUTS ===== */
  .search-row{display:flex;gap:10px;margin-bottom:18px;align-items:center;}
  .inp{
    background:rgba(255,255,255,0.05);
    border:1px solid rgba(255,255,255,0.1);
    border-radius:10px;padding:9px 14px;
    color:var(--text);font-size:13px;outline:none;font-family:'DM Sans',sans-serif;
    transition:all 0.2s;
  }
  .inp:focus{border-color:#00d4aa;background:rgba(0,212,170,0.05);box-shadow:0 0 0 3px rgba(0,212,170,0.08);}

  /* ===== MISC ===== */
  .two-col{display:grid;grid-template-columns:1fr 1fr;gap:18px;}
  .modal-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,0.75);backdrop-filter:blur(6px);
    z-index:200;align-items:center;justify-content:center;}
  .modal-overlay.open{display:flex;}
  .modal{
    background:rgba(17,24,39,0.95);
    backdrop-filter:blur(24px);
    border:1px solid rgba(255,255,255,0.1);
    border-radius:18px;padding:26px;max-width:580px;width:92%;max-height:88vh;overflow-y:auto;
    box-shadow:0 24px 80px rgba(0,0,0,0.6);
  }
  .modal h2{font-family:'Syne',sans-serif;font-size:17px;margin-bottom:18px;}
  .form-group{margin-bottom:14px;}
  .form-label{display:block;font-size:11px;color:var(--text2);margin-bottom:5px;font-weight:500;}
  .form-control{
    width:100%;
    background:rgba(255,255,255,0.05);
    border:1px solid rgba(255,255,255,0.1);
    border-radius:10px;padding:9px 13px;color:var(--text);font-size:13px;outline:none;
    font-family:'DM Sans',sans-serif;transition:all 0.2s;
  }
  .form-control:focus{border-color:#00d4aa;box-shadow:0 0 0 3px rgba(0,212,170,0.08);}
  .empty-state{text-align:center;padding:40px;color:var(--text2);}
  .chat-bubble{padding:10px 14px;border-radius:10px;margin-bottom:8px;max-width:75%;}
  .chat-bubble.out{background:rgba(0,212,170,0.1);margin-left:auto;text-align:right;}
  .chat-bubble.in{background:rgba(255,255,255,0.05);}
  .chat-meta{font-size:10px;color:var(--text2);margin-bottom:3px;}
  .monitor-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:12px;margin-bottom:20px;}
  .monitor-card{
    background:rgba(26,34,53,0.7);
    backdrop-filter:blur(8px);
    border:1px solid rgba(255,255,255,0.07);
    border-radius:12px;padding:16px;text-align:center;
  }
  .monitor-num{font-family:'Syne',sans-serif;font-size:32px;font-weight:800;margin-bottom:4px;}
  .monitor-lbl{font-size:12px;color:var(--text2);}

  /* ===== MOBILE ===== */
  #menu-btn{display:none;}
  @media(max-width:768px){
    #menu-btn{display:block !important;}
    .sidebar{
      transform:translateX(-100%);
      transition:transform 0.3s cubic-bezier(0.4,0,0.2,1);
      z-index:9999 !important;
      position:fixed !important;
      top:0;left:0;height:100vh;
      width:280px;
    }
    .sidebar.open{transform:translateX(0);}
    .main{margin-left:0 !important;}
    .two-col{grid-template-columns:1fr;}
    .stats-grid{grid-template-columns:repeat(2,1fr);gap:10px;}
    .topbar{padding:11px 14px;}
    .content{padding:12px;}
    .stat-card{padding:14px;}
    .stat-value{font-size:22px;}
    .stat-icon{font-size:22px;margin-bottom:7px;}
    .scrollable-table{overflow-x:auto;-webkit-overflow-scrolling:touch;}
    table{min-width:600px;}
    .modal{width:96%;padding:18px;border-radius:14px;}
    .topbar-title{font-size:15px;}
    .live-badge{display:none;}
    body::after{background-size:40px 40px;}
  }
  @media(max-width:400px){
    .stats-grid{grid-template-columns:1fr;}
  }
</style>
</head>
<body>

<!-- SIDEBAR OVERLAY (mobile) -->
<div class="sidebar-overlay" id="sidebar-overlay" onclick="closeSidebar()"></div>

<!-- SIDEBAR -->
<div class="sidebar" id="sidebar">
  <div class="sidebar-logo">
    <div class="logo-badge"><span class="logo-dot"></span> JONLI TIZIM</div>
    <h1>Olimbek<br>SAVDO</h1>
    <span>Admin boshqaruv paneli</span>
  </div>
  <div class="sidebar-nav">
    <div class="nav-group">Asosiy</div>
    <button class="nav-item active" onclick="showSection('dashboard')">
      <span class="icon">📊</span> Dashboard
    </button>
    <button class="nav-item" onclick="showSection('monitoring')">
      <span class="icon">👁️</span> Jonli monitoring
      <span class="nav-badge" id="pending-badge">...</span>
    </button>

    <div class="nav-group">Ma'lumotlar</div>
    <button class="nav-item" onclick="showSection('orders')">
      <span class="icon">📦</span> Buyurtmalar
    </button>
    <button class="nav-item" onclick="showSection('users')">
      <span class="icon">👥</span> Mijozlar
    </button>
    <button class="nav-item" onclick="showSection('couriers')">
      <span class="icon">🚚</span> Kuryerlar
    </button>
    <button class="nav-item" onclick="showSection('shops')">
      <span class="icon">🏪</span> Do'konlar
    </button>

    <div class="nav-group">Moliya</div>
    <button class="nav-item" onclick="showSection('finance')">
      <span class="icon">💰</span> Moliya
    </button>
    <button class="nav-item" onclick="showSection('promo')">
      <span class="icon">🎟️</span> Promo kodlar
    </button>

    <div class="nav-group">Boshqaruv</div>
    <button class="nav-item" onclick="showSection('search')">
      <span class="icon">🔍</span> Qidirish
    </button>
    <button class="nav-item" onclick="showSection('chats')">
      <span class="icon">💬</span> Chatlar
    </button>
    <button class="nav-item" onclick="showSection('problems')">
      <span class="icon">⚠️</span> Muammoli
    </button>
    <button class="nav-item" onclick="showSection('blocked')">
      <span class="icon">🚫</span> Bloklangan
    </button>
    <button class="nav-item" onclick="showSection('top')">
      <span class="icon">🏆</span> Top mijozlar
    </button>
    <button class="nav-item" onclick="showSection('weekly')">
      <span class="icon">📈</span> Haftalik hisobot
    </button>
    <button class="nav-item" onclick="showSection('admin-orders')">
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

<!-- MAIN -->
<div class="main">
  <div class="topbar">
    <div style="display:flex;align-items:center;gap:14px;">
      <button onclick="event.stopPropagation();document.getElementById('sidebar').classList.contains('open')?closeSidebar():openSidebar()"
        class="menu-btn-inner" id="menu-btn">☰</button>
      <div class="topbar-title" id="page-title">Dashboard</div>
    </div>
    <div class="topbar-right">
      <div class="live-badge"><div class="live-dot"></div> JONLI</div>
      <a href="/admin/logout" class="logout-btn">🚪 Chiqish</a>
    </div>
  </div>

  <div class="content">

    <!-- ===== DASHBOARD ===== -->
    <div class="section-page active" id="sec-dashboard">
      <div class="stats-grid" id="stats-grid">
        <div class="stat-card" style="--c1:#00d4aa;--c2:#0ea5e9;">
          <div class="stat-icon">👥</div>
          <div class="stat-value" id="s-users">—</div>
          <div class="stat-label">Jami mijozlar</div>
        </div>
        <div class="stat-card" style="--c1:#f59e0b;--c2:#ef4444;">
          <div class="stat-icon">🏪</div>
          <div class="stat-value" id="s-shops">—</div>
          <div class="stat-label">Do'konlar</div>
          <div class="stat-sub" id="s-shops-open"></div>
        </div>
        <div class="stat-card" style="--c1:#8b5cf6;--c2:#ec4899;">
          <div class="stat-icon">🚚</div>
          <div class="stat-value" id="s-couriers">—</div>
          <div class="stat-label">Kuryerlar</div>
        </div>
        <div class="stat-card" style="--c1:#22c55e;--c2:#00d4aa;">
          <div class="stat-icon">📦</div>
          <div class="stat-value" id="s-orders">—</div>
          <div class="stat-label">Jami buyurtmalar</div>
        </div>
        <div class="stat-card" style="--c1:#0ea5e9;--c2:#8b5cf6;">
          <div class="stat-icon">💰</div>
          <div class="stat-value" id="s-income">—</div>
          <div class="stat-label">Jami daromad</div>
        </div>
        <div class="stat-card" style="--c1:#f59e0b;--c2:#22c55e;">
          <div class="stat-icon">📅</div>
          <div class="stat-value" id="s-today">—</div>
          <div class="stat-label">Bugungi daromad</div>
        </div>
        <div class="stat-card" style="--c1:#ef4444;--c2:#f59e0b;">
          <div class="stat-icon">⏳</div>
          <div class="stat-value" id="s-pending">—</div>
          <div class="stat-label">Kutilayotgan</div>
        </div>
        <div class="stat-card" style="--c1:#00d4aa;--c2:#22c55e;">
          <div class="stat-icon">🚗</div>
          <div class="stat-value" id="s-onway">—</div>
          <div class="stat-label">Yo'lda</div>
        </div>
      </div>

      <div class="two-col">
        <div class="card">
          <div class="card-header"><h3>📦 Oxirgi buyurtmalar</h3></div>
          <div class="scrollable-table">
            <table><thead><tr><th>ID</th><th>Do'kon</th><th>Summa</th><th>Holat</th><th>Vaqt</th></tr></thead>
            <tbody id="recent-orders"></tbody></table>
          </div>
        </div>
        <div class="card">
          <div class="card-header"><h3>🏪 Do'konlar holati</h3></div>
          <div class="scrollable-table">
            <table><thead><tr><th>Do'kon</th><th>Bugun</th><th>Holat</th><th>Reyting</th></tr></thead>
            <tbody id="shops-status"></tbody></table>
          </div>
        </div>
      </div>
    </div>

    <!-- ===== MONITORING ===== -->
    <div class="section-page" id="sec-monitoring">
      <div class="monitor-grid" id="monitor-cards"></div>
      <div class="two-col">
        <div class="card">
          <div class="card-header"><h3>⏳ Kutilayotgan buyurtmalar</h3>
            <button class="btn btn-ghost" onclick="loadMonitoring()">🔄 Yangilash</button>
          </div>
          <div class="scrollable-table">
            <table><thead><tr><th>ID</th><th>Do'kon</th><th>Summa</th><th>Kutish</th><th>Status</th></tr></thead>
            <tbody id="pending-orders-list"></tbody></table>
          </div>
        </div>
        <div class="card">
          <div class="card-header"><h3>🟢 Bo'sh kuryerlar</h3></div>
          <div class="scrollable-table">
            <table><thead><tr><th>Ism</th><th>Tel</th><th>Do'kon</th></tr></thead>
            <tbody id="free-couriers-list"></tbody></table>
          </div>
        </div>
      </div>
    </div>

    <!-- ===== ORDERS ===== -->
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
        <div class="scrollable-table">
          <table><thead><tr><th>ID</th><th>Mijoz</th><th>Do'kon</th><th>Mahsulot</th><th>Summa</th><th>To'lov</th><th>Manzil</th><th>Holat</th><th>Kuryer</th><th>Vaqt</th></tr></thead>
          <tbody id="orders-table"></tbody></table>
        </div>
      </div>
    </div>

    <!-- ===== USERS ===== -->
    <div class="section-page" id="sec-users">
      <div class="search-row">
        <input class="inp" style="flex:1;" type="text" id="user-search" placeholder="🔍 Ism, telefon, ID..." oninput="loadUsers()">
        <button class="btn btn-ghost" onclick="loadUsers()">🔄</button>
      </div>
      <div class="card">
        <div class="card-header"><h3>👥 Mijozlar</h3><span id="users-count" style="color:var(--text2);font-size:12px;"></span></div>
        <div class="scrollable-table">
          <table><thead><tr><th>ID</th><th>Ism</th><th>Telefon</th><th>Username</th><th>Buyurtmalar</th><th>Xarid</th><th>Ro'yxat</th><th>Holat</th><th>Amal</th></tr></thead>
          <tbody id="users-table"></tbody></table>
        </div>
      </div>
    </div>

    <!-- ===== COURIERS ===== -->
    <div class="section-page" id="sec-couriers">
      <div class="search-row">
        <input class="inp" style="flex:1;" type="text" id="courier-search" placeholder="🔍 Ism, telefon, ID..." oninput="loadCouriers()">
        <button class="btn btn-ghost" onclick="loadCouriers()">🔄</button>
      </div>
      <div class="card">
        <div class="card-header"><h3>🚚 Kuryerlar</h3><span id="couriers-count" style="color:var(--text2);font-size:12px;"></span></div>
        <div class="scrollable-table">
          <table><thead><tr><th>ID</th><th>Ism</th><th>Telefon</th><th>TG ID</th><th>Do'kon</th><th>Yetkazgan</th><th>Band</th><th>Holat</th><th>Amal</th></tr></thead>
          <tbody id="couriers-table"></tbody></table>
        </div>
      </div>
    </div>

    <!-- ===== SHOPS ===== -->
    <div class="section-page" id="sec-shops">
      <div class="search-row">
        <input class="inp" style="flex:1;" type="text" id="shop-search" placeholder="🔍 Do'kon nomi..." oninput="loadShops()">
        <button class="btn btn-ghost" onclick="loadShops()">🔄</button>
      </div>
      <div class="card">
        <div class="card-header"><h3>🏪 Do'konlar</h3></div>
        <div class="scrollable-table">
          <table><thead><tr><th>ID</th><th>Nom</th><th>Egasi TG</th><th>Tel</th><th>Reyting</th><th>Buyurtmalar</th><th>Daromad</th><th>Admin %</th><th>Holat</th></tr></thead>
          <tbody id="shops-table"></tbody></table>
        </div>
      </div>
    </div>

    <!-- ===== FINANCE ===== -->
    <div class="section-page" id="sec-finance">
      <div class="stats-grid">
        <div class="stat-card" style="--c1:#22c55e;--c2:#00d4aa;">
          <div class="stat-icon">💵</div>
          <div class="stat-value" id="f-cash">—</div>
          <div class="stat-label">Naqd to'lovlar</div>
        </div>
        <div class="stat-card" style="--c1:#0ea5e9;--c2:#8b5cf6;">
          <div class="stat-icon">💳</div>
          <div class="stat-value" id="f-card">—</div>
          <div class="stat-label">Karta to'lovlari</div>
        </div>
        <div class="stat-card" style="--c1:#f59e0b;--c2:#ef4444;">
          <div class="stat-icon">📊</div>
          <div class="stat-value" id="f-admin">—</div>
          <div class="stat-label">Admin ulushi</div>
        </div>
        <div class="stat-card" style="--c1:#8b5cf6;--c2:#ec4899;">
          <div class="stat-icon">💰</div>
          <div class="stat-value" id="f-total">—</div>
          <div class="stat-label">Umumiy daromad</div>
        </div>
      </div>
      <div class="card">
        <div class="card-header"><h3>🏪 Do'konlar bo'yicha moliya</h3></div>
        <div class="scrollable-table">
          <table><thead><tr><th>Do'kon</th><th>Buyurtmalar</th><th>Daromad</th><th>Admin %</th><th>Admin ulushi</th></tr></thead>
          <tbody id="finance-table"></tbody></table>
        </div>
      </div>
    </div>

    <!-- ===== PROMO ===== -->
    <div class="section-page" id="sec-promo">
      <div class="search-row">
        <button class="btn btn-primary" onclick="openModal('promo-modal')">➕ Promo kod qo'shish</button>
        <button class="btn btn-ghost" onclick="loadPromo()">🔄 Yangilash</button>
      </div>
      <div class="card">
        <div class="card-header"><h3>🎟️ Promo kodlar</h3></div>
        <div class="scrollable-table">
          <table><thead><tr><th>Kod</th><th>Chegirma</th><th>Tur</th><th>Min summa</th><th>Muddat</th><th>Limit</th><th>Ishlatilgan</th><th>Holat</th><th>Amal</th></tr></thead>
          <tbody id="promo-table"></tbody></table>
        </div>
      </div>
    </div>

    <!-- ===== SEARCH ===== -->
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

    <!-- ===== CHATS ===== -->
    <div class="section-page" id="sec-chats">
      <div class="two-col" style="gap:18px;">
        <div class="card">
          <div class="card-header"><h3>💬 Chat ro'yxati</h3>
            <button class="btn btn-ghost" onclick="loadChats()">🔄</button>
          </div>
          <div id="chat-list" style="max-height:500px;overflow-y:auto;"></div>
        </div>
        <div class="card">
          <div class="card-header"><h3>💬 Chat tafsiloti</h3></div>
          <div id="chat-detail" style="padding:14px;max-height:500px;overflow-y:auto;">
            <div class="empty-state"><div style="font-size:36px;">💬</div><p>Chatni tanlang</p></div>
          </div>
        </div>
      </div>
    </div>

    <!-- ===== PROBLEMS ===== -->
    <div class="section-page" id="sec-problems">
      <div class="card">
        <div class="card-header"><h3>⚠️ Muammoli buyurtmalar (10+ daqiqa)</h3>
          <button class="btn btn-ghost" onclick="loadProblems()">🔄 Yangilash</button>
        </div>
        <div class="scrollable-table">
          <table><thead><tr><th>ID</th><th>Do'kon</th><th>Mijoz</th><th>Summa</th><th>Kutish (daqiqa)</th><th>Vaqt</th><th>Status</th></tr></thead>
          <tbody id="problems-table"></tbody></table>
        </div>
      </div>
    </div>

    <!-- ===== BLOCKED ===== -->
    <div class="section-page" id="sec-blocked">
      <div class="two-col">
        <div class="card">
          <div class="card-header"><h3>🚫 Bloklangan mijozlar</h3></div>
          <div class="scrollable-table">
            <table><thead><tr><th>Ism</th><th>Telefon</th><th>ID</th><th>Amal</th></tr></thead>
            <tbody id="blocked-users-table"></tbody></table>
          </div>
        </div>
        <div class="card">
          <div class="card-header"><h3>🚫 Bloklangan kuryerlar</h3></div>
          <div class="scrollable-table">
            <table><thead><tr><th>Ism</th><th>Telefon</th><th>ID</th><th>Amal</th></tr></thead>
            <tbody id="blocked-couriers-table"></tbody></table>
          </div>
        </div>
      </div>
    </div>

    <!-- ===== TOP MIJOZLAR ===== -->
    <div class="section-page" id="sec-top">
      <div class="card">
        <div class="card-header"><h3>🏆 Top 20 mijozlar</h3></div>
        <div class="scrollable-table">
          <table><thead><tr><th>#</th><th>Ism</th><th>Telefon</th><th>Buyurtmalar</th><th>Jami xarid</th></tr></thead>
          <tbody id="top-table"></tbody></table>
        </div>
      </div>
    </div>

    <!-- ===== WEEKLY ===== -->
    <div class="section-page" id="sec-weekly">
      <div class="stats-grid" id="weekly-stats"></div>
      <div class="card">
        <div class="card-header"><h3>📈 Kunlik statistika (7 kun)</h3></div>
        <div class="scrollable-table">
          <table><thead><tr><th>Kun</th><th>Buyurtmalar</th><th>Daromad</th><th>Yangi mijozlar</th></tr></thead>
          <tbody id="weekly-table"></tbody></table>
        </div>
      </div>
    </div>

    <!-- ===== ADMIN BUYURTMALAR ===== -->
    <div class="section-page" id="sec-admin-orders">
      <div class="card">
        <div class="card-header"><h3>📱 Admin tomonidan berilgan buyurtmalar</h3></div>
        <div class="scrollable-table">
          <table><thead><tr><th>ID</th><th>Do'kon</th><th>Manzil</th><th>Mahsulot</th><th>Summa</th><th>Holat</th><th>Vaqt</th></tr></thead>
          <tbody id="admin-orders-table"></tbody></table>
        </div>
      </div>
    </div>

  </div><!-- /content -->
</div><!-- /main -->

<!-- PROMO MODAL -->
<div class="modal-overlay" id="promo-modal">
  <div class="modal">
    <h2>➕ Yangi promo kod</h2>
    <div class="form-group">
      <label class="form-label">Kod nomi</label>
      <input class="form-control" id="pm-code" placeholder="BAHOR20" style="text-transform:uppercase;">
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
      <div class="form-group">
        <label class="form-label">Chegirma turi</label>
        <select class="form-control" id="pm-type">
          <option value="percent">% Foiz</option>
          <option value="fixed">So'm (belgilangan)</option>
        </select>
      </div>
      <div class="form-group">
        <label class="form-label">Chegirma miqdori</label>
        <input class="form-control" id="pm-value" type="number" placeholder="10">
      </div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
      <div class="form-group">
        <label class="form-label">Minimal summa (so'm)</label>
        <input class="form-control" id="pm-min" type="number" placeholder="50000">
      </div>
      <div class="form-group">
        <label class="form-label">Nech kun (0=cheksiz)</label>
        <input class="form-control" id="pm-days" type="number" placeholder="30" value="0">
      </div>
    </div>
    <div class="form-group">
      <label class="form-label">Limit (0=cheksiz)</label>
      <input class="form-control" id="pm-limit" type="number" placeholder="100" value="0">
    </div>
    <div style="display:flex;gap:10px;justify-content:flex-end;margin-top:6px;">
      <button class="btn btn-ghost" onclick="closeModal('promo-modal')">Bekor qilish</button>
      <button class="btn btn-primary" onclick="createPromo()">✅ Yaratish</button>
    </div>
  </div>
</div>

<script>
const api = (url, opts={}) => fetch(url, {headers:{'Content-Type':'application/json'},...opts}).then(r=>r.json());

// CLOCK
function updateClock(){
  const now = new Date();
  document.getElementById('clock').textContent = now.toLocaleTimeString('uz-UZ');
}
setInterval(updateClock, 1000);
updateClock();

// NAVIGATION
const sections = ['dashboard','monitoring','orders','users','couriers','shops',
  'finance','promo','search','chats','problems','blocked','top','weekly','admin-orders'];
const titles = {
  "dashboard":"📊 Dashboard","monitoring":"👁️ Jonli monitoring",
  "orders":"📦 Buyurtmalar","users":"👥 Mijozlar","couriers":"🚚 Kuryerlar",
  "shops":"🏪 Do’konlar","finance":"💰 Moliya","promo":"🎟️ Promo kodlar",
  "search":"🔍 Qidirish","chats":"💬 Chatlar","problems":"⚠️ Muammoli",
  "blocked":"🚫 Bloklangan","top":"🏆 Top mijozlar","weekly":"📈 Haftalik hisobot",
  "admin-orders":"📱 Admin buyurtmalari"
};

function showSection(name){
  sections.forEach(s => {
    document.getElementById('sec-'+s).classList.remove('active');
    document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
  });
  document.getElementById('sec-'+name).classList.add('active');
  document.getElementById('page-title').textContent = titles[name]||name;
  document.querySelectorAll('.nav-item').forEach(el => {
    if(el.getAttribute('onclick')&&el.getAttribute('onclick').includes("'"+name+"'"))
      el.classList.add('active');
  });

  const loaders = {
    'dashboard': loadDashboard,
    'monitoring': loadMonitoring,
    'orders': loadOrders,
    'users': loadUsers,
    'couriers': loadCouriers,
    'shops': loadShops,
    'finance': loadFinance,
    'promo': loadPromo,
    'chats': loadChats,
    'problems': loadProblems,
    'blocked': loadBlocked,
    'top': loadTop,
    'weekly': loadWeekly,
    'admin-orders': loadAdminOrders
  };
  if(loaders[name]) loaders[name]();
}

// STATUS BADGE
function statusBadge(s){
  if(s==="pending") return "<span class='badge badge-yellow'>⏳ Kutilmoqda</span>";
  if(s==="confirmed") return "<span class='badge badge-blue'>✅ Tasdiqlandi</span>";
  if(s==="on_way") return "<span class='badge badge-blue'>🚗 Yo\u2019lda</span>";
  if(s==="delivered") return "<span class='badge badge-green'>✅ Yetkazildi</span>";
  if(s==="rejected") return "<span class='badge badge-red'>❌ Rad etildi</span>";
  return `<span class="badge badge-gray">${s}</span>`;
}
function fmtNum(n){return Number(n||0).toLocaleString('uz-UZ');}

// ===== DASHBOARD =====
async function loadDashboard(){
  let d;
  try { d = await api('/admin/api/dashboard'); } catch(e){ console.error('Dashboard xatosi:',e); return; }
  if(!d||d.error){ console.error('Dashboard API xatosi:', d?.error||'Nomalum'); return; }
  document.getElementById('s-users').textContent = d.users??'—';
  document.getElementById('s-shops').textContent = d.shops??'—';
  document.getElementById('s-shops-open').textContent = (d.shops_open??'—')+' ta ochiq';
  document.getElementById('s-couriers').textContent = d.couriers??'—';
  document.getElementById('s-orders').textContent = d.total_orders??'—';
  document.getElementById('s-income').textContent = fmtNum(d.total_income)+' so’m';
  document.getElementById('s-today').textContent = fmtNum(d.today_income)+' so’m';
  document.getElementById('s-pending').textContent = d.pending??'—';
  document.getElementById('s-onway').textContent = d.on_way??'—';
  document.getElementById('pending-badge').textContent = d.pending??0;

  const ro = document.getElementById('recent-orders');
  ro.innerHTML = (d.recent_orders||[]).map(o=>`<tr>
    <td><code>#${o.order_uid}</code></td>
    <td style="max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${o.shop_name||'—'}</td>
    <td>${fmtNum(o.total_sum)} so’m</td>
    <td>${statusBadge(o.status)}</td>
    <td style="font-size:11px;color:var(--text2);">${o.created_at}</td>
  </tr>`).join('');

  const ss = document.getElementById('shops-status');
  ss.innerHTML = (d.shops_info||[]).map(s=>`<tr>
    <td>${s.name}</td>
    <td>${s.today_count} ta</td>
    <td>${s.is_open?'<span class="badge badge-green">🟢 Ochiq</span>':'<span class="badge badge-red">🔴 Yopiq</span>'}</td>
    <td>⭐${Number(s.rating||0).toFixed(1)}</td>
  </tr>`).join('');
}

// ===== MONITORING =====
async function loadMonitoring(){
  const d = await api('/admin/api/monitoring');
  const mc = document.getElementById('monitor-cards');
  mc.innerHTML = `
    <div class="monitor-card"><div class="monitor-num" style="color:#f59e0b;">${d.pending}</div><div class="monitor-lbl">⏳ Kutilmoqda</div></div>
    <div class="monitor-card"><div class="monitor-num" style="color:#0ea5e9;">${d.on_way}</div><div class="monitor-lbl">🚗 Yo’lda</div></div>
    <div class="monitor-card"><div class="monitor-num" style="color:#22c55e;">${d.free_couriers}</div><div class="monitor-lbl">🟢 Bo’sh kuryer</div></div>
    <div class="monitor-card"><div class="monitor-num" style="color:#ef4444;">${d.busy_couriers}</div><div class="monitor-lbl">🔴 Band kuryer</div></div>
    <div class="monitor-card"><div class="monitor-num" style="color:#00d4aa;">${d.open_shops}</div><div class="monitor-lbl">🏪 Ochiq do’kon</div></div>
    <div class="monitor-card"><div class="monitor-num" style="color:#8b5cf6;">${d.last_hour}</div><div class="monitor-lbl">🕐 Oxirgi 1 soat</div></div>
  `;
  const pol = document.getElementById('pending-orders-list');
  pol.innerHTML = (d.pending_orders||[]).map(o=>{
    const warn = o.wait_min>=10?' <span style="color:var(--danger);">🔴</span>':'';
    return `<tr>
      <td><code>#${o.order_uid}</code></td>
      <td>${o.shop_name||'—'}</td>
      <td>${fmtNum(o.total_sum)} so’m</td>
      <td>${o.wait_min} daq${warn}</td>
      <td>${statusBadge(o.status)}</td>
    </tr>`;
  }).join('') || "<tr><td colspan='5' class='empty-state'>✅ Muammo yo’q</td></tr>";

  const fcl = document.getElementById('free-couriers-list');
  fcl.innerHTML = (d.free_couriers_list||[]).map(c=>`<tr>
    <td>${c.full_name}</td>
    <td>${c.phone}</td>
    <td>${c.shop_name||'—'}</td>
  </tr>`).join('') || "<tr><td colspan='3' class='empty-state'>Bo’sh kuryer yo’q</td></tr>";
}

// ===== ORDERS =====
async function loadOrders(){
  const status = document.getElementById('order-status-filter').value;
  const search = document.getElementById('order-search').value;
  const d = await api(`/admin/api/orders?status=${status}&search=${encodeURIComponent(search)}`);
  document.getElementById('orders-count').textContent = d.total+' ta';
  const t = document.getElementById('orders-table');
  t.innerHTML = (d.orders||[]).map(o=>`<tr>
    <td><code>#${o.order_uid}</code></td>
    <td>${o.user_name||'Tel buyurtma'}<br><small style="color:var(--text2);">${o.user_phone||''}</small></td>
    <td>${o.shop_name||'—'}</td>
    <td style="max-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${o.products}">${o.products}</td>
    <td style="white-space:nowrap;">${fmtNum(o.total_sum)} so’m</td>
    <td>${o.payment_type}</td>
    <td style="max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${o.address}">${o.address}</td>
    <td>${statusBadge(o.status)}</td>
    <td>${o.courier_name||'—'}</td>
    <td style="font-size:11px;white-space:nowrap;">${o.created_at}</td>
  </tr>`).join('') || "<tr><td colspan='10' class='empty-state'>Buyurtma yo’q</td></tr>";
}

// ===== USERS =====
async function loadUsers(){
  const search = document.getElementById('user-search').value;
  const d = await api(`/admin/api/users?search=${encodeURIComponent(search)}`);
  document.getElementById('users-count').textContent = d.total+' ta';
  const t = document.getElementById('users-table');
  t.innerHTML = (d.users||[]).map(u=>`<tr>
    <td>${u.id}</td>
    <td>${u.full_name}</td>
    <td>${u.phone}</td>
    <td>${u.username?'@'+u.username:'—'}</td>
    <td>${u.order_count}</td>
    <td>${fmtNum(u.total_spent)} so’m</td>
    <td style="font-size:11px;">${u.registered_at}</td>
    <td>${u.is_blocked?'<span class="badge badge-red">🚫 Bloklangan</span>':'<span class="badge badge-green">✅ Faol</span>'}</td>
    <td>
      ${u.is_blocked
        ? `<button class="btn btn-success btn-sm" onclick="toggleUser(${u.tg_id},0)">✅ Ochish</button>`
        : `<button class="btn btn-danger btn-sm" onclick="toggleUser(${u.tg_id},1)">🚫 Bloklash</button>`
      }
    </td>
  </tr>`).join('');
}

async function toggleUser(tg_id, block){
  if(!confirm(block?'Bloklashni tasdiqlaysizmi?':'Blokdan chiqarishni tasdiqlaysizmi?')) return;
  await api('/admin/api/user/block', {method:'POST',body:JSON.stringify({tg_id,block})});
  loadUsers();
}

// ===== COURIERS =====
async function loadCouriers(){
  const search = document.getElementById('courier-search').value;
  const d = await api(`/admin/api/couriers?search=${encodeURIComponent(search)}`);
  document.getElementById('couriers-count').textContent = d.total+' ta';
  const t = document.getElementById('couriers-table');
  t.innerHTML = (d.couriers||[]).map(c=>`<tr>
    <td>${c.id}</td>
    <td>${c.full_name}</td>
    <td>${c.phone}</td>
    <td>${c.tg_id}</td>
    <td>${c.shop_name||'—'}</td>
    <td>${c.delivered_count}</td>
    <td>${c.is_busy?'<span class="badge badge-yellow">🔴 Band</span>':"<span class='badge badge-green'>🟢 Bo’sh</span>"}</td>
    <td>${c.is_blocked?'<span class="badge badge-red">🚫</span>':'<span class="badge badge-green">✅</span>'}</td>
    <td>
      ${c.is_blocked
        ? `<button class="btn btn-success btn-sm" onclick="toggleCourier(${c.tg_id},0)">✅</button>`
        : `<button class="btn btn-danger btn-sm" onclick="toggleCourier(${c.tg_id},1)">🚫</button>`
      }
      <button class="btn btn-danger btn-sm" onclick="deleteCourier(${c.tg_id})">🗑️</button>
    </td>
  </tr>`).join('');
}

async function toggleCourier(tg_id, block){
  if(!confirm(block?'Bloklashni tasdiqlaysizmi?':'Blokdan chiqarishni tasdiqlaysizmi?')) return;
  await api('/admin/api/courier/block', {method:'POST',body:JSON.stringify({tg_id,block})});
  loadCouriers();
}
async function deleteCourier(tg_id){
  if(!confirm("O’chirishni tasdiqlaysizmi?")) return;
  await api('/admin/api/courier/delete', {method:'POST',body:JSON.stringify({tg_id})});
  loadCouriers();
}

// ===== SHOPS =====
async function loadShops(){
  const search = document.getElementById('shop-search').value;
  const d = await api(`/admin/api/shops?search=${encodeURIComponent(search)}`);
  const t = document.getElementById('shops-table');
  t.innerHTML = (d.shops||[]).map(s=>`<tr>
    <td>${s.id}</td>
    <td>${s.name}</td>
    <td>${s.owner_tg_id}</td>
    <td>${s.phone||'—'}</td>
    <td>⭐${Number(s.rating||0).toFixed(1)}</td>
    <td>${s.order_count}</td>
    <td>${fmtNum(s.total_income)} so’m</td>
    <td>${s.admin_percent}%</td>
    <td>${s.is_open?'<span class="badge badge-green">🟢 Ochiq</span>':'<span class="badge badge-red">🔴 Yopiq</span>'}</td>
  </tr>`).join('');
}

// ===== FINANCE =====
async function loadFinance(){
  const d = await api('/admin/api/finance');
  document.getElementById('f-cash').textContent = fmtNum(d.cash_total)+' so’m';
  document.getElementById('f-card').textContent = fmtNum(d.card_total)+' so’m';
  document.getElementById('f-admin').textContent = fmtNum(d.admin_share)+' so’m';
  document.getElementById('f-total').textContent = fmtNum(d.total)+' so’m';
  const t = document.getElementById('finance-table');
  t.innerHTML = (d.shops||[]).map(s=>`<tr>
    <td>${s.name}</td>
    <td>${s.order_count}</td>
    <td>${fmtNum(s.total_income)} so’m</td>
    <td>${s.admin_percent}%</td>
    <td>${fmtNum(s.total_income*s.admin_percent/100)} so’m</td>
  </tr>`).join('');
}

// ===== PROMO =====
async function loadPromo(){
  const d = await api('/admin/api/promo');
  const t = document.getElementById('promo-table');
  t.innerHTML = (d.promos||[]).map(p=>{
    const active = (p.max_uses===0||p.used_count<p.max_uses)&&(!p.expires_at||new Date(p.expires_at)>=new Date());
    const valText = p.discount_type==='percent'?p.discount_value+'%':fmtNum(p.discount_value)+' so’m';
    return `<tr>
      <td><code>${p.code}</code></td>
      <td>${valText}</td>
      <td>${p.discount_type==='percent'?'Foiz':'Belgilangan'}</td>
      <td>${fmtNum(p.min_sum)} so’m</td>
      <td>${p.expires_at||'Cheksiz'}</td>
      <td>${p.max_uses||'Cheksiz'}</td>
      <td>${p.used_count}</td>
      <td>${active?'<span class="badge badge-green">✅ Faol</span>':'<span class="badge badge-red">❌ Tugagan</span>'}</td>
      <td><button class="btn btn-danger btn-sm" onclick="deletePromo(${p.id})">🗑️</button></td>
    </tr>`;
  }).join('');
}

async function createPromo(){
  const data = {
    code: document.getElementById('pm-code').value.toUpperCase(),
    discount_type: document.getElementById('pm-type').value,
    discount_value: parseFloat(document.getElementById('pm-value').value)||0,
    min_sum: parseFloat(document.getElementById('pm-min').value)||0,
    days: parseInt(document.getElementById('pm-days').value)||0,
    max_uses: parseInt(document.getElementById('pm-limit').value)||0
  };
  const r = await api('/admin/api/promo/create', {method:'POST',body:JSON.stringify(data)});
  if(r.ok){ closeModal('promo-modal'); loadPromo(); alert('✅ Promo kod yaratildi!'); }
  else alert('❌ Xatolik: '+r.error);
}

async function deletePromo(id){
  if(!confirm("O’chirishni tasdiqlaysizmi?")) return;
  await api('/admin/api/promo/delete', {method:'POST',body:JSON.stringify({id})});
  loadPromo();
}

// ===== SEARCH =====
async function doSearch(){
  const q = document.getElementById('global-search').value.trim();
  const type = document.getElementById('search-type').value;
  if(!q) return;
  const d = await api(`/admin/api/search?q=${encodeURIComponent(q)}&type=${type}`);
  const div = document.getElementById('search-results');
  let html = '';
  if(d.users&&d.users.length){
    html += `<div class="card"><div class="card-header"><h3>👥 Mijozlar (${d.users.length})</h3></div>
    <div class="scrollable-table"><table><thead><tr><th>ID</th><th>Ism</th><th>Telefon</th><th>TG ID</th><th>Buyurtmalar</th></tr></thead><tbody>
    ${d.users.map(u=>`<tr><td>${u.id}</td><td>${u.full_name}</td><td>${u.phone}</td><td>${u.tg_id}</td><td>${u.order_count}</td></tr>`).join('')}
    </tbody></table></div></div>`;
  }
  if(d.couriers&&d.couriers.length){
    html += `<div class="card"><div class="card-header"><h3>🚚 Kuryerlar (${d.couriers.length})</h3></div>
    <div class="scrollable-table"><table><thead><tr><th>ID</th><th>Ism</th><th>Telefon</th><th>TG ID</th><th>Do’kon</th></tr></thead><tbody>
    ${d.couriers.map(c=>`<tr><td>${c.id}</td><td>${c.full_name}</td><td>${c.phone}</td><td>${c.tg_id}</td><td>${c.shop_name||'—'}</td></tr>`).join('')}
    </tbody></table></div></div>`;
  }
  if(d.shops&&d.shops.length){
    html += `<div class="card"><div class="card-header"><h3>🏪 Do’konlar (${d.shops.length})</h3></div>
    <div class="scrollable-table"><table><thead><tr><th>ID</th><th>Nom</th><th>Telefon</th></tr></thead><tbody>
    ${d.shops.map(s=>`<tr><td>${s.id}</td><td>${s.name}</td><td>${s.phone||'—'}</td></tr>`).join('')}
    </tbody></table></div></div>`;
  }
  if(d.orders&&d.orders.length){
    html += `<div class="card"><div class="card-header"><h3>📦 Buyurtmalar (${d.orders.length})</h3></div>
    <div class="scrollable-table"><table><thead><tr><th>ID</th><th>Do’kon</th><th>Summa</th><th>Holat</th><th>Vaqt</th></tr></thead><tbody>
    ${d.orders.map(o=>`<tr><td>#${o.order_uid}</td><td>${o.shop_name||'—'}</td><td>${fmtNum(o.total_sum)} so’m</td><td>${statusBadge(o.status)}</td><td>${o.created_at}</td></tr>`).join('')}
    </tbody></table></div></div>`;
  }
  if(!html) html = '<div class="card"><div class="empty-state"><div class="empty-icon">🔍</div><p>Hech narsa topilmadi</p></div></div>';
  div.innerHTML = html;
}

// ===== CHATS =====
async function loadChats(){
  const d = await api('/admin/api/chats');
  const list = document.getElementById('chat-list');
  list.innerHTML = (d.chats||[]).map(c=>`
    <div onclick="loadChatDetail(${c.from_tg_id},${c.to_tg_id})"
      style="padding:12px 16px;border-bottom:1px solid var(--border);cursor:pointer;transition:background 0.1s;"
      onmouseover="this.style.background='var(--surface2)'" onmouseout="this.style.background=''">
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <span style="font-size:13px;font-weight:500;">${c.from_tg_id}</span>
        <span style="font-size:10px;color:var(--text2);">${c.chat_type}</span>
      </div>
      <div style="font-size:11px;color:var(--text2);margin-top:2px;">${c.last_msg||''}</div>
      <div style="font-size:10px;color:var(--text2);margin-top:2px;">${c.last_time||''}</div>
    </div>
  `).join('') || '<div class="empty-state"><p>Chat yo’q</p></div>';
}

async function loadChatDetail(from_id, to_id){
  const d = await api(`/admin/api/chat-detail?from=${from_id}&to=${to_id}`);
  const detail = document.getElementById('chat-detail');
  detail.innerHTML = (d.messages||[]).map(m=>`
    <div class="chat-bubble ${m.from_tg_id==from_id?'out':'in'}">
      <div class="chat-meta">${m.from_tg_id} • ${m.created_at}</div>
      <div>${m.message}</div>
    </div>
  `).join('') || '<div class="empty-state"><p>Xabar yo’q</p></div>';
  detail.scrollTop = detail.scrollHeight;
}

// ===== PROBLEMS =====
async function loadProblems(){
  const d = await api('/admin/api/problems');
  const t = document.getElementById('problems-table');
  t.innerHTML = (d.orders||[]).map(o=>{
    const warn = o.wait_min>=10?' <span style="color:var(--danger);font-weight:700;">🔴 URGENT</span>':'';
    return `<tr style="${o.wait_min>=10?'background:rgba(239,68,68,0.05);':''}">
      <td><code>#${o.order_uid}</code></td>
      <td>${o.shop_name||'—'}</td>
      <td>${o.user_name||'Tel buyurtma'}</td>
      <td>${fmtNum(o.total_sum)} so’m</td>
      <td>${o.wait_min} daqiqa${warn}</td>
      <td style="font-size:11px;">${o.created_at}</td>
      <td>${statusBadge(o.status)}</td>
    </tr>`;
  }).join('') || '<tr><td colspan="7" class="empty-state">✅ Muammo yo’q</td></tr>';
}

// ===== BLOCKED =====
async function loadBlocked(){
  const d = await api('/admin/api/blocked');
  const bu = document.getElementById('blocked-users-table');
  bu.innerHTML = (d.users||[]).map(u=>`<tr>
    <td>${u.full_name}</td><td>${u.phone}</td><td>${u.id}</td>
    <td><button class="btn btn-success btn-sm" onclick="toggleUser(${u.tg_id},0)">✅ Ochish</button></td>
  </tr>`).join('') || "<tr><td colspan='4' class='empty-state'>Yo’q</td></tr>";

  const bc = document.getElementById('blocked-couriers-table');
  bc.innerHTML = (d.couriers||[]).map(c=>`<tr>
    <td>${c.full_name}</td><td>${c.phone}</td><td>${c.id}</td>
    <td><button class="btn btn-success btn-sm" onclick="toggleCourier(${c.tg_id},0)">✅ Ochish</button></td>
  </tr>`).join('') || "<tr><td colspan='4' class='empty-state'>Yo’q</td></tr>";
}

// ===== TOP =====
async function loadTop(){
  const d = await api('/admin/api/top');
  const t = document.getElementById('top-table');
  const medals = ['🥇','🥈','🥉'];
  t.innerHTML = (d.users||[]).map((u,i)=>`<tr>
    <td>${medals[i]||i+1}</td>
    <td>${u.full_name||'Noma’lum'}</td>
    <td>${u.phone||'—'}</td>
    <td>${u.order_count}</td>
    <td>${fmtNum(u.total_spent)} so’m</td>
  </tr>`).join('');
}

// ===== WEEKLY =====
async function loadWeekly(){
  const d = await api('/admin/api/weekly');
  const ws = document.getElementById('weekly-stats');
  ws.innerHTML = `
    <div class="stat-card" style="--c1:#00d4aa;--c2:#0ea5e9;">
      <div class="stat-icon">📦</div><div class="stat-value">${d.total_orders}</div>
      <div class="stat-label">Haftalik buyurtmalar</div>
    </div>
    <div class="stat-card" style="--c1:#22c55e;--c2:#00d4aa;">
      <div class="stat-icon">💰</div><div class="stat-value">${fmtNum(d.total_income)} so’m</div>
      <div class="stat-label">Haftalik daromad</div>
    </div>
    <div class="stat-card" style="--c1:#8b5cf6;--c2:#ec4899;">
      <div class="stat-icon">👥</div><div class="stat-value">${d.new_users}</div>
      <div class="stat-label">Yangi mijozlar</div>
    </div>
  `;
  const t = document.getElementById('weekly-table');
  t.innerHTML = (d.days||[]).map(day=>`<tr>
    <td>${day.date}</td>
    <td>${day.orders}</td>
    <td>${fmtNum(day.income)} so’m</td>
    <td>${day.new_users}</td>
  </tr>`).join('');
}

// ===== ADMIN ORDERS =====
async function loadAdminOrders(){
  const d = await api('/admin/api/admin-orders');
  const t = document.getElementById('admin-orders-table');
  t.innerHTML = (d.orders||[]).map(o=>`<tr>
    <td><code>#${o.order_uid}</code></td>
    <td>${o.shop_name||'—'}</td>
    <td style="max-width:140px;overflow:hidden;text-overflow:ellipsis;">${o.address}</td>
    <td style="max-width:140px;overflow:hidden;text-overflow:ellipsis;">${o.products}</td>
    <td>${fmtNum(o.total_sum)} so’m</td>
    <td>${statusBadge(o.status)}</td>
    <td style="font-size:11px;">${o.created_at}</td>
  </tr>`).join('');
}

// MODAL
function openModal(id){ document.getElementById(id).classList.add('open'); }
function closeModal(id){ document.getElementById(id).classList.remove('open'); }
document.querySelectorAll('.modal-overlay').forEach(m=>{
  m.addEventListener('click',e=>{ if(e.target===m) m.classList.remove('open'); });
});

function closeSidebar(){
  document.getElementById('sidebar').classList.remove('open');
  document.getElementById('sidebar-overlay').classList.remove('show');
  document.body.style.overflow = '';
}
function openSidebar(){
  document.getElementById('sidebar').classList.add('open');
  document.getElementById('sidebar-overlay').classList.add('show');
  document.body.style.overflow = 'hidden';
}

document.querySelectorAll('.nav-item').forEach(function(item){
  item.addEventListener('click', function(){
    if(window.innerWidth <= 768) closeSidebar();
  });
});

// AUTO REFRESH monitoring every 30s
setInterval(()=>{
  if(document.getElementById('sec-monitoring').classList.contains('active')) loadMonitoring();
  api('/admin/api/dashboard').then(d=>{ if(d&&!d.error) document.getElementById('pending-badge').textContent=d.pending||0; });
}, 30000);

// INITIAL LOAD
loadDashboard();
</script>
</body>
</html>'''

# ===================== ROUTES =====================
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
        error = "Noto\u02bbg\u02bbri username yoki parol!"
    return render_template_string(LOGIN_HTML, error=error)

@app.route('/admin/api/login-stats')
def api_login_stats():
    """Login sahifasidagi floating card uchun — autentifikatsiya talab qilinmaydi"""
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
    except Exception as e:
        return jsonify({'orders': 0, 'income': 0})

@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect('/admin/login')

@app.route('/admin')
@login_required
def admin_index():
    return render_template_string(DASHBOARD_HTML, username=session.get('admin_username','admin'))

# ===================== API ENDPOINTS =====================
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

        c.execute("""SELECT o.id, o.order_uid, o.total_sum, o.status, o.created_at,
                            s.name as shop_name
                     FROM orders o
                     LEFT JOIN shops s ON o.shop_id=s.id
                     ORDER BY o.id DESC LIMIT 10""")
        recent_orders = [dict(r) for r in c.fetchall()]

        c.execute("""SELECT s.id, s.name, s.is_open, COALESCE(s.rating,0) as rating,
                     COUNT(CASE WHEN o.created_at LIKE %s THEN 1 END) as today_count
                     FROM shops s LEFT JOIN orders o ON s.id=o.shop_id
                     GROUP BY s.id, s.name, s.is_open, s.rating ORDER BY s.name""", (f"{today}%",))
        shops_info = [dict(r) for r in c.fetchall()]
        conn.close()

        return jsonify({
            'users': users, 'shops': shops, 'shops_open': shops_open,
            'couriers': couriers, 'total_orders': total_orders,
            'total_income': float(total_income), 'today_income': float(today_income),
            'pending': pending, 'on_way': on_way,
            'recent_orders': recent_orders, 'shops_info': shops_info
        })
    except Exception as e:
        import traceback
        print("DASHBOARD ERROR:", traceback.format_exc())
        return jsonify({'error': str(e)}), 500

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
        c.execute("SELECT COUNT(*) as cnt FROM couriers WHERE is_busy=0 AND is_blocked=0 AND is_available=1")
        free_couriers = c.fetchone()['cnt']
        c.execute("SELECT COUNT(*) as cnt FROM couriers WHERE is_busy=1 AND is_blocked=0")
        busy_couriers = c.fetchone()['cnt']
        c.execute("SELECT COUNT(*) as cnt FROM shops WHERE is_open=1")
        open_shops = c.fetchone()['cnt']
        one_hour_ago = (datetime.now() - timedelta(hours=1)).strftime("%d.%m.%Y %H:%M")
        c.execute("SELECT COUNT(*) as cnt FROM orders WHERE created_at >= %s", (one_hour_ago,))
        last_hour = c.fetchone()['cnt']

        c.execute("""SELECT o.*, s.name as shop_name, u.full_name as user_name
                     FROM orders o
                     LEFT JOIN shops s ON o.shop_id=s.id
                     LEFT JOIN users u ON o.user_tg_id=u.tg_id
                     WHERE o.status='pending' ORDER BY o.created_at ASC""")
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

        return jsonify({
            'pending': pending, 'on_way': on_way,
            'free_couriers': free_couriers, 'busy_couriers': busy_couriers,
            'open_shops': open_shops, 'last_hour': last_hour,
            'pending_orders': pending_orders,
            'free_couriers_list': free_couriers_list
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/api/orders')
@login_required
def api_orders():
    try:
        status = request.args.get('status','')
        search = request.args.get('search','')
        conn = get_db()
        c = conn.cursor()
        sql = """SELECT o.*, s.name as shop_name,
                        u.full_name as user_name, u.phone as user_phone,
                        cu.full_name as courier_name
                 FROM orders o
                 LEFT JOIN shops s ON o.shop_id=s.id
                 LEFT JOIN users u ON o.user_tg_id=u.tg_id
                 LEFT JOIN couriers cu ON o.courier_tg_id=cu.tg_id
                 WHERE 1=1"""
        params = []
        if status:
            sql += " AND o.status=%s"; params.append(status)
        if search:
            sql += " AND (o.order_uid ILIKE %s OR o.address ILIKE %s OR u.full_name ILIKE %s)"
            params += [f"%{search}%"]*3
        sql += " ORDER BY o.created_at DESC LIMIT 100"
        c.execute(sql, params)
        orders = [dict(r) for r in c.fetchall()]
        c.execute("SELECT COUNT(*) as cnt FROM orders")
        total = c.fetchone()['cnt']
        conn.close()
        return jsonify({'orders': orders, 'total': len(orders)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/api/users')
@login_required
def api_users():
    try:
        search = request.args.get('search','')
        conn = get_db()
        c = conn.cursor()
        sql = """SELECT u.id, u.tg_id, u.username, u.full_name, u.phone, u.registered_at, u.is_blocked,
                        COUNT(o.id) as order_count,
                        COALESCE(SUM(CASE WHEN o.status='delivered' THEN o.total_sum ELSE 0 END),0) as total_spent
                 FROM users u LEFT JOIN orders o ON u.tg_id=o.user_tg_id
                 WHERE 1=1"""
        params = []
        if search:
            sql += " AND (u.full_name ILIKE %s OR u.phone ILIKE %s OR CAST(u.id AS TEXT) ILIKE %s OR CAST(u.tg_id AS TEXT) ILIKE %s)"
            params += [f"%{search}%"]*4
        sql += " GROUP BY u.id, u.tg_id, u.username, u.full_name, u.phone, u.registered_at, u.is_blocked ORDER BY order_count DESC"
        c.execute(sql, params)
        users = [dict(r) for r in c.fetchall()]
        conn.close()
        return jsonify({'users': users, 'total': len(users)})
    except Exception as e:
        import traceback
        print("USERS ERROR:", traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/admin/api/user/block', methods=['POST'])
@login_required
def api_user_block():
    try:
        data = request.json
        db_query("UPDATE users SET is_blocked=%s WHERE tg_id=%s",
                 (data['block'], data['tg_id']), commit=True)
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/api/couriers')
@login_required
def api_couriers():
    try:
        search = request.args.get('search','')
        conn = get_db()
        c = conn.cursor()
        sql = """SELECT cu.*, s.name as shop_name,
                        COUNT(o.id) as delivered_count
                 FROM couriers cu
                 LEFT JOIN shops s ON cu.shop_id=s.id
                 LEFT JOIN orders o ON cu.tg_id=o.courier_tg_id AND o.status='delivered'
                 WHERE 1=1"""
        params = []
        if search:
            sql += " AND (cu.full_name ILIKE %s OR cu.phone ILIKE %s OR CAST(cu.tg_id AS TEXT) ILIKE %s)"
            params += [f"%{search}%"]*3
        sql += " GROUP BY cu.id,cu.tg_id,cu.full_name,cu.phone,cu.shop_id,cu.is_busy,cu.is_blocked,cu.is_available,cu.queue_order,cu.registered_at,s.name ORDER BY delivered_count DESC"
        c.execute(sql, params)
        couriers = [dict(r) for r in c.fetchall()]
        conn.close()
        return jsonify({'couriers': couriers, 'total': len(couriers)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/api/courier/block', methods=['POST'])
@login_required
def api_courier_block():
    try:
        data = request.json
        db_query("UPDATE couriers SET is_blocked=%s WHERE tg_id=%s",
                 (data['block'], data['tg_id']), commit=True)
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/api/courier/delete', methods=['POST'])
@login_required
def api_courier_delete():
    try:
        data = request.json
        db_query("DELETE FROM couriers WHERE tg_id=%s", (data['tg_id'],), commit=True)
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/api/shops')
@login_required
def api_shops():
    try:
        search = request.args.get('search','')
        conn = get_db()
        c = conn.cursor()
        sql = """SELECT s.id, s.owner_tg_id, s.name, s.phone, s.card_number, s.work_time,
                        s.is_open, COALESCE(s.rating,0) as rating, 
                        COALESCE(s.rating_count,0) as rating_count, 
                        s.admin_percent, s.created_at,
                        COUNT(o.id) as order_count,
                        COALESCE(SUM(CASE WHEN o.status='delivered' THEN o.total_sum ELSE 0 END),0) as total_income
                 FROM shops s LEFT JOIN orders o ON s.id=o.shop_id
                 WHERE 1=1"""
        params = []
        if search:
            sql += " AND (s.name ILIKE %s OR CAST(s.id AS TEXT) ILIKE %s)"
            params += [f"%{search}%"]*2
        sql += " GROUP BY s.id, s.owner_tg_id, s.name, s.phone, s.card_number, s.work_time, s.is_open, s.rating, s.rating_count, s.admin_percent, s.created_at ORDER BY total_income DESC"
        c.execute(sql, params)
        shops = [dict(r) for r in c.fetchall()]
        conn.close()
        return jsonify({'shops': shops})
    except Exception as e:
        import traceback
        print("SHOPS ERROR:", traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/admin/api/finance')
@login_required
def api_finance():
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT COALESCE(SUM(total_sum),0) as t FROM orders WHERE payment_type='Naqd' AND status='delivered'")
        cash_total = c.fetchone()['t']
        c.execute("SELECT COALESCE(SUM(total_sum),0) as t FROM orders WHERE payment_type='Karta' AND status='delivered'")
        card_total = c.fetchone()['t']
        c.execute("SELECT COALESCE(SUM(total_sum),0) as t FROM orders WHERE status='delivered'")
        total = c.fetchone()['t']
        c.execute("""SELECT s.name, s.admin_percent, COUNT(o.id) as order_count,
                            COALESCE(SUM(CASE WHEN o.status='delivered' THEN o.total_sum ELSE 0 END),0) as total_income
                     FROM shops s LEFT JOIN orders o ON s.id=o.shop_id
                     GROUP BY s.id,s.name,s.admin_percent ORDER BY total_income DESC""")
        shops = [dict(r) for r in c.fetchall()]
        conn.close()
        admin_share = sum(float(s['total_income'])*float(s['admin_percent'])/100 for s in shops)
        return jsonify({
            'cash_total': float(cash_total), 'card_total': float(card_total),
            'total': float(total), 'admin_share': admin_share,
            'shops': shops
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/api/promo')
@login_required
def api_promo():
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM promo_codes ORDER BY created_at DESC")
        promos = [dict(r) for r in c.fetchall()]
        conn.close()
        return jsonify({'promos': promos})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/api/promo/create', methods=['POST'])
@login_required
def api_promo_create():
    try:
        import random
        data = request.json
        expires_at = None
        if data.get('days', 0) > 0:
            exp = datetime.now() + timedelta(days=data['days'])
            expires_at = exp.strftime("%d.%m.%Y")
        uid = random.randint(100000, 999999)
        now_str = datetime.now().strftime("%d.%m.%Y %H:%M")
        db_query("""INSERT INTO promo_codes (id,code,discount_type,discount_value,min_sum,days,max_uses,created_at,expires_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                 (uid, data['code'], data['discount_type'], data['discount_value'],
                  data.get('min_sum',0), data.get('days',0), data.get('max_uses',0),
                  now_str, expires_at), commit=True)
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})

@app.route('/admin/api/promo/delete', methods=['POST'])
@login_required
def api_promo_delete():
    try:
        data = request.json
        db_query("DELETE FROM promo_codes WHERE id=%s", (data['id'],), commit=True)
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
            c.execute("""SELECT u.*, COUNT(o.id) as order_count FROM users u
                         LEFT JOIN orders o ON u.tg_id=o.user_tg_id
                         WHERE u.full_name ILIKE %s OR u.phone ILIKE %s
                               OR CAST(u.id AS TEXT) ILIKE %s OR CAST(u.tg_id AS TEXT) ILIKE %s
                         GROUP BY u.id,u.tg_id,u.username,u.full_name,u.phone,u.registered_at,u.is_blocked
                         LIMIT 20""", [f"%{q}%"]*4)
            result['users'] = [dict(r) for r in c.fetchall()]
        if stype in ('all','couriers'):
            c.execute("""SELECT cu.*, s.name as shop_name FROM couriers cu
                         LEFT JOIN shops s ON cu.shop_id=s.id
                         WHERE cu.full_name ILIKE %s OR cu.phone ILIKE %s OR CAST(cu.tg_id AS TEXT) ILIKE %s
                         LIMIT 20""", [f"%{q}%"]*3)
            result['couriers'] = [dict(r) for r in c.fetchall()]
        if stype in ('all','shops'):
            c.execute("SELECT * FROM shops WHERE name ILIKE %s OR CAST(id AS TEXT) ILIKE %s LIMIT 20",
                      [f"%{q}%"]*2)
            result['shops'] = [dict(r) for r in c.fetchall()]
        if stype in ('all','orders'):
            c.execute("""SELECT o.*, s.name as shop_name FROM orders o
                         LEFT JOIN shops s ON o.shop_id=s.id
                         WHERE o.order_uid ILIKE %s OR o.address ILIKE %s LIMIT 20""",
                      [f"%{q}%"]*2)
            result['orders'] = [dict(r) for r in c.fetchall()]
        conn.close()
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
        return jsonify({'error': str(e)}), 500

@app.route('/admin/api/chat-detail')
@login_required
def api_chat_detail():
    try:
        from_id = request.args.get('from')
        to_id = request.args.get('to')
        conn = get_db()
        c = conn.cursor()
        c.execute("""SELECT * FROM chats
                     WHERE (from_tg_id=%s AND to_tg_id=%s) OR (from_tg_id=%s AND to_tg_id=%s)
                     ORDER BY created_at ASC LIMIT 50""",
                  (from_id, to_id, to_id, from_id))
        messages = [dict(r) for r in c.fetchall()]
        conn.close()
        return jsonify({'messages': messages})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/api/problems')
@login_required
def api_problems():
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("""SELECT o.*, s.name as shop_name, u.full_name as user_name
                     FROM orders o
                     LEFT JOIN shops s ON o.shop_id=s.id
                     LEFT JOIN users u ON o.user_tg_id=u.tg_id
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
        return jsonify({'error': str(e)}), 500

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
        return jsonify({'users': users, 'couriers': couriers})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/api/top')
@login_required
def api_top():
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("""SELECT o.user_tg_id, u.full_name, u.phone,
                            COUNT(o.id) as order_count,
                            COALESCE(SUM(o.total_sum),0) as total_spent
                     FROM orders o LEFT JOIN users u ON u.tg_id=o.user_tg_id
                     WHERE o.status='delivered'
                     GROUP BY o.user_tg_id,u.full_name,u.phone
                     ORDER BY order_count DESC LIMIT 20""")
        users = [dict(r) for r in c.fetchall()]
        conn.close()
        return jsonify({'users': users})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
            days.append({'date':d, 'orders':row['cnt'], 'income':float(row['income']), 'new_users':nu})
        conn.close()
        return jsonify({'total_orders':total_orders,'total_income':float(total_income),'new_users':new_users,'days':days})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/api/admin-orders')
@login_required
def api_admin_orders():
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("""SELECT o.*, s.name as shop_name FROM orders o
                     LEFT JOIN shops s ON o.shop_id=s.id
                     WHERE o.source='admin' OR o.user_tg_id=0
                     ORDER BY o.created_at DESC LIMIT 50""")
        orders = [dict(r) for r in c.fetchall()]
        conn.close()
        return jsonify({'orders': orders})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ===================== RUN (standalone) =====================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
