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
# ⚠️ غير الرقم ده لمعرفك من @userinfobot
ADMIN_IDS = [1103784347]  # حط معرفك هنا

# =========== قاعدة البيانات ===========
def init_db():
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
                  is_banned INTEGER DEFAULT 0,
                  ban_reason TEXT DEFAULT NULL,
                  notes TEXT DEFAULT NULL)''')
    
    # جدول الإعلانات
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
                  transaction_id TEXT,
                  status TEXT DEFAULT 'قيد الانتظار',
                  request_date TEXT,
                  process_date TEXT DEFAULT NULL)''')
    
    # جدول المحافظ
    c.execute('''CREATE TABLE IF NOT EXISTS wallets
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  wallet_type TEXT,
                  wallet_number TEXT,
                  is_default INTEGER DEFAULT 0,
                  added_date TEXT,
                  UNIQUE(user_id, wallet_type, wallet_number))''')
    
    # جدول سجل المشرفين
    c.execute('''CREATE TABLE IF NOT EXISTS admin_logs
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  admin_id INTEGER,
                  action TEXT,
                  target_user INTEGER,
                  details TEXT,
                  action_date TEXT)''')
    
    conn.commit()
    conn.close()
    print("✅ تم إنشاء قاعدة البيانات")

# =========== دوال المستخدمين ===========
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
    
    # التحقق من وجود المستخدم
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    if c.fetchone():
        conn.close()
        return
    
    c.execute('''INSERT INTO users 
                 (user_id, username, first_name, joined_date, referrer_id) 
                 VALUES (?, ?, ?, ?, ?)''',
              (user_id, username, first_name, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), referrer_id))
    
    conn.commit()
    conn.close()

def update_points(user_id, points_to_add):
    try:
        conn = sqlite3.connect('profit_bot.db')
        c = conn.cursor()
        
        # التحقق من عدم حظر المستخدم
        c.execute("SELECT is_banned FROM users WHERE user_id=?", (user_id,))
        user = c.fetchone()
        if user and user[0]:
            conn.close()
            return False, 0, "محظور"
        
        c.execute("UPDATE users SET points = points + ?, total_earned = total_earned + ? WHERE user_id=?", 
                  (points_to_add, points_to_add, user_id))
        c.execute("SELECT points FROM users WHERE user_id=?", (user_id,))
        new_points = c.fetchone()[0]
        conn.commit()
        conn.close()
        return True, new_points, "تم"
    except Exception as e:
        print(f"❌ خطأ في إضافة النقاط: {e}")
        return False, 0, str(e)

