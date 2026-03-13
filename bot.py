import logging
import sqlite3
from datetime import datetime, timedelta
import os
import random
import asyncio
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
                  phone_number TEXT DEFAULT NULL,
                  is_admin INTEGER DEFAULT 0)''')
    
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
                  request_date TEXT,
                  process_date TEXT DEFAULT NULL)''')
    
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

def create_user(user_id, username, first_name, referrer_id=None):
    conn = sqlite3.connect('profit_bot.db')
    c = conn.cursor()
    c.execute('''INSERT OR IGNORE INTO users 
                 (user_id, username, first_name, joined_date, referrer_id) 
                 VALUES (?, ?, ?, ?, ?)''',
              (user_id, username, first_name, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), referrer_id))
    
    if referrer_id and referrer_id != user_id:
        c.execute("UPDATE users SET points = points + 80, total_referrals = total_referrals + 1, referral_earned = referral_earned + 80 WHERE user_id=?", (referrer_id,))
    
    conn.commit()
    conn.close()

def update_points(user_id, points_to_add):
    try:
        conn = sqlite3.connect('profit_bot.db')
        c = conn.cursor()
        c.execute("UPDATE users SET points = points + ?, total_earned = total_earned + ? WHERE user_id=?", 
                  (points_to_add, points_to_add, user_id))
        c.execute("SELECT points FROM users WHERE user_id=?", (user_id,))
        new_points = c.fetchone()[0]
        conn.commit()
        conn.close()
        print(f"✅ تم إضافة {points_to_add} نقاط للمستخدم {user_id}")
        return new_points
    except Exception as e:
        print(f"❌ خطأ في إضافة النقاط: {e}")
        return 0

def get_ads_today(user_id):
    conn = sqlite3.connect('profit_bot.db')
    c = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')
    c.execute("SELECT ad_count FROM ads WHERE user_id=? AND ad_date=?", (user_id, today))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 0

def add_ad_watch(user_id):
    try:
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
        print(f"✅ تم تسجيل مشاهدة إعلان للمستخدم {user_id}")
        return True
    except Exception as e:
        print(f"❌ خطأ في تسجيل المشاهدة: {e}")
        return False

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
    count = c.fetchone()[0]
    conn.close()
    return count

