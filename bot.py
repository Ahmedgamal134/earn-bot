import logging
import sqlite3
from datetime import datetime, timedelta
import os
import random
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
import csv
from io import StringIO

# إعداد التسجيل
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# التوكن من المتغيرات البيئية
TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_IDS = [1103784347]  # ⚠️ غير الرقم ده لمعرفك من @userinfobot

# =========== قاعدة البيانات المحسّنة ===========
def init_db():
    """إنشاء جداول قاعدة البيانات"""
    conn = sqlite3.connect('profit_bot.db')
    c = conn.cursor()
    
    # جدول المستخدمين (موسع)
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
                  is_admin INTEGER DEFAULT 0,
                  is_banned INTEGER DEFAULT 0,
                  last_active TEXT,
                  ads_watched_today INTEGER DEFAULT 0,
                  last_ad_date TEXT)''')
    
    # جدول الإعلانات (عدد المشاهدات)
    c.execute('''CREATE TABLE IF NOT EXISTS ads
                 (user_id INTEGER,
                  ad_date TEXT,
                  ad_count INTEGER DEFAULT 0,
                  UNIQUE(user_id, ad_date))''')
    
    # جدول التسجيل اليومي
    c.execute('''CREATE TABLE IF NOT EXISTS daily_checkin
                 (user_id INTEGER,
                  check_date TEXT,
                  streak INTEGER DEFAULT 1,
                  UNIQUE(user_id, check_date))''')
    
    # جدول طلبات السحب
    c.execute('''CREATE TABLE IF NOT EXISTS withdrawals
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  amount REAL,
                  wallet_type TEXT,
                  wallet_number TEXT,
                  status TEXT DEFAULT 'قيد الانتظار',
                  request_date TEXT,
                  process_date TEXT DEFAULT NULL)''')
    
    # جدول الإعلانات النصية (المحتوى)
    c.execute('''CREATE TABLE IF NOT EXISTS ads_content
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  ad_text TEXT,
                  ad_link TEXT,
                  ad_type TEXT DEFAULT 'text',
                  is_active INTEGER DEFAULT 1)''')
    
    # جدول الدعوات (للتأكد من الدعوات الحقيقية)
    c.execute('''CREATE TABLE IF NOT EXISTS referrals
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  referrer_id INTEGER,
                  referred_id INTEGER UNIQUE,
                  referred_date TEXT,
                  points_given INTEGER DEFAULT 0,
                  UNIQUE(referrer_id, referred_id))''')
    
    conn.commit()
    conn.close()
    print("✅ تم إنشاء قاعدة البيانات")

# =========== دوال مساعدة ===========
def get_user(user_id):
    """جلب بيانات المستخدم"""
    conn = sqlite3.connect('profit_bot.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def get_user_points(user_id):
    """جلب نقاط المستخدم"""
    conn = sqlite3.connect('profit_bot.db')
    c = conn.cursor()
    c.execute("SELECT points FROM users WHERE user_id=?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 0

def is_user_banned(user_id):
    """التحقق من حظر المستخدم"""
    conn = sqlite3.connect('profit_bot.db')
    c = conn.cursor()
    c.execute("SELECT is_banned FROM users WHERE user_id=?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result and result[0] == 1

def create_user(user_id, username, first_name, referrer_id=None):
    """إنشاء مستخدم جديد"""
    if is_user_banned(user_id):
        return False
    
    conn = sqlite3.connect('profit_bot.db')
    c = conn.cursor()
    c.execute('''INSERT OR IGNORE INTO users 
                 (user_id, username, first_name, joined_date, referrer_id, last_active) 
                 VALUES (?, ?, ?, ?, ?, ?)''',
              (user_id, username, first_name, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), referrer_id, datetime.now().strftime('%Y-%m-%d')))
    
    # لو في دعوة حقيقية، نضيف نقاط للداعي
    if referrer_id and referrer_id != user_id:
        # نتأكد إن الدعوة جديدة
        c.execute("SELECT * FROM referrals WHERE referred_id=?", (user_id,))
        if not c.fetchone():
            c.execute("INSERT INTO referrals (referrer_id, referred_id, referred_date) VALUES (?, ?, ?)",
                     (referrer_id, user_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            c.execute("UPDATE users SET points = points + 80, total_referrals = total_referrals + 1, referral_earned = referral_earned + 80 WHERE user_id=?", (referrer_id,))
    
    conn.commit()
    conn.close()
    return True

def update_points(user_id, points_to_add):
    """إضافة نقاط للمستخدم"""
    if is_user_banned(user_id):
        return 0
    
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

def update_last_active(user_id):
    """تحديث آخر نشاط للمستخدم"""
    conn = sqlite3.connect('profit_bot.db')
    c = conn.cursor()
    c.execute("UPDATE users SET last_active=? WHERE user_id=?", (datetime.now().strftime('%Y-%m-%d'), user_id))
    conn.commit()
    conn.close()

def get_ads_today(user_id):
    """جلب عدد الإعلانات اللي شاهدها المستخدم اليوم"""
    conn = sqlite3.connect('profit_bot.db')
    c = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')
    c.execute("SELECT ad_count FROM ads WHERE user_id=? AND ad_date=?", (user_id, today))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 0

def add_ad_watch(user_id):
    """تسجيل مشاهدة إعلان"""
    if is_user_banned(user_id):
        return False
    
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
        
        # تحديث عدد الإعلانات اليومية في جدول المستخدمين
        c.execute("UPDATE users SET ads_watched_today = ads_watched_today + 1, last_ad_date=? WHERE user_id=?", (today, user_id))
        
        conn.commit()
        conn.close()
        print(f"✅ تم تسجيل مشاهدة إعلان للمستخدم {user_id}")
        return True
    except Exception as e:
        print(f"❌ خطأ في تسجيل المشاهدة: {e}")
        return False

def can_checkin(user_id):
    """التحقق من إمكانية تسجيل الدخول اليومي"""
    if is_user_banned(user_id):
        return False
    
    conn = sqlite3.connect('profit_bot.db')
    c = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')
    c.execute("SELECT * FROM daily_checkin WHERE user_id=? AND check_date=?", (user_id, today))
    result = c.fetchone()
    conn.close()
    return result is None

def add_checkin(user_id):
    """تسجيل دخول يومي"""
    if is_user_banned(user_id):
        return 0
    
    conn = sqlite3.connect('profit_bot.db')
    c = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')
    
    # جلب آخر تسجيل
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
    """جلب عدد المستخدمين الكلي"""
    conn = sqlite3.connect('profit_bot.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users WHERE is_banned=0")
    count = c.fetchone()[0]
    conn.close()
    return count

def get_all_users():
    """جلب كل المستخدمين (للأدمن)"""
    conn = sqlite3.connect('profit_bot.db')
    c = conn.cursor()
    c.execute("SELECT user_id, first_name, points, total_earned, joined_date, last_active FROM users ORDER BY points DESC")
    users = c.fetchall()
    conn.close()
    return users

# =========== أوامر الأدمن (التحكم الكامل) ===========
async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض إحصائيات المستخدمين (للأدمن)"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ هذا الأمر مخصص للأدمن فقط.")
        return
    
    total_users = get_total_users()
    users = get_all_users()
    
    text = f"👥 **إجمالي المستخدمين:** {total_users}\n\n"
    text += "**آخر 10 مستخدمين (حسب النقاط):**\n"
    
    for i, user in enumerate(users[:10], 1):
        user_id, name, points, earned, joined, last = user
        text += f"{i}. {name} - {points} نقطة (إجمالي: {earned})\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def admin_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """البحث عن مستخدم بواسطة معرفه"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ هذا الأمر مخصص للأدمن فقط.")
        return
    
    try:
        user_id = int(context.args[0])
        user = get_user(user_id)
        
        if not user:
            await update.message.reply_text("❌ المستخدم غير موجود")
            return
        
        text = f"👤 **بيانات المستخدم:**\n"
        text += f"🆔 المعرف: {user[0]}\n"
        text += f"👤 الاسم: {user[2]}\n"
        text += f"💰 النقاط: {user[3]}\n"
        text += f"📊 إجمالي الأرباح: {user[4]}\n"
        text += f"📅 تاريخ التسجيل: {user[5][:10]}\n"
        text += f"👥 الدعوات: {user[7]}\n"
        text += f"🎁 أرباح الدعوات: {user[8]}\n"
        text += f"🚫 محظور؟: {'نعم' if user[11] else 'لا'}\n"
        text += f"📱 آخر نشاط: {user[12]}\n"
        
        await update.message.reply_text(text, parse_mode='Markdown')
    except (IndexError, ValueError):
        await update.message.reply_text("❌ استخدم: /search [معرف المستخدم]")

async def admin_add_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إضافة نقاط لمستخدم"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ هذا الأمر مخصص للأدمن فقط.")
        return
    
    try:
        user_id = int(context.args[0])
        points = int(context.args[1])
        
        new_points = update_points(user_id, points)
        await update.message.reply_text(f"✅ تم إضافة {points} نقاط للمستخدم {user_id}. الرصيد الجديد: {new_points}")
    except (IndexError, ValueError):
        await update.message.reply_text("❌ استخدم: /addpoints [معرف المستخدم] [عدد النقاط]")

async def admin_remove_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """خصم نقاط من مستخدم"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ هذا الأمر مخصص للأدمن فقط.")
        return
    
    try:
        user_id = int(context.args[0])
        points = int(context.args[1])
        
        new_points = update_points(user_id, -points)
        await update.message.reply_text(f"✅ تم خصم {points} نقاط من المستخدم {user_id}. الرصيد الجديد: {new_points}")
    except (IndexError, ValueError):
        await update.message.reply_text("❌ استخدم: /removepoints [معرف المستخدم] [عدد النقاط]")

async def admin_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حظر مستخدم"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ هذا الأمر مخصص للأدمن فقط.")
        return
    
    try:
        user_id = int(context.args[0])
        
        conn = sqlite3.connect('profit_bot.db')
        c = conn.cursor()
        c.execute("UPDATE users SET is_banned=1 WHERE user_id=?", (user_id,))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(f"✅ تم حظر المستخدم {user_id}")
    except (IndexError, ValueError):
        await update.message.reply_text("❌ استخدم: /ban [معرف المستخدم]")

async def admin_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إلغاء حظر مستخدم"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ هذا الأمر مخصص للأدمن فقط.")
        return
    
    try:
        user_id = int(context.args[0])
        
        conn = sqlite3.connect('profit_bot.db')
        c = conn.cursor()
        c.execute("UPDATE users SET is_banned=0 WHERE user_id=?", (user_id,))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(f"✅ تم إلغاء حظر المستخدم {user_id}")
    except (IndexError, ValueError):
        await update.message.reply_text("❌ استخدم: /unban [معرف المستخدم]")

async def admin_export(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تصدير بيانات المستخدمين كملف CSV"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ هذا الأمر مخصص للأدمن فقط.")
        return
    
    users = get_all_users()
    
    # إنشاء ملف CSV
    import csv
    from io import StringIO
    
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['User ID', 'Name', 'Points', 'Total Earned', 'Joined Date', 'Last Active'])
    
    for user in users:
        writer.writerow([user[0], user[1], user[2], user[3], user[4][:10], user[5]])
    
    # إرسال الملف
    await update.message.reply_document(
        document=output.getvalue().encode('utf-8'),
        filename='users_export.csv',
        caption='📊 بيانات المستخدمين'
    )

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إحصائيات عامة"""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ هذا الأمر مخصص للأدمن فقط.")
        return
    
    conn = sqlite3.connect('profit_bot.db')
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM users WHERE is_banned=0")
    total_users = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM users WHERE is_banned=1")
    banned_users = c.fetchone()[0]
    
    c.execute("SELECT SUM(points) FROM users")
    total_points = c.fetchone()[0] or 0
    
    c.execute("SELECT SUM(total_earned) FROM users")
    total_earned = c.fetchone()[0] or 0
    
    c.execute("SELECT COUNT(*) FROM withdrawals WHERE status='قيد الانتظار'")
    pending_withdrawals = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM ads WHERE ad_date=?", (datetime.now().strftime('%Y-%m-%d'),))
    ads_today = c.fetchone()[0]
    
    conn.close()
    
    text = (
        f"📊 **إحصائيات عامة**\n\n"
        f"👥 إجمالي المستخدمين: {total_users}\n"
        f"🚫 محظورين: {banned_users}\n"
        f"💰 إجمالي النقاط: {total_points}\n"
        f"💵 إجمالي الأرباح: {total_earned} نقطة\n"
        f"⏳ طلبات سحب معلقة: {pending_withdrawals}\n"
        f"📺 إعلانات اليوم: {ads_today}"
    )
    
    await update.message.reply_text(text, parse_mode='Markdown')

# =========== أوامر البوت للمستخدمين ===========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر /start"""
    user = update.effective_user
    user_id = user.id
    username = user.username or "لا يوجد"
    first_name = user.first_name or "مستخدم"
    
    # التحقق من الحظر
    if is_user_banned(user_id):
        await update.message.reply_text("⛔ لقد تم حظرك من استخدام هذا البوت.")
        return
    
    # التحقق من وجود دعوة
    referrer_id = None
    if context.args and context.args[0].startswith('invite_'):
        try:
            referrer_id = int(context.args[0].replace('invite_', ''))
            if referrer_id == user_id:
                referrer_id = None  # منع دعوة النفس
        except:
            referrer_id = None
    
    # إنشاء المستخدم لو مش موجود
    create_user(user_id, username, first_name, referrer_id)
    update_last_active(user_id)
    
    # جلب البيانات
    points = get_user_points(user_id)
    ads_today = get_ads_today(user_id)
    
    # إنشاء رابط دعوة فريد
    invite_link = f"https://t.me/{(await context.bot.get_me()).username}?start=invite_{user_id}"
    
    # الأزرار
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
        f"🔗 رابط دعوتك الخاص:\n`{invite_link}`\n\n"
        f"💡 كل 300 نقطة = 55 جنيه (سحب مفتوح)\n\n"
        "اختر من القائمة 👇",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def watch_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مشاهدة إعلان"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if is_user_banned(user_id):
        await query.edit_message_text("⛔ لقد تم حظرك من استخدام هذا البوت.")
        return
    
    update_last_active(user_id)
    ads_today = get_ads_today(user_id)
    
    if ads_today >= 400:
        await query.edit_message_text(
            "❌ لقد استنفدت حد الإعلانات اليومي (400 إعلان)\n"
            "تعال غداً لمشاهدة المزيد! 🌅",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 القائمة", callback_data='main_menu')
            ]])
        )
        return
    
    # رابط موقع الإعلانات
    site_url = "https://t.me/YourTapEarnBot/Earn_App"
    
    keyboard = [
        [InlineKeyboardButton("🌐 شاهد الإعلان على الموقع", url=site_url)],
        [InlineKeyboardButton("✅ بعد المشاهدة اضغط هنا", callback_data='ad_watched')],
        [InlineKeyboardButton("🔙 إلغاء", callback_data='main_menu')]
    ]
    
    await query.edit_message_text(
        f"📺 **مشاهدة إعلان**\n\n"
        f"⏱️ **الطريقة الصحيحة:**\n"
        f"1. اضغط على الرابط لفتح موقع الإعلانات\n"
        f"2. شاهد أي إعلان يظهر في الموقع\n"
        f"3. انتظر 15 ثانية\n"
        f"4. ارجع هنا واضغط على 'بعد المشاهدة اضغط هنا'\n\n"
        f"📊 إعلانات اليوم: {ads_today}/400",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def ad_watched(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بعد مشاهدة الإعلان"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if is_user_banned(user_id):
        await query.edit_message_text("⛔ لقد تم حظرك من استخدام هذا البوت.")
        return
    
    # إرسال مؤقت الانتظار
    await query.edit_message_text(
        "⏳ **جاري التحقق...**\n\n"
        "الرجاء الانتظار 15 ثانية",
        parse_mode='Markdown'
    )
    
    # انتظر 15 ثانية
    await asyncio.sleep(15)
    
    # تسجيل المشاهدة
    ads_today = get_ads_today(user_id)
    
    if ads_today >= 400:
        await query.edit_message_text(
            "❌ لقد استنفدت حد الإعلانات اليومي",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 القائمة", callback_data='main_menu')
            ]])
        )
        return
    
    # تسجيل المشاهدة وإضافة النقاط
    success = add_ad_watch(user_id)
    if success:
        new_points = update_points(user_id, 1)
        ads_today += 1
        ads_left = 400 - ads_today
        update_last_active(user_id)
        
        keyboard = [
            [InlineKeyboardButton("📺 إعلان آخر", callback_data='watch_ad')],
            [InlineKeyboardButton("🔙 القائمة", callback_data='main_menu')]
        ]
        
        await query.edit_message_text(
            f"✅ **تمت المشاهدة بنجاح!**\n\n"
            f"🎁 +1 نقطة\n"
            f"💰 رصيدك: {new_points} نقطة\n"
            f"📊 إعلانات اليوم: {ads_today}/400\n"
            f"⏳ تبقي {ads_left} إعلان",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    else:
        await query.edit_message_text(
            "❌ حدث خطأ في تسجيل المشاهدة، حاول مرة أخرى",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 القائمة", callback_data='main_menu')
            ]])
        )

async def daily_checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تسجيل يومي"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if is_user_banned(user_id):
        await query.edit_message_text("⛔ لقد تم حظرك من استخدام هذا البوت.")
        return
    
    if not can_checkin(user_id):
        await query.edit_message_text(
            "✅ لقد سجلت حضورك اليوم بالفعل!\n"
            "تعال غداً للتسجيل مرة أخرى ✨",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 القائمة", callback_data='main_menu')
            ]])
        )
        return
    
    update_last_active(user_id)
    streak = add_checkin(user_id)
    new_points = update_points(user_id, 3)  # 3 نقاط (بدل 5)
    
    # مكافآت إضافية للسلسلة
    bonus_message = ""
    if streak == 7:
        bonus_points = 20
        update_points(user_id, bonus_points)
        bonus_message = f"\n🎉 **مبروك! أكملت أسبوع كامل! +{bonus_points} نقطة هدية!**"
    elif streak == 30:
        bonus_points = 100
        update_points(user_id, bonus_points)
        bonus_message = f"\n🔥 **إنجاز! شهر كامل! +{bonus_points} نقطة هدية!**"
    
    await query.edit_message_text(
        f"✅ **تسجيل يومي ناجح!**\n\n"
        f"🔥 سلسلة تسجيلك: {streak} أيام\n"
        f"🎁 حصلت على: 3 نقاط\n"
        f"{bonus_message}\n"
        f"💰 رصيدك الآن: {new_points} نقطة",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 القائمة", callback_data='main_menu')
        ]]),
        parse_mode='Markdown'
    )

async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض الرصيد"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if is_user_banned(user_id):
        await query.edit_message_text("⛔ لقد تم حظرك من استخدام هذا البوت.")
        return
    
    update_last_active(user_id)
    user = get_user(user_id)
    if not user:
        await query.edit_message_text("حدث خطأ، حاول مرة أخرى")
        return
    
    points = user[3]
    total_earned = user[4]
    referrals = user[7]
    referral_earned = user[8]
    
    # حساب قيمة النقاط بالجنيه (300 نقطة = 55 جنيه)
    egp_value = (points / 300) * 55
    
    await query.edit_message_text(
        f"💰 **رصيدك الحالي**\n\n"
        f"النقاط: {points} نقطة\n"
        f"قيمتها: {egp_value:.2f} جنيه\n\n"
        f"📊 إجمالي ما كسبته: {total_earned} نقطة\n"
        f"👥 عدد دعواتك: {referrals}\n"
        f"🎁 أرباح الدعوات: {referral_earned} نقطة\n\n"
        f"💡 300 نقطة = 55 جنيه (سحب مفتوح)",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 القائمة", callback_data='main_menu')
        ]]),
        parse_mode='Markdown'
    )

async def show_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نظام الدعوة"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if is_user_banned(user_id):
        await query.edit_message_text("⛔ لقد تم حظرك من استخدام هذا البوت.")
        return
    
    update_last_active(user_id)
    bot_username = (await context.bot.get_me()).username
    referral_link = f"https://t.me/{bot_username}?start=invite_{user_id}"
    
    user = get_user(user_id)
    referrals = user[7] if user else 0
    referral_earned = user[8] if user else 0
    
    await query.edit_message_text(
        f"👥 **نظام دعوة الأصدقاء**\n\n"
        f"🔗 رابط الدعوة الخاص بك:\n"
        f"`{referral_link}`\n\n"
        f"🎁 مكافآت الدعوة:\n"
        f"• كل صديق يسجل من الرابط: 80 نقطة فوراً\n\n"
        f"📊 إحصائياتك:\n"
        f"• عدد الأصدقاء: {referrals}\n"
        f"• أرباح الدعوات: {referral_earned} نقطة",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 نسخ الرابط", callback_data='copy_link')],
            [InlineKeyboardButton("🔙 القائمة", callback_data='main_menu')]
        ]),
        parse_mode='Markdown'
    )

async def copy_referral_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نسخ رابط الدعوة"""
    query = update.callback_query
    user_id = query.from_user.id
    
    bot_username = (await context.bot.get_me()).username
    referral_link = f"https://t.me/{bot_username}?start=invite_{user_id}"
    
    await query.answer("تم النسخ! أرسل الرابط لأصدقائك", show_alert=True)
    
    await query.edit_message_text(
        f"👥 **نظام دعوة الأصدقاء**\n\n"
        f"🔗 رابط الدعوة:\n"
        f"`{referral_link}`\n\n"
        f"تم نسخ الرابط! شاركه مع أصدقائك 🎁",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 القائمة", callback_data='main_menu')
        ]]),
        parse_mode='Markdown'
    )

async def show_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """صفحة السحب"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if is_user_banned(user_id):
        await query.edit_message_text("⛔ لقد تم حظرك من استخدام هذا البوت.")
        return
    
    update_last_active(user_id)
    user = get_user(user_id)
    points = user[3] if user else 0
    
    if points < 300:
        points_needed = 300 - points
        
        await query.edit_message_text(
            f"💳 **سحب الأرباح**\n\n"
            f"❌ الحد الأدنى للسحب هو 300 نقطة (55 جنيه)\n\n"
            f"💰 رصيدك: {points} نقطة\n"
            f"📊 ينقصك: {points_needed} نقطة للوصول للحد الأدنى\n\n"
            f"استمر في الكسب حتى تصل للحد الأدنى 💪",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 القائمة", callback_data='main_menu')
            ]]),
            parse_mode='Markdown'
        )
        return
    
    # حساب المبلغ بالجنيه (كل 300 نقطة = 55 جنيه)
    egp_amount = (points / 300) * 55
    
    keyboard = [
        [InlineKeyboardButton("📱 فودافون كاش", callback_data='wallet_vodafone')],
        [InlineKeyboardButton("🟠 أورانج كاش", callback_data='wallet_orange')],
        [InlineKeyboardButton("📞 اتصالات كاش", callback_data='wallet_etisalat')],
        [InlineKeyboardButton("💳 وي كاش", callback_data='wallet_we')],
        [InlineKeyboardButton("🔙 رجوع", callback_data='main_menu')]
    ]
    
    await query.edit_message_text(
        f"💳 **طلب سحب أرباح**\n\n"
        f"💰 رصيدك: {points} نقطة\n"
        f"💵 قيمتها: {egp_amount:.2f} جنيه\n"
        f"اختر نوع المحفظة الإلكترونية:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def choose_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اختيار نوع المحفظة"""
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    
    wallet_type = {
        'wallet_vodafone': 'فودافون كاش',
        'wallet_orange': 'أورانج كاش', 
        'wallet_etisalat': 'اتصالات كاش',
        'wallet_we': 'وي كاش'
    }.get(data, 'محفظة')
    
    # جلب النقاط وحساب المبلغ
    user = get_user(user_id)
    points = user[3] if user else 0
    egp_amount = (points / 300) * 55
    
    context.user_data['wallet_type'] = wallet_type
    context.user_data['withdraw_amount'] = egp_amount
    context.user_data['withdraw_points'] = points
    context.user_data['awaiting_wallet'] = True
    
    await query.edit_message_text(
        f"💳 **طلب سحب - {wallet_type}**\n\n"
        f"💰 رصيدك: {points} نقطة\n"
        f"💵 المبلغ المستحق: {egp_amount:.2f} جنيه\n\n"
        f"الرجاء إرسال رقم المحفظة الخاص بك:\n"
        f"(مثال: 01012345678)\n\n"
        f"📌 تأكد من كتابة الرقم بشكل صحيح",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 رجوع", callback_data='withdraw')
        ]]),
        parse_mode='Markdown'
    )

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الإحصائيات الشخصية"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if is_user_banned(user_id):
        await query.edit_message_text("⛔ لقد تم حظرك من استخدام هذا البوت.")
        return
    
    update_last_active(user_id)
    total_users = get_total_users()
    user = get_user(user_id)
    points = user[3] if user else 0
    referrals = user[7] if user else 0
    ads_today = get_ads_today(user_id)
    
    ads_percent = (ads_today / 400) * 100
    
    await query.edit_message_text(
        f"📊 **إحصائياتك الشخصية**\n\n"
        f"👥 عدد مستخدمي البوت: {total_users}\n"
        f"💰 نقاطك: {points}\n"
        f"👤 دعواتك: {referrals}\n"
        f"📺 إعلانات اليوم: {ads_today}/400 ({ads_percent:.1f}%)\n\n"
        f"🏆 تقدمك نحو السحب:\n"
        f"{'█' * int(ads_percent/4)}{'░' * (25 - int(ads_percent/4))} {ads_percent:.1f}%",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 القائمة", callback_data='main_menu')
        ]]),
        parse_mode='Markdown'
    )

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """لوحة تحكم الأدمن"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if user_id not in ADMIN_IDS:
        await query.edit_message_text("⛔ هذا الأمر مخصص للأدمن فقط.")
        return
    
    keyboard = [
        [InlineKeyboardButton("📊 إحصائيات عامة", callback_data='admin_stats')],
        [InlineKeyboardButton("👥 عرض المستخدمين", callback_data='admin_users')],
        [InlineKeyboardButton("💳 طلبات السحب", callback_data='admin_withdrawals')],
        [InlineKeyboardButton("🔙 رجوع", callback_data='main_menu')]
    ]
    
    await query.edit_message_text(
        "⚙️ **لوحة تحكم الأدمن**\n"
        "اختر ما تريد:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def admin_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إحصائيات عامة (للأدمن)"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if user_id not in ADMIN_IDS:
        await query.edit_message_text("⛔ هذا الأمر مخصص للأدمن فقط.")
        return
    
    conn = sqlite3.connect('profit_bot.db')
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM users WHERE is_banned=0")
    total_users = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM users WHERE is_banned=1")
    banned_users = c.fetchone()[0]
    
    c.execute("SELECT SUM(points) FROM users")
    total_points = c.fetchone()[0] or 0
    
    c.execute("SELECT SUM(total_earned) FROM users")
    total_earned = c.fetchone()[0] or 0
    
    c.execute("SELECT COUNT(*) FROM withdrawals WHERE status='قيد الانتظار'")
    pending_withdrawals = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM ads WHERE ad_date=?", (datetime.now().strftime('%Y-%m-%d'),))
    ads_today = c.fetchone()[0]
    
    conn.close()
    
    text = (
        f"📊 **إحصائيات عامة**\n\n"
        f"👥 إجمالي المستخدمين: {total_users}\n"
        f"🚫 محظورين: {banned_users}\n"
        f"💰 إجمالي النقاط: {total_points}\n"
        f"💵 إجمالي الأرباح: {total_earned} نقطة\n"
        f"⏳ طلبات سحب معلقة: {pending_withdrawals}\n"
        f"📺 إعلانات اليوم: {ads_today}"
    )
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 رجوع", callback_data='admin_panel')
        ]]),
        parse_mode='Markdown'
    )

async def admin_users_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض المستخدمين (للأدمن)"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if user_id not in ADMIN_IDS:
        await query.edit_message_text("⛔ هذا الأمر مخصص للأدمن فقط.")
        return
    
    conn = sqlite3.connect('profit_bot.db')
    c = conn.cursor()
    c.execute('''SELECT user_id, first_name, points, total_earned, joined_date, is_banned 
                 FROM users ORDER BY points DESC LIMIT 10''')
    users = c.fetchall()
    conn.close()
    
    text = "👥 **أكثر 10 مستخدمين نقاطاً:**\n\n"
    for i, u in enumerate(users, 1):
        banned = "🚫" if u[5] else ""
        text += f"{i}. {u[1]} {banned}- {u[2]} نقطة (إجمالي: {u[3]})\n"
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 رجوع", callback_data='admin_panel')
        ]]),
        parse_mode='Markdown'
    )

async def admin_withdrawals_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض طلبات السحب (للأدمن)"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if user_id not in ADMIN_IDS:
        await query.edit_message_text("⛔ هذا الأمر مخصص للأدمن فقط.")
        return
    
    conn = sqlite3.connect('profit_bot.db')
    c = conn.cursor()
    c.execute('''SELECT * FROM withdrawals WHERE status="قيد الانتظار" ORDER BY request_date''')
    withdrawals = c.fetchall()
    conn.close()
    
    if not withdrawals:
        text = "✅ لا توجد طلبات سحب معلقة"
    else:
        text = "💳 **طلبات السحب المعلقة:**\n\n"
        for w in withdrawals:
            text += f"🆔 #{w[0]}\n"
            text += f"👤 مستخدم: {w[1]}\n"
            text += f"💰 المبلغ: {w[2]:.2f} جنيه\n"
            text += f"💳 المحفظة: {w[3]}\n"
            text += f"📱 الرقم: {w[4]}\n"
            text += f"📅 التاريخ: {w[6][:16]}\n"
            text += "-" * 20 + "\n"
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 رجوع", callback_data='admin_panel')
        ]]),
        parse_mode='Markdown'
    )

async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الرجوع للقائمة الرئيسية"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if is_user_banned(user_id):
        await query.edit_message_text("⛔ لقد تم حظرك من استخدام هذا البوت.")
        return
    
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
        f"🎯 **القائمة الرئيسية**\n\n"
        f"📊 إعلانات اليوم: {ads_today}/400\n"
        f"💰 رصيدك: {points} نقطة\n"
        f"💡 300 نقطة = 55 جنيه",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج الأزرار الرئيسي"""
    query = update.callback_query
    data = query.data
    
    if data == 'watch_ad':
        await watch_ad(update, context)
    elif data == 'ad_watched':
        await ad_watched(update, context)
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
    elif data == 'admin_panel':
        await admin_panel(update, context)
    elif data == 'admin_stats':
        await admin_stats_callback(update, context)
    elif data == 'admin_users':
        await admin_users_callback(update, context)
    elif data == 'admin_withdrawals':
        await admin_withdrawals_callback(update, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرسائل النصية"""
    user_id = update.effective_user.id
    text = update.message.text
    
    if is_user_banned(user_id):
        await update.message.reply_text("⛔ لقد تم حظرك من استخدام هذا البوت.")
        return
    
    # استقبال رقم المحفظة
    if context.user_data.get('awaiting_wallet'):
        wallet_number = text.strip()
        user_id = update.effective_user.id
        wallet_type = context.user_data.get('wallet_type', 'محفظة')
        points = context.user_data.get('withdraw_points', 0)
        egp_amount = context.user_data.get('withdraw_amount', 0)
        
        conn = sqlite3.connect('profit_bot.db')
        c = conn.cursor()
        c.execute('''INSERT INTO withdrawals 
                     (user_id, amount, wallet_type, wallet_number, request_date) 
                     VALUES (?, ?, ?, ?, ?)''',
                  (user_id, egp_amount, wallet_type, wallet_number, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        
        # خصم النقاط بالكامل
        c.execute("UPDATE users SET points = 0 WHERE user_id=?", (user_id,))
        
        conn.commit()
        conn.close()
        
        context.user_data['awaiting_wallet'] = False
        
        await update.message.reply_text(
            f"✅ **تم استلام طلب السحب!**\n\n"
            f"💰 المبلغ: {egp_amount:.2f} جنيه\n"
            f"💳 المحفظة: {wallet_type}\n"
            f"📱 الرقم: {wallet_number}\n\n"
            f"سيتم مراجعة الطلب وإرسال المبلغ خلال 24 ساعة ⏳",
            parse_mode='Markdown'
        )
    
    else:
        await update.message.reply_text("استخدم الأزرار للتحكم في البوت")

# =========== تشغيل البوت ===========
def main():
    """تشغيل البوت"""
    if not TOKEN:
        print("❌ خطأ: لم يتم تعيين BOT_TOKEN")
        return
    
    # إنشاء قاعدة البيانات
    init_db()
    
    # إنشاء التطبيق
    app = Application.builder().token(TOKEN).build()
    
    # إضافة المعالجات
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("users", admin_users))
    app.add_handler(CommandHandler("search", admin_search))
    app.add_handler(CommandHandler("addpoints", admin_add_points))
    app.add_handler(CommandHandler("removepoints", admin_remove_points))
    app.add_handler(CommandHandler("ban", admin_ban))
    app.add_handler(CommandHandler("unban", admin_unban))
    app.add_handler(CommandHandler("export", admin_export))
    app.add_handler(CommandHandler("stats", admin_stats))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # تشغيل البوت
    print("✅ البوت يعمل بنجاح...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
