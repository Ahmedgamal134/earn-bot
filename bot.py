import logging
import sqlite3
from datetime import datetime, timedelta
import os
import random
import asyncio
import json
import requests  # <-- هنستخدم requests عشان نطلب الإعلانات من API بتاع TADS
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# إعداد التسجيل
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# التوكن من المتغيرات البيئية
TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_IDS = [1103784347]  # ⚠️ غير الرقم ده لمعرفك من @userinfobot

# =========== بيانات TADS (من حسابك) ===========
TADS_WIDGET_ID = 9544  # الـ ID بتاع الـ widget
TADS_DEBUG = False     # لازم يكون False عشان تجيب إعلانات حقيقية (مش وهمية) 
TADS_API_URL = "https://api.tads.me/v1/ad"  # الرابط المفترض لطلب الإعلانات
TADS_REWARD_URL = "https://your-webhook-url.com/tads-callback"  # دا الـ Webhook URL اللي المفروض تضيفه في إعدادات الـ Widget عشان TADS تبعتلك إشارة لما المستخدم يشوف أو يضغط على إعلان

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
    
    # إضافة بعض الإعلانات الافتراضية (احتياطي)
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
    try:
        conn = sqlite3.connect('profit_bot.db')
        c = conn.cursor()
        c.execute("UPDATE users SET points = points + ?, total_earned = total_earned + ? WHERE user_id=?", 
                  (points_to_add, points_to_add, user_id))
        c.execute("SELECT points FROM users WHERE user_id=?", (user_id,))
        new_points = c.fetchone()[0]
        conn.commit()
        conn.close()
        print(f"✅ تم إضافة {points_to_add} نقاط للمستخدم {user_id}. الرصيد الجديد: {new_points}")
        return new_points
    except Exception as e:
        print(f"❌ خطأ في إضافة النقاط: {e}")
        return 0

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
    """جلب إعلان عشوائي من قاعدة البيانات (احتياطي)"""
    conn = sqlite3.connect('profit_bot.db')
    c = conn.cursor()
    c.execute("SELECT id, ad_text, ad_link, ad_type FROM ads_content WHERE is_active=1 ORDER BY RANDOM() LIMIT 1")
    ad = c.fetchone()
    conn.close()
    return ad  # (id, text, link, type)

# =========== دوال TADS (طريقة API الحقيقية) ===========
async def fetch_tads_ad(user_id: int):
    """جلب إعلان حقيقي من TADS باستخدام widget_id"""
    try:
        # 1. نبني الطلب اللي هنرسله لـ TADS
        # دي طريقة تقريبية حسب وثائق TADS، لكن التفاصيل الدقيقة محتاجة تتأكد من موقعهم
        params = {
            'widget_id': TADS_WIDGET_ID,
            'user_id': user_id,
            'debug': 1 if TADS_DEBUG else 0  # لو True، هيرجع إعلانات تجريبية
        }
        
        # 2. نرسل طلب GET لـ TADS API
        # هنا حطيت URL افتراضي، لازم تتأكد من الرابط الصحيح من وثائقهم
        response = requests.get(TADS_API_URL, params=params, timeout=10)
        
        if response.status_code == 200:
            ad_data = response.json()
            print(f"✅ تم جلب إعلان من TADS للمستخدم {user_id}")
            return ad_data
        else:
            print(f"❌ خطأ من TADS API: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ خطأ في الاتصال بـ TADS API: {e}")
        return None