# =========== أوامر البوت ===========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    username = user.username or "لا يوجد"
    first_name = user.first_name or "مستخدم"
    
    referrer_id = None
    if context.args and context.args[0].isdigit():
        referrer_id = int(context.args[0])
    
    create_user(user_id, username, first_name, referrer_id)
    
    points = get_user_points(user_id)
    ads_today = get_ads_today(user_id)
    
    keyboard = [
        [InlineKeyboardButton("📺 مشاهدة إعلان", callback_data='watch_ad')],
        [InlineKeyboardButton("✅ تسجيل يومي", callback_data='daily_checkin'),
         InlineKeyboardButton("💰 رصيدي", callback_data='balance')],
        [InlineKeyboardButton("👥 دعوة أصدقاء", callback_data='refer'),
         InlineKeyboardButton("💳 سحب أرباح", callback_data='withdraw')],
        [InlineKeyboardButton("📊 الإحصائيات", callback_data='stats')]
    ]
    
    if user_id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("⚙️ لوحة التحكم", callback_data='admin_panel')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"🎉 أهلاً بك في **بوت الربح الذكي** يا {first_name}!\n\n"
        f"📊 إعلانات اليوم: {ads_today}/400\n"
        f"💰 رصيدك: {points} نقطة\n\n"
        f"💡 كل 300 نقطة = 55 جنيه\n\n"
        "اختر من القائمة 👇",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def watch_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء مشاهدة إعلان"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    ads_today = get_ads_today(user_id)
    
    if ads_today >= 400:
        await query.edit_message_text(
            "❌ لقد استنفدت حد الإعلانات اليومي",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 القائمة", callback_data='main_menu')
            ]])
        )
        return
    
    # إنشاء أزرار الإعلان
    keyboard = [
        [InlineKeyboardButton("🌐 الذهاب للموقع", url="https://t.me/YourTapEarnBot/Earn_App")],
        [InlineKeyboardButton("✅ تمت المشاهدة", callback_data='check_ad_watched')],
        [InlineKeyboardButton("🔙 إلغاء", callback_data='main_menu')]
    ]
    
    # تسجيل وقت بدء المشاهدة
    context.user_data['ad_start_time'] = datetime.now()
    context.user_data['ad_watched'] = False
    
    await query.edit_message_text(
        f"📺 **مشاهدة إعلان**\n\n"
        f"1. اضغط على 'الذهاب للموقع'\n"
        f"2. شاهد الإعلان في الموقع\n"
        f"3. انتظر 30 ثانية\n"
        f"4. اضغط على 'تمت المشاهدة'\n\n"
        f"📊 إعلانات اليوم: {ads_today}/400",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def check_ad_watched(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """التحقق من مشاهدة الإعلان"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # التحقق من وجود وقت بدء
    if 'ad_start_time' not in context.user_data:
        await query.edit_message_text(
            "❌ حدث خطأ، حاول مرة أخرى",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 القائمة", callback_data='main_menu')
            ]])
        )
        return
    
    # حساب الوقت المنقضي
    elapsed = (datetime.now() - context.user_data['ad_start_time']).total_seconds()
    
    if elapsed < 30:
        # لو لسه مكملش 30 ثانية
        remaining = int(30 - elapsed)
        await query.edit_message_text(
            f"⏳ **لم تكتمل المشاهدة بعد**\n\n"
            f"انتظر {remaining} ثانية إضافية",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 رجوع", callback_data='watch_ad')
            ]])
        )
        return
    
    # لو عدى 30 ثانية
    ads_today = get_ads_today(user_id)
    
    if ads_today >= 400:
        await query.edit_message_text(
            "❌ لقد استنفدت حد الإعلانات اليومي",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 القائمة", callback_data='main_menu')
            ]])
        )
        return
    
    # إضافة النقطة
    success = add_ad_watch(user_id)
    if success:
        new_points = update_points(user_id, 1)
        ads_today = get_ads_today(user_id)
        ads_left = 400 - ads_today
        
        # تنظيف بيانات الجلسة
        del context.user_data['ad_start_time']
        
        keyboard = [
            [InlineKeyboardButton("📺 إعلان آخر", callback_data='watch_ad')],
            [InlineKeyboardButton("🔙 القائمة", callback_data='main_menu')]
        ]
        
        await query.edit_message_text(
            f"✅ **تمت المشاهدة بنجاح!**\n\n"
            f"🎁 +1 نقطة\n"
            f"💰 رصيدك: {new_points} نقطة\n"
            f"📊 إعلانات اليوم: {ads_today}/400\n"
            f"⏳ تبقى {ads_left} إعلان",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    else:
        await query.edit_message_text(
            "❌ حدث خطأ، حاول مرة أخرى",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 القائمة", callback_data='main_menu')
            ]])
        )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    
    if data == 'watch_ad':
        await watch_ad(update, context)
    elif data == 'check_ad_watched':
        await check_ad_watched(update, context)
    elif data == 'daily_checkin':
        await daily_checkin(update, context)
    elif data == 'balance':
        await show_balance(update, context)
    elif data == 'refer':
        await show_referral(update, context)
    elif data == 'copy_link':
        await copy_referral_link(update, context)
    elif data == 'withdraw':
        await show_withdraw(update, context)
    elif data.startswith('wallet_'):
        await choose_wallet(update, context)
    elif data == 'stats':
        await show_stats(update, context)
    elif data == 'main_menu':
        await main_menu(update, context)
    elif data == 'admin_panel' and query.from_user.id in ADMIN_IDS:
        await admin_panel(update, context)
    elif data == 'admin_stats' and query.from_user.id in ADMIN_IDS:
        await admin_stats(update, context)
    elif data == 'admin_users' and query.from_user.id in ADMIN_IDS:
        await admin_users(update, context)
    elif data == 'admin_withdrawals' and query.from_user.id in ADMIN_IDS:
        await admin_withdrawals(update, context)
    elif data == 'admin_ads' and query.from_user.id in ADMIN_IDS:
        await admin_ads(update, context)
    elif data == 'admin_add_ad' and query.from_user.id in ADMIN_IDS:
        await admin_add_ad(update, context)

# =========== باقي الدوال (daily_checkin, show_balance, refer, withdraw, stats, admin, إلخ) ===========
# (سيتم إضافتها كما هي من الكود القديم لتجنب الإطالة)

async def daily_checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    
    if not can_checkin(user_id):
        await query.edit_message_text("✅ سجلت حضورك اليوم بالفعل!")
        return
    
    streak = add_checkin(user_id)
    new_points = update_points(user_id, 5)
    
    await query.edit_message_text(
        f"✅ **تسجيل يومي ناجح!**\n\n🔥 السلسلة: {streak} أيام\n💰 رصيدك: {new_points} نقطة",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 القائمة", callback_data='main_menu')
        ]]),
        parse_mode='Markdown'
    )

async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    points = get_user_points(user_id)
    egp_value = (points / 300) * 55
    
    await query.edit_message_text(
        f"💰 **رصيدك**\n\nالنقاط: {points}\nالقيمة: {egp_value:.2f} جنيه",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 القائمة", callback_data='main_menu')
        ]]),
        parse_mode='Markdown'
    )

async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    
    points = get_user_points(user_id)
    ads_today = get_ads_today(user_id)
    
    keyboard = [
        [InlineKeyboardButton("📺 مشاهدة إعلان", callback_data='watch_ad')],
        [InlineKeyboardButton("✅ تسجيل يومي", callback_data='daily_checkin'),
         InlineKeyboardButton("💰 رصيدي", callback_data='balance')],
        [InlineKeyboardButton("👥 دعوة أصدقاء", callback_data='refer'),
         InlineKeyboardButton("💳 سحب أرباح", callback_data='withdraw')],
        [InlineKeyboardButton("📊 الإحصائيات", callback_data='stats')]
    ]
    
    if user_id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("⚙️ لوحة التحكم", callback_data='admin_panel')])
    
    await query.edit_message_text(
        f"🎯 **القائمة الرئيسية**\n\n📊 إعلانات اليوم: {ads_today}/400\n💰 رصيدك: {points} نقطة",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

# =========== أوامر الأدمن ===========
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    keyboard = [
        [InlineKeyboardButton("📊 إحصائيات", callback_data='admin_stats')],
        [InlineKeyboardButton("👥 المستخدمين", callback_data='admin_users')],
        [InlineKeyboardButton("💳 السحوبات", callback_data='admin_withdrawals')],
        [InlineKeyboardButton("🔙 رجوع", callback_data='main_menu')]
    ]
    await query.edit_message_text("⚙️ لوحة الأدمن", reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    conn = sqlite3.connect('profit_bot.db')
    c = conn.cursor()
    total_users = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    total_points = c.execute("SELECT SUM(points) FROM users").fetchone()[0] or 0
    conn.close()
    await query.edit_message_text(f"📊 الإحصائيات\n\n👥 المستخدمين: {total_users}\n💰 النقاط: {total_points}")

# =========== تشغيل البوت ===========
def main():
    if not TOKEN:
        print("❌ خطأ: لم يتم تعيين BOT_TOKEN")
        return
    
    init_db()
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("✅ البوت يعمل بنجاح...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