def log_admin_action(admin_id, action, target_user, details=""):
    conn = sqlite3.connect('profit_bot.db')
    c = conn.cursor()
    c.execute('''INSERT INTO admin_logs (admin_id, action, target_user, details, action_date)
                 VALUES (?, ?, ?, ?, ?)''',
              (admin_id, action, target_user, details, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()

# =========== إشعارات المشرفين ===========
async def notify_admin(context, user_id, action, details):
    """إرسال إشعار فوري للمشرف عن أي نشاط"""
    
    # جلب معلومات المستخدم
    conn = sqlite3.connect('profit_bot.db')
    c = conn.cursor()
    c.execute("SELECT first_name, username, points FROM users WHERE user_id=?", (user_id,))
    user = c.fetchone()
    conn.close()
    
    if not user:
        return
    
    name = user[0]
    points = user[2]
    
    # أيقونة حسب النشاط
    icons = {
        'watch_ad': '📺',
        'daily_checkin': '✅',
        'wheel_spin': '🎡',
        'withdraw_request': '💳',
        'new_user': '🆕'
    }
    icon = icons.get(action, '🔔')
    
    # تجهيز الرسالة
    message = f"{icon} **نشاط جديد في الموقع**\n\n"
    message += f"👤 **المستخدم:** {name}\n"
    message += f"🆔 **المعرف:** `{user_id}`\n"
    message += f"⚡ **الإجراء:** {action}\n"
    message += f"📝 **التفاصيل:** {details}\n"
    message += f"💰 **الرصيد الحالي:** {points}\n"
    message += f"🕐 **الوقت:** {datetime.now().strftime('%H:%M:%S')}"
    
    # أزرار التحكم السريع
    keyboard = [
        [
            InlineKeyboardButton("👤 عرض المستخدم", callback_data=f"view_{user_id}"),
            InlineKeyboardButton("💰 تعديل الرصيد", callback_data=f"points_{user_id}")
        ],
        [
            InlineKeyboardButton("🚫 حظر", callback_data=f"ban_{user_id}"),
            InlineKeyboardButton("✅ إلغاء حظر", callback_data=f"unban_{user_id}")
        ]
    ]
    
    # إرسال لكل المشرفين
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                admin_id,
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        except:
            pass

# =========== أوامر التحكم للمشرفين ===========
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """لوحة تحكم المشرف"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ هذا الأمر للمشرفين فقط")
        return
    
    keyboard = [
        [InlineKeyboardButton("👥 كل المستخدمين", callback_data='list_users_1')],
        [InlineKeyboardButton("💰 إدارة النقاط", callback_data='points_menu')],
        [InlineKeyboardButton("🚫 إدارة الحظر", callback_data='ban_menu')],
        [InlineKeyboardButton("💳 طلبات السحب", callback_data='withdrawals')],
        [InlineKeyboardButton("📊 إحصائيات", callback_data='stats')],
    ]
    
    await update.message.reply_text(
        "🔰 **لوحة تحكم المشرف**\n\n"
        "اختر ما تريد:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def view_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض معلومات مستخدم"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ غير مصرح")
        return
    
    try:
        target = int(context.args[0])
        
        conn = sqlite3.connect('profit_bot.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE user_id=?", (target,))
        user = c.fetchone()
        
        if not user:
            await update.message.reply_text("❌ المستخدم غير موجود")
            return
        
        # جلب المحافظ
        c.execute("SELECT wallet_type, wallet_number FROM wallets WHERE user_id=?", (target,))
        wallets = c.fetchall()
        
        # جلب طلبات السحب
        c.execute("SELECT amount, status, request_date FROM withdrawals WHERE user_id=? ORDER BY request_date DESC LIMIT 3", (target,))
        withdrawals = c.fetchall()
        
        conn.close()
        
        status = "✅ نشط" if not user[9] else f"🚫 محظور ({user[10]})"
        
        text = f"👤 **معلومات المستخدم**\n\n"
        text += f"🆔 **المعرف:** `{user[0]}`\n"
        text += f"📝 **الاسم:** {user[2]}\n"
        text += f"🔰 **اليوزر:** @{user[1] if user[1] else 'لا يوجد'}\n"
        text += f"💰 **النقاط:** {user[3]}\n"
        text += f"📊 **إجمالي الأرباح:** {user[4]}\n"
        text += f"📅 **التسجيل:** {user[5][:10]}\n"
        text += f"👥 **الدعوات:** {user[7]}\n"
        text += f"🔰 **الحالة:** {status}\n\n"
        
        if wallets:
            text += "💳 **المحافظ:**\n"
            for w in wallets:
                text += f"• {w[0]}: `{w[1]}`\n"
        
        if withdrawals:
            text += "\n📋 **آخر طلبات السحب:**\n"
            for w in withdrawals:
                text += f"• {w[0]} جنيه - {w[1]} ({w[2][:10]})\n"
        
        await update.message.reply_text(text, parse_mode='Markdown')
        
    except IndexError:
        await update.message.reply_text("❌ استخدم: /user [معرف المستخدم]")

async def add_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إضافة نقاط لمستخدم"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ غير مصرح")
        return
    
    try:
        target = int(context.args[0])
        points = int(context.args[1])
        reason = ' '.join(context.args[2:]) if len(context.args) > 2 else "مكافأة"
        
        success, new_points, msg = update_points(target, points)
        
        if success:
            log_admin_action(user_id, "إضافة نقاط", target, f"{points} نقطة - {reason}")
            
            # إبلاغ المستخدم
            try:
                await context.bot.send_message(
                    target,
                    f"🎁 **تم إضافة {points} نقطة إلى رصيدك!**\n"
                    f"السبب: {reason}\n"
                    f"💰 رصيدك الآن: {new_points}",
                    parse_mode='Markdown'
                )
            except:
                pass
            
            await update.message.reply_text(f"✅ تم إضافة {points} نقاط\nالرصيد الجديد: {new_points}")
        else:
            await update.message.reply_text(f"❌ فشل: {msg}")
            
    except (IndexError, ValueError):
        await update.message.reply_text("❌ استخدم: /add [المعرف] [النقاط] [السبب]")

async def remove_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """خصم نقاط من مستخدم"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ غير مصرح")
        return
    
    try:
        target = int(context.args[0])
        points = int(context.args[1])
        reason = ' '.join(context.args[2:]) if len(context.args) > 2 else "مخالفة"
        
        success, new_points, msg = update_points(target, -points)
        
        if success:
            log_admin_action(user_id, "خصم نقاط", target, f"{points} نقطة - {reason}")
            
            # إبلاغ المستخدم
            try:
                await context.bot.send_message(
                    target,
                    f"⚠️ **تم خصم {points} نقطة من رصيدك**\n"
                    f"السبب: {reason}\n"
                    f"💰 رصيدك الآن: {new_points}",
                    parse_mode='Markdown'
                )
            except:
                pass
            
            await update.message.reply_text(f"✅ تم خصم {points} نقاط\nالرصيد الجديد: {new_points}")
        else:
            await update.message.reply_text(f"❌ فشل: {msg}")
            
    except (IndexError, ValueError):
        await update.message.reply_text("❌ استخدم: /remove [المعرف] [النقاط] [السبب]")

async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حظر مستخدم"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ غير مصرح")
        return
    
    try:
        target = int(context.args[0])
        reason = ' '.join(context.args[1:]) if len(context.args) > 1 else "مخالفة القواعد"
        
        conn = sqlite3.connect('profit_bot.db')
        c = conn.cursor()
        c.execute("UPDATE users SET is_banned=1, ban_reason=? WHERE user_id=?", (reason, target))
        conn.commit()
        conn.close()
        
        log_admin_action(user_id, "حظر", target, reason)
        
        # إبلاغ المستخدم
        try:
            await context.bot.send_message(
                target,
                f"🚫 **تم حظرك من البوت**\n"
                f"السبب: {reason}",
                parse_mode='Markdown'
            )
        except:
            pass
        
        await update.message.reply_text(f"✅ تم حظر المستخدم {target}")
        
    except (IndexError, ValueError):
        await update.message.reply_text("❌ استخدم: /ban [المعرف] [السبب]")

