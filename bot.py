import logging
import sqlite3
from datetime import datetime, timedelta
import os
import asyncio
import csv
from io import StringIO
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# إعداد التسجيل
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# التوكن من المتغيرات البيئية
TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_IDS = [1103784347]  # ⚠️ غير الرقم ده لمعرفك من @userinfobot

# =========== قاعدة البيانات ===========
def init_db():
    conn = sqlite3.connect('profit_bot.db')
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
                  amount REAL,
                  wallet_type TEXT,
                  wallet_number TEXT,
                  status TEXT DEFAULT 'قيد الانتظار',
                  request_date TEXT)''')
    conn.commit()
    conn.close()
    print("✅ تم إنشاء قاعدة البيانات")

# =========== دوال مساعدة ===========
def get_user(user_id):
    conn = sqlite3.connect('profit_bot.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def get_user_points(user_id):
    conn = sqlite3.connect('profit_bot.db')
    c = conn.cursor()
    c.execute("SELECT points FROM users WHERE user_id=?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 0

def update_points(user_id, points_to_add):
    conn = sqlite3.connect('profit_bot.db')
    c = conn.cursor()
    c.execute("UPDATE users SET points = points + ?, total_earned = total_earned + ? WHERE user_id=?", 
              (points_to_add, points_to_add, user_id))
    conn.commit()
    conn.close()

def get_ads_today(user_id):
    conn = sqlite3.connect('profit_bot.db')
    c = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')
    c.execute("SELECT ad_count FROM ads WHERE user_id=? AND ad_date=?", (user_id, today))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 0

def add_ad_watch(user_id):
    conn = sqlite3.connect('profit_bot.db')
    c = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')
    c.execute("SELECT ad_count FROM ads WHERE user_id=? AND ad_date=?", (user_id, today))
    result = c.fetchone()
    if not result:
        c.execute("INSERT INTO ads (user_id, ad_date, ad_count) VALUES (?, ?, ?)", (user_id, today, 1))
    else:
        c.execute("UPDATE ads SET ad_count = ad_count + 1 WHERE user_id=? AND ad_date=?", (user_id, today))
    conn.commit()
    conn.close()

def can_checkin(user_id):
    conn = sqlite3.connect('profit_bot.db')
    c = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')
    c.execute("SELECT * FROM daily_checkin WHERE user_id=? AND check_date=?", (user_id, today))
    result = c.fetchone()
    conn.close()
    return result is None

def add_checkin(user_id):
    conn = sqlite3.connect('profit_bot.db')
    c = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')
    c.execute('''SELECT check_date, streak FROM daily_checkin 
                 WHERE user_id=? ORDER BY check_date DESC LIMIT 1''', (user_id,))
    last = c.fetchone()
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    if last and last[0] == yesterday:
        streak = last[1] + 1
    else:
        streak = 1
    c.execute("INSERT INTO daily_checkin (user_id, check_date, streak) VALUES (?, ?, ?)",
              (user_id, today, streak))
    conn.commit()
    conn.close()
    return streak

def get_total_users():
    conn = sqlite3.connect('profit_bot.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    return c.fetchone()[0]

def get_all_users():
    conn = sqlite3.connect('profit_bot.db')
    c = conn.cursor()
    c.execute("SELECT user_id, first_name, points, total_earned, joined_date FROM users ORDER BY points DESC")
    return c.fetchall()

# =========== أوامر المستخدمين ===========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    username = user.username or "لا يوجد"
    first_name = user.first_name or "مستخدم"
    
    conn = sqlite3.connect('profit_bot.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, username, first_name, joined_date) VALUES (?, ?, ?, ?)",
              (user_id, username, first_name, datetime.now().strftime('%Y-%m-%d')))
    conn.commit()
    conn.close()
    
    points = get_user_points(user_id)
    ads_today = get_ads_today(user_id)
    
    keyboard = [
        [InlineKeyboardButton("📺 مشاهدة إعلان", callback_data='watch_ad')],
        [InlineKeyboardButton("✅ تسجيل يومي", callback_data='daily_checkin'),
         InlineKeyboardButton("💰 رصيدي", callback_data='balance')],
        [InlineKeyboardButton("👥 دعوة أصدقاء", callback_data='refer'),
         InlineKeyboardButton("💳 سحب أرباح", callback_data='withdraw')],
    ]
    
    if user_id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("⚙️ لوحة التحكم", callback_data='admin_panel')])
    
    await update.message.reply_text(
        f"🎉 أهلاً بك يا {first_name}!\n\n"
        f"💰 رصيدك: {points} نقطة\n"
        f"📺 إعلانات اليوم: {ads_today}/400",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def watch_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    site_url = "https://t.me/YourTapEarnBot/Earn_App"
    keyboard = [
        [InlineKeyboardButton("🌐 شاهد الإعلان", url=site_url)],
        [InlineKeyboardButton("✅ تمت المشاهدة", callback_data='ad_watched')]
    ]
    await query.edit_message_text("📺 اختر الإعلان:", reply_markup=InlineKeyboardMarkup(keyboard))

async def ad_watched(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    await query.edit_message_text("⏳ انتظر 15 ثانية...")
    await asyncio.sleep(15)
    add_ad_watch(user_id)
    update_points(user_id, 1)
    await query.edit_message_text("✅ +1 نقطة! استمر في الكسب.")

async def daily_checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if not can_checkin(user_id):
        await query.edit_message_text("✅ لقد سجلت حضورك اليوم بالفعل!")
        return
    streak = add_checkin(user_id)
    update_points(user_id, 5)
    await query.edit_message_text(f"✅ تم التسجيل! +5 نقاط (سلسلة: {streak})")

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    points = get_user_points(user_id)
    await query.edit_message_text(f"💰 رصيدك الحالي: {points} نقطة")

async def refer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    bot_username = (await context.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start={user_id}"
    await query.edit_message_text(f"👥 رابط دعوتك:\n{link}")

async def withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("💳 سيتم إضافة السحب قريبًا...")

# =========== أوامر الأدمن ===========
async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    users = get_all_users()
    text = "👥 **المستخدمون:**\n\n"
    for u in users[:10]:
        text += f"👤 {u[1]}: {u[2]} نقطة\n"
    await update.message.reply_text(text)

async def admin_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    try:
        user_id = int(context.args[0])
        user = get_user(user_id)
        if user:
            await update.message.reply_text(f"👤 {user[2]}: {user[3]} نقطة")
        else:
            await update.message.reply_text("❌ غير موجود")
    except:
        await update.message.reply_text("❌ استخدم: /search [المعرف]")

async def admin_addpoints(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    try:
        user_id = int(context.args[0])
        points = int(context.args[1])
        update_points(user_id, points)
        await update.message.reply_text(f"✅ تم إضافة {points} نقاط")
    except:
        await update.message.reply_text("❌ استخدم: /addpoints [المعرف] [النقاط]")

async def admin_removepoints(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    try:
        user_id = int(context.args[0])
        points = int(context.args[1])
        update_points(user_id, -points)
        await update.message.reply_text(f"✅ تم خصم {points} نقاط")
    except:
        await update.message.reply_text("❌ استخدم: /removepoints [المعرف] [النقاط]")

async def admin_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    try:
        user_id = int(context.args[0])
        conn = sqlite3.connect('profit_bot.db')
        c = conn.cursor()
        c.execute("UPDATE users SET is_banned=1 WHERE user_id=?", (user_id,))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"✅ تم حظر {user_id}")
    except:
        await update.message.reply_text("❌ خطأ")

async def admin_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    try:
        user_id = int(context.args[0])
        conn = sqlite3.connect('profit_bot.db')
        c = conn.cursor()
        c.execute("UPDATE users SET is_banned=0 WHERE user_id=?", (user_id,))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"✅ تم فك الحظر عن {user_id}")
    except:
        await update.message.reply_text("❌ خطأ")

async def admin_export(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    users = get_all_users()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'الاسم', 'النقاط', 'الإجمالي', 'تاريخ التسجيل'])
    for u in users:
        writer.writerow([u[0], u[1], u[2], u[3], u[4][:10]])
    await update.message.reply_document(document=output.getvalue().encode(), filename='users.csv')

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    total = get_total_users()
    conn = sqlite3.connect('profit_bot.db')
    c = conn.cursor()
    c.execute("SELECT SUM(points) FROM users")
    points = c.fetchone()[0] or 0
    conn.close()
    await update.message.reply_text(f"📊 إجمالي المستخدمين: {total}\n💰 إجمالي النقاط: {points}")

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id not in ADMIN_IDS:
        return
    keyboard = [
        [InlineKeyboardButton("📊 إحصائيات", callback_data='admin_stats')],
        [InlineKeyboardButton("👥 المستخدمين", callback_data='admin_users')],
    ]
    await query.edit_message_text("⚙️ لوحة التحكم", reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id not in ADMIN_IDS:
        return
    await query.answer()
    total = get_total_users()
    conn = sqlite3.connect('profit_bot.db')
    c = conn.cursor()
    c.execute("SELECT SUM(points) FROM users")
    points = c.fetchone()[0] or 0
    conn.close()
    await query.edit_message_text(f"📊 إجمالي المستخدمين: {total}\n💰 إجمالي النقاط: {points}")

async def admin_users_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id not in ADMIN_IDS:
        return
    await query.answer()
    users = get_all_users()
    text = "👥 **المستخدمون:**\n\n"
    for u in users[:10]:
        text += f"👤 {u[1]}: {u[2]} نقطة\n"
    await query.edit_message_text(text)

# =========== معالج الأزرار الرئيسي (الأهم) ===========
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    # أوامر المستخدمين
    if data == 'watch_ad':
        await watch_ad(update, context)
    elif data == 'ad_watched':
        await ad_watched(update, context)
    elif data == 'daily_checkin':
        await daily_checkin(update, context)
    elif data == 'balance':
        await balance(update, context)
    elif data == 'refer':
        await refer(update, context)
    elif data == 'withdraw':
        await withdraw(update, context)
    # أوامر الأدمن
    elif data == 'admin_panel':
        await admin_panel(update, context)
    elif data == 'admin_stats':
        await admin_stats_callback(update, context)
    elif data == 'admin_users':
        await admin_users_callback(update, context)
    else:
        await query.edit_message_text("❌ أمر غير معروف")

# =========== تشغيل البوت ===========
def main():
    if not TOKEN:
        print("❌ خطأ: التوكن غير موجود")
        return
    init_db()
    app = Application.builder().token(TOKEN).build()
    
    # أوامر المستخدمين
    app.add_handler(CommandHandler("start", start))
    
    # أوامر الأدمن (نصية)
    app.add_handler(CommandHandler("users", admin_users))
    app.add_handler(CommandHandler("search", admin_search))
    app.add_handler(CommandHandler("addpoints", admin_addpoints))
    app.add_handler(CommandHandler("removepoints", admin_removepoints))
    app.add_handler(CommandHandler("ban", admin_ban))
    app.add_handler(CommandHandler("unban", admin_unban))
    app.add_handler(CommandHandler("export", admin_export))
    app.add_handler(CommandHandler("stats", admin_stats))
    
    # معالج الأزرار (الأهم)
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("✅ البوت يعمل...")
    app.run_polling()

if __name__ == '__main__':
    main()
