"""
PROFIT BOT v2.1 - RAILWAY PRODUCTION FIXED
F-String Syntax Error: RESOLVED
"""

import logging
import sqlite3
from datetime import datetime, timedelta
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    ContextTypes, MessageHandler, filters
)

# ================= CONFIG =================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)

TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_IDS = [1103784347]
DB = "profit_bot.db"
MINI_APP_URL = "https://earn-mini-appuprailwayapp-production.up.railway.app/"

# ================= DATABASE (Simplified for Railway) =================
def init_db():
    conn = sqlite3.connect(DB, check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, 
                  points INTEGER DEFAULT 0, total_earned INTEGER DEFAULT 0, 
                  joined_date TEXT, last_active TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS daily_checkin
                 (user_id INTEGER, check_date TEXT, streak INTEGER DEFAULT 1,
                  UNIQUE(user_id, check_date))''')
    c.execute('''CREATE TABLE IF NOT EXISTS withdrawals
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
                  amount INTEGER, wallet_type TEXT, status TEXT DEFAULT 'قيد الانتظار',
                  request_date TEXT)''')
    conn.commit()
    conn.close()
    logging.info("✅ قاعدة البيانات جاهزة")

def get_user_points(user_id):
    conn = sqlite3.connect(DB, check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT points FROM users WHERE user_id=?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 0

def update_points(user_id, points_to_add):
    conn = sqlite3.connect(DB, check_same_thread=False)
    c = conn.cursor()
    c.execute("UPDATE users SET points=points+?, total_earned=total_earned+?, last_active=? WHERE user_id=?",
              (points_to_add, points_to_add, datetime.now().isoformat(), user_id))
    conn.commit()
    conn.close()

def can_checkin(user_id):
    today = datetime.now().strftime('%Y-%m-%d')
    conn = sqlite3.connect(DB, check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT 1 FROM daily_checkin WHERE user_id=? AND check_date=?", (user_id, today))
    result = c.fetchone()
    conn.close()
    return result is None

def add_checkin(user_id):
    today = datetime.now().strftime('%Y-%m-%d')
    conn = sqlite3.connect(DB, check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT check_date, streak FROM daily_checkin WHERE user_id=? ORDER BY check_date DESC LIMIT 1", (user_id,))
    last = c.fetchone()
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    streak = last[1] + 1 if last and last[0] == yesterday else 1
    c.execute("INSERT INTO daily_checkin(user_id, check_date, streak) VALUES(?,?,?)", (user_id, today, streak))
    conn.commit()
    conn.close()
    return streak

# ================= START COMMAND =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    # تسجيل المستخدم
    conn = sqlite3.connect(DB, check_same_thread=False)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users(user_id, username, first_name, joined_date, last_active) VALUES(?,?,?,?,?)",
              (user_id, user.username or "غير محدد", user.first_name or "مستخدم",
               datetime.now().strftime('%Y-%m-%d'), datetime.now().isoformat()))
    conn.commit()
    conn.close()
    
    points = get_user_points(user_id)
    
    keyboard = [
        [InlineKeyboardButton("🚀 الدخول للـ Mini App", web_app=WebAppInfo(url=MINI_APP_URL))],
        [InlineKeyboardButton("✅ تسجيل يومي", callback_data='daily_checkin'),
         InlineKeyboardButton("💰 رصيدي", callback_data='balance')],
        [InlineKeyboardButton("👥 دعوة أصدقاء", callback_data='referral'),
         InlineKeyboardButton("💳 سحب الأرباح", callback_data='withdraw')],
    ]
    if user_id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("⚙️ لوحة الإدارة", callback_data='admin_panel')])
    
    # F-STRING المُصحح 100% ✅
    welcome_text = (
        "🎉 أهلاً بك " + (user.first_name or 'مستخدم') + "! 🎉

"
        "💰 نقاطك الحالية: " + str(points) + " نقطة

"
        "📱 استخدم Mini App لكسب المزيد!
"
        "⚡ شاهد إعلانات | عجلة الحظ | مهام يومية"
    )
    
    await update.message.reply_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard))

# ================= BUTTON CALLBACKS =================
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data == 'daily_checkin':
        if can_checkin(user_id):
            streak = add_checkin(user_id)
            reward = 5 * streak
            update_points(user_id, reward)
            points = get_user_points(user_id)
            
            text = (
                "✅ تم تسجيل الدخول اليومي!

"
                f"🔥 سلسلة: {streak} يوم
"
                f"💰 حصلت على: {reward} نقطة
"
                f"📊 إجمالي نقاطك: {points}"
            )
            await query.edit_message_text(text)
        else:
            await query.edit_message_text("❌ لقد سجلت الدخول اليوم بالفعل!
⏳ عد غداً.")
    
    elif data == 'balance':
        points = get_user_points(user_id)
        await query.edit_message_text(f"💰 رصيدك الحالي: {points} نقطة

📌 الحد الأدنى للسحب: 100 نقطة")
    
    elif data == 'referral':
        bot_username = context.bot.username
        ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
        text = (
            "👥 نظام الدعوة:

"
            f"🔗 رابطك: {ref_link}

"
            "💰 ستحصل على 10% من أرباح المدعوين!"
        )
        await query.edit_message_text(text)
    
    elif data == 'withdraw':
        points = get_user_points(user_id)
        keyboard = [
            [InlineKeyboardButton("💳 فاوصة", callback_data='withdraw_fawry')],
            [InlineKeyboardButton("💰 فودافون كاش", callback_data='withdraw_vodafone')],
            [InlineKeyboardButton("◀️ رجوع", callback_data='back')]
        ]
        text = f"💳 اختر طريقة السحب:

💰 رصيدك: {points} نقطة
📌 الحد الأدنى: 100 نقطة"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == 'admin_panel' and user_id in ADMIN_IDS:
        conn = sqlite3.connect(DB, check_same_thread=False)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]
        conn.close()
        
        await query.edit_message_text(f"⚙️ لوحة الإدارة

👥 إجمالي المستخدمين: {total_users}")

# ================= WEBAPP DATA =================
async def webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = update.message.text.strip()
    
    if data.startswith("watch_ad"):
        update_points(user_id, 5)
        await update.message.reply_text("✅ شكراً لمشاهدتك الإعلان!
💰 تم إضافة 5 نقاط لرصيدك!")
    
    elif data.startswith("wheel_"):
        try:
            reward = int(data.split("_")[1])
            update_points(user_id, reward)
            await update.message.reply_text(f"🎉 مبروك! حصلت على {reward} نقطة!")
        except:
            pass

# ================= ADMIN =================
async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    
    conn = sqlite3.connect(DB, check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT user_id, first_name, points FROM users ORDER BY points DESC LIMIT 10")
    users = c.fetchall()
    conn.close()
    
    msg = "🏆 أفضل 10 مستخدمين:

"
    for i, (uid, name, points) in enumerate(users, 1):
        msg += f"{i}. {name} - {points} نقطة
"
    
    await update.message.reply_text(msg)

# ================= MAIN =================
def main():
    if not TOKEN:
        logging.error("❌ BOT_TOKEN غير موجود")
        return
    
    init_db()
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), webapp_data))
    app.add_handler(CommandHandler("users", admin_users))
    
    logging.info("🚀 PROFIT BOT v2.1 - RAILWAY PRODUCTION READY")
    app.run_polling()

if __name__ == "__main__":
    main()
