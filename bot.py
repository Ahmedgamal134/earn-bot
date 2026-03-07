import logging
import sqlite3
from datetime import datetime, timedelta
import os
import random
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# إعداد التسجيل
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# التوكن من المتغيرات البيئية
TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_IDS = [1103784347]  # ⚠️ غير الرقم ده لمعرفك من @userinfobot

# =========== قاعدة البيانات ===========
def init_db():
    """إنشاء جداول قاعدة البيانات"""
    conn = sqlite3.connect('profit_bot.db')
    c = conn.cursor()
    
    # جدول المستخدمين
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
                  amount INTEGER,
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
                  ad_type TEXT DEFAULT 'text',  -- text, video, channel
                  is_active INTEGER DEFAULT 1)''')
    
    # إضافة بعض الإعلانات الافتراضية
    c.execute("SELECT COUNT(*) FROM ads_content")
    if c.fetchone()[0] == 0:
        c.execute('''INSERT INTO ads_content (ad_text, ad_link, ad_type) VALUES
                     ('اشترك في قناتنا على التليجرام', 'https://t.me/your_channel', 'channel'),
                     ('حمّل تطبيق الألعاب الجديد', 'https://play.google.com/store/apps/', 'text'),
                     ('خصم 20% على أول طلب', 'https://example.com/coupon', 'text'),
                     ('سيرفر ديسكورد للألعاب', 'https://discord.gg/', 'text'),
                     ('كوبون خصم 50 جنيه', 'https://example.com/offer', 'text')''')
    
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

def create_user(user_id, username, first_name, referrer_id=None):
    """إنشاء مستخدم جديد"""
    conn = sqlite3.connect('profit_bot.db')
    c = conn.cursor()
    c.execute('''INSERT OR IGNORE INTO users 
                 (user_id, username, first_name, joined_date, referrer_id) 
                 VALUES (?, ?, ?, ?, ?)''',
              (user_id, username, first_name, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), referrer_id))
    
    # لو في دعوة، نضيف نقاط للداعي
    if referrer_id and referrer_id != user_id:
        c.execute("UPDATE users SET points = points + 80, total_referrals = total_referrals + 1, referral_earned = referral_earned + 80 WHERE user_id=?", (referrer_id,))
    
    conn.commit()
    conn.close()

def update_points(user_id, points_to_add):
    """إضافة نقاط للمستخدم"""
    conn = sqlite3.connect('profit_bot.db')
    c = conn.cursor()
    c.execute("UPDATE users SET points = points + ?, total_earned = total_earned + ? WHERE user_id=?", 
              (points_to_add, points_to_add, user_id))
    c.execute("SELECT points FROM users WHERE user_id=?", (user_id,))
    new_points = c.fetchone()[0]
    conn.commit()
    conn.close()
    return new_points

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
    """التحقق من إمكانية تسجيل الدخول اليومي"""
    conn = sqlite3.connect('profit_bot.db')
    c = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')
    c.execute("SELECT * FROM daily_checkin WHERE user_id=? AND check_date=?", (user_id, today))
    result = c.fetchone()
    conn.close()
    return result is None

def add_checkin(user_id):
    """تسجيل دخول يومي"""
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
    c.execute("SELECT COUNT(*) FROM users")
    count = c.fetchone()[0]
    conn.close()
    return count

def get_random_ad():
    """جلب إعلان عشوائي من قاعدة البيانات"""
    conn = sqlite3.connect('profit_bot.db')
    c = conn.cursor()
    c.execute("SELECT id, ad_text, ad_link, ad_type FROM ads_content WHERE is_active=1 ORDER BY RANDOM() LIMIT 1")
    ad = c.fetchone()
    conn.close()
    return ad  # (id, text, link, type)

# =========== أوامر البوت ===========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر /start"""
    user = update.effective_user
    user_id = user.id
    username = user.username or "لا يوجد"
    first_name = user.first_name or "مستخدم"
    
    # التحقق من وجود دعوة
    referrer_id = None
    if context.args and context.args[0].isdigit():
        referrer_id = int(context.args[0])
    
    # إنشاء المستخدم لو مش موجود
    create_user(user_id, username, first_name, referrer_id)
    
    # جلب البيانات
    points = get_user_points(user_id)
    ads_today = get_ads_today(user_id)
    
    # زر Mini App
    web_app_button = InlineKeyboardButton(
        "🚀 فتح التطبيق المصغر", 
        web_app=WebAppInfo(url="https://ahmedgaml134.github.io/mini-app/")
    )
    
    keyboard = [
        [web_app_button],
        [InlineKeyboardButton("📺 مشاهدة إعلان", callback_data='watch_ad')],
        [InlineKeyboardButton("✅ تسجيل يومي", callback_data='daily_checkin'),
         InlineKeyboardButton("💰 رصيدي", callback_data='balance')],
        [InlineKeyboardButton("👥 دعوة أصدقاء", callback_data='refer'),
         InlineKeyboardButton("💳 سحب أرباح", callback_data='withdraw')],
        [InlineKeyboardButton("📊 الإحصائيات", callback_data='stats')]
    ]
    
    # لو المستخدم أدمن، ضيف زر التحكم
    if user_id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("⚙️ لوحة التحكم", callback_data='admin_panel')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"🎉 أهلاً بك في **بوت الربح الذكي** يا {first_name}!\n\n"
        f"📊 إعلانات اليوم: {ads_today}/400\n"
        f"💰 رصيدك: {points} نقطة\n\n"
        "اختر من القائمة 👇",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def watch_ad_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء مشاهدة إعلان"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
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
    
    # جلب إعلان عشوائي
    ad = get_random_ad()
    if not ad:
        await query.edit_message_text(
            "❌ لا توجد إعلانات حالياً، حاول لاحقاً",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 القائمة", callback_data='main_menu')
            ]])
        )
        return
    
    ad_id, ad_text, ad_link, ad_type = ad
    
    # حفظ الإعلان الحالي في context
    context.user_data['current_ad'] = {
        'id': ad_id,
        'text': ad_text,
        'link': ad_link,
        'type': ad_type
    }
    
    # رسالة الإعلان مع زر الرابط وزر الانتظار
    keyboard = [
        [InlineKeyboardButton("🔗 رابط الإعلان", url=ad_link)],
        [InlineKeyboardButton("⏳ اضغط بعد مشاهدة الإعلان", callback_data='ad_watched')],
        [InlineKeyboardButton("🔙 إلغاء", callback_data='main_menu')]
    ]
    
    await query.edit_message_text(
        f"📺 **مشاهدة إعلان**\n\n"
        f"{ad_text}\n\n"
        f"⏱️ **طريقة المشاهدة:**\n"
        f"1. اضغط على رابط الإعلان\n"
        f"2. انتظر 15 ثانية\n"
        f"3. اضغط على '⏳ اضغط بعد المشاهدة'\n\n"
        f"📊 إعلانات اليوم: {ads_today}/400",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def ad_watched(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بعد مشاهدة الإعلان"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # التحقق من وجود إعلان حالي
    if 'current_ad' not in context.user_data:
        await query.edit_message_text(
            "❌ حدث خطأ، حاول مرة أخرى",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 القائمة", callback_data='main_menu')
            ]])
        )
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
    
    add_ad_watch(user_id)
    new_points = update_points(user_id, 1)
    ads_today += 1
    ads_left = 400 - ads_today
    
    # حذف الإعلان الحالي من context
    del context.user_data['current_ad']
    
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

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج الأزرار الرئيسي"""
    query = update.callback_query
    data = query.data
    
    if data == 'watch_ad':
        await watch_ad_start(update, context)
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

async def daily_checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تسجيل يومي"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if not can_checkin(user_id):
        await query.edit_message_text(
            "✅ لقد سجلت حضورك اليوم بالفعل!\n"
            "تعال غداً للتسجيل مرة أخرى ✨",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 القائمة", callback_data='main_menu')
            ]])
        )
        return
    
    streak = add_checkin(user_id)
    new_points = update_points(user_id, 5)
    
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
        f"🎁 حصلت على: 5 نقاط\n"
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
    
    user = get_user(user_id)
    if not user:
        await query.edit_message_text("حدث خطأ، حاول مرة أخرى")
        return
    
    points = user[3]
    total_earned = user[4]
    referrals = user[7]
    referral_earned = user[8]
    
    # حساب قيمة النقاط بالجنيه
    egp_value = (points / 150000) * 600
    
    await query.edit_message_text(
        f"💰 **رصيدك الحالي**\n\n"
        f"النقاط: {points} نقطة\n"
        f"قيمتها: {egp_value:.2f} جنيه\n\n"
        f"📊 إجمالي ما كسبته: {total_earned} نقطة\n"
        f"👥 عدد دعواتك: {referrals}\n"
        f"🎁 أرباح الدعوات: {referral_earned} نقطة\n\n"
        f"💡 150,000 نقطة = 600 جنيه",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 القائمة", callback_data='main_menu')
        ]]),
        parse_mode='Markdown'
    )

async def show_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نظام الدعوة"""
    query = update.callback_query
    user_id = query.from_user.id
    
    bot_username = (await context.bot.get_me()).username
    referral_link = f"https://t.me/{bot_username}?start={user_id}"
    
    user = get_user(user_id)
    referrals = user[7] if user else 0
    referral_earned = user[8] if user else 0
    
    await query.edit_message_text(
        f"👥 **نظام دعوة الأصدقاء**\n\n"
        f"🔗 رابط الدعوة الخاص بك:\n"
        f"`{referral_link}`\n\n"
        f"🎁 مكافآت الدعوة:\n"
        f"• كل صديق يسجل: 80 نقطة فوراً\n\n"
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
    referral_link = f"https://t.me/{bot_username}?start={user_id}"
    
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
    
    user = get_user(user_id)
    points = user[3] if user else 0
    
    if points < 150000:
        points_needed = 150000 - points
        
        await query.edit_message_text(
            f"💳 **سحب الأرباح**\n\n"
            f"❌ لم تصل للحد الأدنى للسحب\n\n"
            f"💰 رصيدك: {points} نقطة\n"
            f"🎯 الحد الأدنى: 150,000 نقطة (600 جنيه)\n"
            f"📊 ينقصك: {points_needed} نقطة\n\n"
            f"استمر في الكسب حتى تصل للحد الأدنى 💪",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 القائمة", callback_data='main_menu')
            ]]),
            parse_mode='Markdown'
        )
        return
    
    # لو وصل للحد، نعرض اختيار المحفظة
    keyboard = [
        [InlineKeyboardButton("📱 فودافون كاش", callback_data='wallet_vodafone')],
        [InlineKeyboardButton("🟠 أورانج كاش", callback_data='wallet_orange')],
        [InlineKeyboardButton("📞 اتصالات كاش", callback_data='wallet_etisalat')],
        [InlineKeyboardButton("💳 وي كاش", callback_data='wallet_we')],
        [InlineKeyboardButton("🔙 رجوع", callback_data='main_menu')]
    ]
    
    await query.edit_message_text(
        f"💳 **طلب سحب أرباح**\n\n"
        f"💰 رصيدك: {points} نقطة = 600 جنيه\n"
        f"اختر نوع المحفظة الإلكترونية:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def choose_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اختيار نوع المحفظة"""
    query = update.callback_query
    data = query.data
    
    wallet_type = {
        'wallet_vodafone': 'فودافون كاش',
        'wallet_orange': 'أورانج كاش', 
        'wallet_etisalat': 'اتصالات كاش',
        'wallet_we': 'وي كاش'
    }.get(data, 'محفظة')
    
    context.user_data['wallet_type'] = wallet_type
    context.user_data['awaiting_wallet'] = True
    
    await query.edit_message_text(
        f"💳 **طلب سحب - {wallet_type}**\n\n"
        f"الرجاء إرسال رقم المحفظة الخاص بك:\n"
        f"(مثال: 01012345678)\n\n"
        f"📌 تأكد من كتابة الرقم بشكل صحيح",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 رجوع", callback_data='withdraw')
        ]]),
        parse_mode='Markdown'
    )

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الإحصائيات"""
    query = update.callback_query
    user_id = query.from_user.id
    
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
        f"🏆 تقدمك نحو 600 جنيه:\n"
        f"{'█' * int(ads_percent/4)}{'░' * (25 - int(ads_percent/4))} {ads_percent:.1f}%",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 القائمة", callback_data='main_menu')
        ]]),
        parse_mode='Markdown'
    )

async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الرجوع للقائمة الرئيسية"""
    query = update.callback_query
    user_id = query.from_user.id
    
    points = get_user_points(user_id)
    ads_today = get_ads_today(user_id)
    
    web_app_button = InlineKeyboardButton(
        "🚀 فتح التطبيق المصغر", 
        web_app=WebAppInfo(url="https://ahmedgaml134.github.io/mini-app/")
    )
    
    keyboard = [
        [web_app_button],
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
        f"💰 رصيدك: {points} نقطة",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

# =========== أوامر الأدمن ===========
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """لوحة تحكم الأدمن"""
    query = update.callback_query
    
    keyboard = [
        [InlineKeyboardButton("📊 إحصائيات عامة", callback_data='admin_stats')],
        [InlineKeyboardButton("👥 عرض المستخدمين", callback_data='admin_users')],
        [InlineKeyboardButton("💳 طلبات السحب", callback_data='admin_withdrawals')],
        [InlineKeyboardButton("📢 إدارة الإعلانات", callback_data='admin_ads')],
        [InlineKeyboardButton("🔙 رجوع", callback_data='main_menu')]
    ]
    
    await query.edit_message_text(
        "⚙️ **لوحة تحكم الأدمن**\n"
        "اختر ما تريد:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إحصائيات عامة للأدمن"""
    query = update.callback_query
    
    conn = sqlite3.connect('profit_bot.db')
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    
    c.execute("SELECT SUM(points) FROM users")
    total_points = c.fetchone()[0] or 0
    
    c.execute("SELECT SUM(total_earned) FROM users")
    total_earned = c.fetchone()[0] or 0
    
    c.execute("SELECT COUNT(*) FROM withdrawals WHERE status='قيد الانتظار'")
    pending_withdrawals = c.fetchone()[0]
    
    today = datetime.now().strftime('%Y-%m-%d')
    c.execute("SELECT COUNT(DISTINCT user_id) FROM ads WHERE ad_date=?", (today,))
    active_today = c.fetchone()[0]
    
    conn.close()
    
    text = (
        f"📊 **إحصائيات عامة**\n\n"
        f"👥 إجمالي المستخدمين: {total_users}\n"
        f"💰 إجمالي النقاط: {total_points}\n"
        f"💵 إجمالي الأرباح: {total_earned} نقطة\n"
        f"⏳ طلبات سحب معلقة: {pending_withdrawals}\n"
        f"📱 نشطاء اليوم: {active_today}"
    )
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 رجوع", callback_data='admin_panel')
        ]]),
        parse_mode='Markdown'
    )

async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض المستخدمين للأدمن"""
    query = update.callback_query
    
    conn = sqlite3.connect('profit_bot.db')
    c = conn.cursor()
    c.execute('''SELECT user_id, first_name, points, total_referrals 
                 FROM users ORDER BY points DESC LIMIT 10''')
    users = c.fetchall()
    conn.close()
    
    text = "👥 **أكثر 10 مستخدمين نقاطاً:**\n\n"
    for i, u in enumerate(users, 1):
        text += f"{i}. {u[1]} - {u[2]} نقطة - {u[3]} دعوات\n"
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 رجوع", callback_data='admin_panel')
        ]]),
        parse_mode='Markdown'
    )

async def admin_withdrawals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض طلبات السحب للأدمن"""
    query = update.callback_query
    
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
            text += f"💰 المبلغ: {w[3]} جنيه\n"
            text += f"💳 المحفظة: {w[4]}\n"
            text += f"📱 الرقم: {w[5]}\n"
            text += f"📅 التاريخ: {w[7][:16]}\n"
            text += "-" * 20 + "\n"
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 رجوع", callback_data='admin_panel')
        ]]),
        parse_mode='Markdown'
    )

async def admin_ads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إدارة الإعلانات للأدمن"""
    query = update.callback_query
    
    conn = sqlite3.connect('profit_bot.db')
    c = conn.cursor()
    c.execute("SELECT id, ad_text, ad_link, is_active FROM ads_content")
    ads = c.fetchall()
    conn.close()
    
    text = "📢 **إدارة الإعلانات**\n\n"
    for ad in ads:
        status = "✅ نشط" if ad[3] else "❌ غير نشط"
        text += f"🆔 {ad[0]}: {ad[1]}\n{ad[2]}\nالحالة: {status}\n\n"
    
    keyboard = [
        [InlineKeyboardButton("➕ إضافة إعلان", callback_data='admin_add_ad')],
        [InlineKeyboardButton("🔙 رجوع", callback_data='admin_panel')]
    ]
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def admin_add_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إضافة إعلان جديد (الأدمن)"""
    query = update.callback_query
    
    context.user_data['adding_ad'] = True
    await query.edit_message_text(
        "📝 أرسل الإعلان الجديد بالصيغة:\n"
        "عنوان الإعلان\n"
        "رابط الإعلان\n\n"
        "مثال:\n"
        "اشترك في قناتنا\n"
        "https://t.me/your_channel",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 إلغاء", callback_data='admin_ads')
        ]])
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرسائل النصية"""
    user_id = update.effective_user.id
    text = update.message.text
    
    # استقبال رقم المحفظة
    if context.user_data.get('awaiting_wallet'):
        wallet_number = text.strip()
        wallet_type = context.user_data.get('wallet_type', 'محفظة')
        
        conn = sqlite3.connect('profit_bot.db')
        c = conn.cursor()
        c.execute('''INSERT INTO withdrawals 
                     (user_id, amount, wallet_type, wallet_number, request_date) 
                     VALUES (?, ?, ?, ?, ?)''',
                  (user_id, 600, wallet_type, wallet_number, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        c.execute("UPDATE users SET points = points - 150000 WHERE user_id=?", (user_id,))
        conn.commit()
        conn.close()
        
        context.user_data['awaiting_wallet'] = False
        
        await update.message.reply_text(
            f"✅ **تم استلام طلب السحب!**\n\n"
            f"💰 المبلغ: 600 جنيه\n"
            f"💳 المحفظة: {wallet_type}\n"
            f"📱 الرقم: {wallet_number}\n\n"
            f"سيتم مراجعة الطلب وإرسال المبلغ خلال 24 ساعة ⏳",
            parse_mode='Markdown'
        )
    
    # استقبال إعلان جديد من الأدمن
    elif context.user_data.get('adding_ad') and user_id in ADMIN_IDS:
        lines = text.strip().split('\n')
        if len(lines) >= 2:
            ad_text = lines[0]
            ad_link = lines[1]
            
            conn = sqlite3.connect('profit_bot.db')
            c = conn.cursor()
            c.execute("INSERT INTO ads_content (ad_text, ad_link) VALUES (?, ?)", (ad_text, ad_link))
            conn.commit()
            conn.close()
            
            context.user_data['adding_ad'] = False
            await update.message.reply_text("✅ تم إضافة الإعلان بنجاح!")
        else:
            await update.message.reply_text("❌ صيغة خاطئة! أرسل عنوان الإعلان ثم في سطر جديد الرابط")
    
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
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # تشغيل البوت
    print("✅ البوت يعمل بنجاح...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