async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إلغاء حظر مستخدم"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ غير مصرح")
        return
    
    try:
        target = int(context.args[0])
        
        conn = sqlite3.connect('profit_bot.db')
        c = conn.cursor()
        c.execute("UPDATE users SET is_banned=0, ban_reason=NULL WHERE user_id=?", (target,))
        conn.commit()
        conn.close()
        
        log_admin_action(user_id, "إلغاء حظر", target, "")
        
        await update.message.reply_text(f"✅ تم إلغاء حظر المستخدم {target}")
        
    except (IndexError, ValueError):
        await update.message.reply_text("❌ استخدم: /unban [المعرف]")

async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض كل المستخدمين"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ غير مصرح")
        return
    
    conn = sqlite3.connect('profit_bot.db')
    c = conn.cursor()
    c.execute("SELECT user_id, first_name, points, is_banned FROM users ORDER BY points DESC LIMIT 20")
    users = c.fetchall()
    total = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()
    
    text = f"📋 **آخر 20 مستخدم** (الإجمالي: {total})\n\n"
    for user in users:
        status = "🚫" if user[3] else "✅"
        text += f"{status} `{user[0]}` - {user[1]} - {user[2]} نقطة\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def withdrawals_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض طلبات السحب المعلقة"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ غير مصرح")
        return
    
    conn = sqlite3.connect('profit_bot.db')
    c = conn.cursor()
    c.execute('''SELECT w.*, u.first_name FROM withdrawals w 
                 JOIN users u ON w.user_id = u.user_id 
                 WHERE w.status="قيد الانتظار" ORDER BY w.request_date''')
    withdrawals = c.fetchall()
    conn.close()
    
    if not withdrawals:
        await update.message.reply_text("✅ لا توجد طلبات سحب معلقة")
        return
    
    for w in withdrawals:
        keyboard = [
            [
                InlineKeyboardButton("✅ قبول", callback_data=f"approve_{w[0]}"),
                InlineKeyboardButton("❌ رفض", callback_data=f"reject_{w[0]}")
            ],
            [InlineKeyboardButton("👤 عرض المستخدم", callback_data=f"view_{w[1]}")]
        ]
        
        text = f"💳 **طلب سحب #{w[0]}**\n\n"
        text += f"👤 {w[10]}\n"
        text += f"💰 {w[2]} جنيه\n"
        text += f"💳 {w[3]}\n"
        text += f"📱 `{w[4]}`\n"
        text += f"🆔 `{w[5]}`\n"
        text += f"📅 {w[7][:16]}"
        
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الأزرار"""
    query = update.callback_query
    await query.answer()
    
    admin_id = query.from_user.id
    if admin_id not in ADMIN_IDS:
        await query.edit_message_text("⛔ غير مصرح")
        return
    
    data = query.data
    
    if data.startswith('view_'):
        user_id = int(data.replace('view_', ''))
        # عرض المستخدم (هننفذها بعدين)
        await query.edit_message_text(f"جاري عرض المستخدم {user_id}...")
    
    elif data.startswith('ban_'):
        user_id = int(data.replace('ban_', ''))
        conn = sqlite3.connect('profit_bot.db')
        c = conn.cursor()
        c.execute("UPDATE users SET is_banned=1 WHERE user_id=?", (user_id,))
        conn.commit()
        conn.close()
        await query.edit_message_text(f"✅ تم حظر المستخدم {user_id}")
    
    elif data.startswith('unban_'):
        user_id = int(data.replace('unban_', ''))
        conn = sqlite3.connect('profit_bot.db')
        c = conn.cursor()
        c.execute("UPDATE users SET is_banned=0 WHERE user_id=?", (user_id,))
        conn.commit()
        conn.close()
        await query.edit_message_text(f"✅ تم إلغاء حظر المستخدم {user_id}")
    
    elif data.startswith('approve_'):
        withdraw_id = int(data.replace('approve_', ''))
        # كود قبول السحب
        await query.edit_message_text(f"✅ تم قبول الطلب #{withdraw_id}")
    
    elif data.startswith('reject_'):
        withdraw_id = int(data.replace('reject_', ''))
        # كود رفض السحب مع إعادة النقاط
        await query.edit_message_text(f"❌ تم رفض الطلب #{withdraw_id}")

# =========== أوامر المستخدمين ===========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر بدء البوت"""
    user = update.effective_user
    user_id = user.id
    username = user.username or ""
    first_name = user.first_name or "مستخدم"
    
    referrer_id = None
    if context.args and context.args[0].isdigit():
        referrer_id = int(context.args[0])
    
    create_user(user_id, username, first_name, referrer_id)
    
    # إشعار للمشرف بمستخدم جديد
    await notify_admin(context, user_id, 'new_user', f'مستخدم جديد')
    
    points = get_user_points(user_id)
    
    keyboard = [
        [InlineKeyboardButton("📺 مشاهدة إعلان", url="https://your-app.railway.app")],
        [InlineKeyboardButton("💰 رصيدي", callback_data='balance')],
        [InlineKeyboardButton("💳 سحب أرباح", callback_data='withdraw')]
    ]
    
    if user_id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("⚙️ لوحة التحكم", callback_data='admin')])
    
    await update.message.reply_text(
        f"🎉 أهلاً بك يا {first_name}!\n\n"
        f"💰 رصيدك: {points} نقطة\n"
        f"📱 استخدم الموقع لمشاهدة الإعلانات",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =========== تشغيل البوت ===========
def main():
    if not TOKEN:
        print("❌ خطأ: لم يتم تعيين BOT_TOKEN")
        return
    
    init_db()
    app = Application.builder().token(TOKEN).build()
    
    # أوامر المشرفين
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("user", view_user))
    app.add_handler(CommandHandler("add", add_points))
    app.add_handler(CommandHandler("remove", remove_points))
    app.add_handler(CommandHandler("ban", ban_user))
    app.add_handler(CommandHandler("unban", unban_user))
    app.add_handler(CommandHandler("users", list_users))
    app.add_handler(CommandHandler("withdrawals", withdrawals_list))
    
    # أوامر المستخدمين
    app.add_handler(CommandHandler("start", start))
    
    # معالجة الأزرار
    app.add_handler(CallbackQueryHandler(handle_callback))
    
    print("✅ البوت يعمل بنجاح...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
