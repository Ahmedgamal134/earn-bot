import logging
import sqlite3
from datetime import datetime, timedelta
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# إعداد التسجيل
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_IDS = [1103784347]  # ضع معرفك هنا

DB = "profit_bot.db"

# ================== قاعدة البيانات ==================
def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY,
                  username TEXT,
                  first_name TEXT,
                  points INTEGER DEFAULT 0,
                  total_earned INTEGER DEFAULT 0,
                  joined_date TEXT,
                  referrer_id INTEGER DEFAULT NULL,
                  total_referrals INTEGER DEFAULT 0,
                  referral_earned INTEGER DEFAULT 0,
                  is_banned INTEGER DEFAULT 0,
                  last_active TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS ads
                 (user_id INTEGER,
                  ad_date TEXT,
                  ad_count INTEGER DEFAULT 0,
                  UNIQUE(user_id, ad_date))''')
    c.execute('''CREATE TABLE IF NOT EXISTS daily_checkin
                 (user_id INTEGER,
                  check_date TEXT,
                  streak INTEGER DEFAULT 1,
                  UNIQUE(user_id, check_date))''')
    c.execute('''CREATE TABLE IF NOT EXISTS withdrawals
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  amount INTEGER,
                  wallet_type TEXT,
                  status TEXT DEFAULT 'قيد الانتظار',
                  request_date TEXT)''')
    conn.commit()
    conn.close()
    print("✅ قاعدة البيانات جاهزة")

# ================== دوال مساعدة ==================
def get_user(user_id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def get_user_points(user_id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT points FROM users WHERE user_id=?", (user_id,))
    res = c.fetchone()
    conn.close()
    return res[0] if res else 0

def update_points(user_id, points_to_add):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("UPDATE users SET points=points+?, total_earned=total_earned+? WHERE user_id=?",
              (points_to_add, points_to_add, user_id))
    conn.commit()
    conn.close()

def add_ad_watch(user_id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')
    c.execute("SELECT ad_count FROM ads WHERE user_id=? AND ad_date=?", (user_id, today))
    res = c.fetchone()
    if not res:
        c.execute("INSERT INTO ads(user_id, ad_date, ad_count) VALUES(?,?,1)", (user_id, today))
    else:
        c.execute("UPDATE ads SET ad_count=ad_count+1 WHERE user_id=? AND ad_date=?", (user_id, today))
    conn.commit()
    conn.close()

def can_checkin(user_id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')
    c.execute("SELECT * FROM daily_checkin WHERE user_id=? AND check_date=?", (user_id, today))
    res = c.fetchone()
    conn.close()
    return res is None

def add_checkin(user_id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')
    c.execute("SELECT check_date, streak FROM daily_checkin WHERE user_id=? ORDER BY check_date DESC LIMIT 1", (user_id,))
    last = c.fetchone()
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    streak = last[1]+1 if last and last[0]==yesterday else 1
    c.execute("INSERT INTO daily_checkin(user_id, check_date, streak) VALUES(?,?,?)", (user_id, today, streak))
    conn.commit()
    conn.close()
    return streak

def get_total_users():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    total = c.fetchone()[0]
    conn.close()
    return total

# ================== أوامر البوت ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    username = user.username or "لا يوجد"
    first_name = user.first_name or "مستخدم"
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users(user_id, username, first_name, joined_date) VALUES(?,?,?,?)",
              (user_id, username, first_name, datetime.now().strftime('%Y-%m-%d')))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"🎉 مرحباً {first_name}!\n💰 نقاطك الحالية: {get_user_points(user_id)}\n📺 شاهد الإعلانات لكسب النقاط.")

# ================== WebApp Data ==================
async def webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = update.message.text
    if data.startswith("watch_ad"):
        add_ad_watch(user_id)
        update_points(user_id, 3)  # النقاط بعد 15 ثانية من Mini App
    elif data.startswith("wheel_"):
        reward = int(data.split("_")[1])
        update_points(user_id, reward)
    elif data=="checkin":
        streak = add_checkin(user_id)
        update_points(user_id, 5)
    elif data.startswith("withdraw_"):
        _, wallet, amount = data.split("_")
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute("INSERT INTO withdrawals(user_id, amount, wallet_type, request_date) VALUES(?,?,?,?)",
                  (user_id, int(amount), wallet, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"💳 طلب السحب إلى {wallet} بمقدار {amount} نقطة")

# ================== إدارة الأدمن ==================
async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    conn = sqlite3.connect(DB);c=conn.cursor()
    c.execute("SELECT user_id, first_name, points FROM users ORDER BY points DESC")
    users = c.fetchall();conn.close()
    msg="👥 المستخدمون:\n"
    for u in users[:20]: msg+=f"👤 {u[1]}: {u[2]} نقطة\n"
    await update.message.reply_text(msg)

# ================== تشغيل البوت ==================
def main():
    if not TOKEN:
        print("❌ التوكن غير موجود")
        return
    init_db()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), webapp_data))
    app.add_handler(CommandHandler("users", admin_users))
    print("✅ البوت جاهز للعمل...")
    app.run_polling()

if __name__ == "__main__":
    main()
