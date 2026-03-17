import logging
import sqlite3
from datetime import datetime, timedelta
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_IDS = [1103784347]
DB = "profit_bot.db"
MINI_APP_URL = "https://earn-mini-appuprailwayapp-production.up.railway.app/"

def init_db():
    conn = sqlite3.connect(DB, check_same_thread=False)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, points INTEGER DEFAULT 0, total_earned INTEGER DEFAULT 0, joined_date TEXT, last_active TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS daily_checkin (user_id INTEGER, check_date TEXT, streak INTEGER DEFAULT 1, UNIQUE(user_id, check_date))')
    c.execute('CREATE TABLE IF NOT EXISTS withdrawals (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount INTEGER, wallet_type TEXT, status TEXT DEFAULT "قيد الانتظار", request_date TEXT)')
    conn.commit()
    conn.close()

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
    c.execute("UPDATE users SET points=points+?, total_earned=total_earned+?, last_active=? WHERE user_id=?", (points_to_add, points_to_add, datetime.now().isoformat(), user_id))
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    conn = sqlite3.connect(DB, check_same_thread=False)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users(user_id, username, first_name, joined_date, last_active) VALUES(?,?,?,?,?)", (user_id, user.username or "غير محدد", user.first_name or "مستخدم", datetime.now().strftime('%Y-%m-%d'), datetime.now().isoformat()))
    conn.commit()
    conn.close()
    
    points = get_user_points(user_id)
    
    text1 = "🎉 اهلا بك "
    text2 = user.first_name or "مستخدم"
    text3 = "! 🎉"
    welcome_text = text1 + text2 + text3 + "

"
    welcome_text = welcome_text + "💰 نقاطك الحالية: " + str(points) + " نقطة

"
    welcome_text = welcome_text + "📱 استخدم Mini App لكسب المزيد!"
    
    keyboard = [
        [InlineKeyboardButton("🚀 الدخول للـ Mini App", web_app=WebAppInfo(url=MINI_APP_URL))],
        [InlineKeyboardButton("✅ تسجيل يومي", callback_data='daily_checkin'), InlineKeyboardButton("💰 رصيدي", callback_data='balance')],
        [InlineKeyboardButton("👥 دعوة أصدقاء", callback_data='referral'), InlineKeyboardButton("💳 سحب الأرباح", callback_data='withdraw')]
    ]
    if user_id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("⚙️ لوحة الإدارة", callback_data='admin_panel')])
    
    await update.message.reply_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard))

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
            text = "✅ تم تسجيل الدخول اليومي!

🔥 سلسلة: "
            text = text + str(streak) + " يوم
💰 حصلت على: "
            text = text + str(reward) + " نقطة
📊 إجمالي نقاطك: "
            text = text + str(points)
            await query.edit_message_text(text)
        else:
            await query.edit_message_text("❌ لقد سجلت الدخول اليوم بالفعل! ⏳ عد غداً.")
    
    elif data == 'balance':
        points = get_user_points(user_id)
        text = "💰 رصيدك الحالي: " + str(points) + " نقطة"
        text = text + "

📌 الحد الأدنى للسحب: 100 نقطة"
        await query.edit_message_text(text)
    
    elif data == 'referral':
        bot_username = context.bot.username
        ref_link = "https://t.me/" + bot_username + "?start=ref_" + str(user_id)
        text = "👥 نظام الدعوة:

🔗 رابطك: " + ref_link
        text = text + "

💰 ستحصل على 10% من أرباح المدعوين!"
        await query.edit_message_text(text)
    
    elif data == 'withdraw':
        points = get_user_points(user_id)
        text = "💳 اختر طريقة السحب:

💰 رصيدك: "
        text = text + str(points) + " نقطة
📌 الحد الأدنى: 100 نقطة"
        keyboard = [
            [InlineKeyboardButton("💳 فاوصة", callback_data='withdraw_fawry')],
            [InlineKeyboardButton("💰 فودافون كاش", callback_data='withdraw_vodafone')],
            [InlineKeyboardButton("◀️ رجوع", callback_data='back')]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = update.message.text.strip()
    
    if data.startswith("watch_ad"):
        update_points(user_id, 5)
        await update.message.reply_text("✅ شكراً لمشاهدتك الإعلان! 💰 تم إضافة 5 نقاط لرصيدك!")
    
    elif data.startswith("wheel_"):
        try:
            reward = int(data.split("_")[1])
            update_points(user_id, reward)
            msg = "🎉 مبروك! حصلت على " + str(reward) + " نقطة!"
            await update.message.reply_text(msg)
        except:
            pass

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
        msg = msg + str(i) + ". " + str(name) + " - " + str(points) + " نقطة
"
    await update.message.reply_text(msg)

def main():
    if not TOKEN:
        print("❌ BOT_TOKEN غير موجود")
        return
    init_db()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), webapp_data))
    app.add_handler(CommandHandler("users", admin_users))
    print("🚀 PROFIT BOT v3.0 - RAILWAY BULLETPROOF")
    app.run_polling()

if __name__ == "__main__":
    main()