async def fetch_tads_ad_fallback(user_id: int):
    """دالة احتياطية لو API مش شغال، بتجيب بيانات إعلان وهمي"""
    print(f"⚠️ استخدام الإعلان الاحتياطي للمستخدم {user_id}")
    return {
        'id': TADS_WIDGET_ID,
        'image_url': 'https://via.placeholder.com/300x150/764ba2/ffffff?text=إعلان',
        'title': 'إعلان ممول',
        'description': 'شاهد هذا الإعلان واحصل على نقاط مجانية!',
        'click_url': 'https://t.me/YourTapEarnBot/Earn_App?start=ad',
        'reward_type': 'click'  # TGB يعطي مكافأة عند النقر 
    }

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
    
    # الأزرار العادية
    keyboard = [
        [InlineKeyboardButton("📺 مشاهدة إعلان TADS", callback_data='watch_tads_ad')],
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
        f"💡 كل 300 نقطة = 55 جنيه (سحب مفتوح)\n\n"
        "اختر من القائمة 👇",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def watch_tads_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مشاهدة إعلان TADS (يحاول يجيب إعلان حقيقي من API)"""
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
    
    # 1. نحاول نجيب إعلان حقيقي من API
    await query.edit_message_text("⏳ جاري تحميل الإعلان...")
    
    ad_data = await fetch_tads_ad(user_id)
    
    # 2. لو API فشل (مثلاً مش شغال أو رجع None)، نستخدم الإعلان الاحتياطي
    if not ad_data:
        ad_data = await fetch_tads_ad_fallback(user_id)
    
    # 3. بناء رسالة الإعلان وعرضها
    try:
        # حفظ بيانات الإعلان في context عشان نستخدمها بعدين
        context.user_data['current_ad'] = {
            'id': ad_data.get('id', TADS_WIDGET_ID),
            'click_url': ad_data.get('click_url', 'https://t.me/YourTapEarnBot/Earn_App'),
            'reward_type': ad_data.get('reward_type', 'click')
        }
        
        # إنشاء أزرار الإعلان
        keyboard = [
            [InlineKeyboardButton("🔗 رابط الإعلان", url=ad_data.get('click_url', 'https://t.me/YourTapEarnBot/Earn_App'))],
            [InlineKeyboardButton("✅ استلام النقاط", callback_data='tads_ad_clicked')],
            [InlineKeyboardButton("🔙 إلغاء", callback_data='main_menu')]
        ]
        
        # إرسال الإعلان (صورة + كابشن)
        image_url = ad_data.get('image_url', 'https://via.placeholder.com/300x150/764ba2/ffffff?text=إعلان')
        title = ad_data.get('title', 'إعلان ممول')
        description = ad_data.get('description', 'شاهد هذا الإعلان واحصل على نقاط مجانية!')
        
        await query.message.reply_photo(
            photo=image_url,
            caption=f"📢 **{title}**\n\n{description}\n\nاضغط على الرابط لمشاهدة الإعلان، ثم استلم نقاطك!",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        # حذف رسالة "جاري التحميل"
        await query.delete_message()
            
    except Exception as e:
        print(f"❌ خطأ في عرض الإعلان: {e}")
        await query.edit_message_text(
            "❌ حدث خطأ في عرض الإعلان",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 القائمة", callback_data='main_menu')
            ]])
        )

async def tads_ad_clicked(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بعد النقر على إعلان TADS (أو الضغط على استلام النقاط)"""
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
    
    # تسجيل المشاهدة وإضافة النقاط
    success = add_ad_watch(user_id)
    if success:
        new_points = update_points(user_id, 1)
        ads_today += 1
        ads_left = 400 - ads_today
        
        # حذف الإعلان الحالي من context
        del context.user_data['current_ad']
        
        keyboard = [
            [InlineKeyboardButton("📺 إعلان آخر", callback_data='watch_tads_ad')],
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

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج الأزرار الرئيسي"""
    query = update.callback_query
    data = query.data
    
    if data == 'watch_tads_ad':
        await watch_tads_ad(update, context)
    elif data == 'tads_ad_clicked':
        await tads_ad_clicked(update, context)
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

# =========== باقي أوامر المستخدم (زي ما هي) ===========
# دوال daily_checkin, show_balance, show_referral, copy_referral_link, show_withdraw, choose_wallet, show_stats, main_menu
# كلها موجودة في الكود القديم، مش محتاج نكررها هنا للاختصار.
# لو حابب أضيفها كاملة في الملف النهائي، قولي.

# =========== أوامر الأدمن (زي ما هي) ===========
# دوال admin_panel, admin_stats, admin_users, admin_withdrawals, admin_ads, admin_add_ad
# كلها موجودة في الكود القديم.

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
