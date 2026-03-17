"""
PROFIT BOT v2.0 - Production Ready
Deployed on Railway - March 2026
"""

import logging
import sqlite3
import aiosqlite
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
ADMIN_IDS = [1103784347]  # معرفك
DB = "profit_bot.db"
MINI_APP_URL = "https://earn-mini-appuprailwayapp-production.up.railway.app/"

class DatabaseManager:
    def __init__(self, db_path):
        self.db_path = db_path
    
    async def get_connection(self):
        return await aiosqlite.connect(self.db_path)
    
    async def init_db(self):
        async with self.get_connection() as conn:
            await conn.execute('''CREATE TABLE IF NOT EXISTS users
                (user_id INTEGER PRIMARY KEY,
                 username TEXT, first_name TEXT, points INTEGER DEFAULT 0,
                 total_earned INTEGER DEFAULT 0, joined_date TEXT,
                 referrer_id INTEGER DEFAULT NULL, total_referrals INTEGER DEFAULT 0,
                 referral_earned INTEGER DEFAULT 0, is_banned INTEGER DEFAULT 0,
                 last_active TEXT)''')
            await conn.execute('''CREATE TABLE IF NOT EXISTS ads
                (user_id INTEGER, ad_date TEXT, ad_count INTEGER DEFAULT 0,
                 UNIQUE(user_id, ad_date))''')
            await conn.execute('''CREATE TABLE IF NOT EXISTS daily_checkin
                (user_id INTEGER, check_date TEXT, streak INTEGER DEFAULT 1,
                 UNIQUE(user_id, check_date))''')
            await conn.execute('''CREATE TABLE IF NOT EXISTS withdrawals
                (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
                 amount INTEGER, wallet_type TEXT, status TEXT DEFAULT 'قيد الانتظار',
                 request_date TEXT)''')
            await conn.commit()
        logging.info("✅ قاعدة البيانات جاهزة - Production Mode")

db = DatabaseManager(DB)

# ================= DATABASE HELPERS =================
async def get_user_points(user_id: int) -> int:
    async with db.get_connection() as conn:
        cursor = await conn.execute("SELECT points FROM users WHERE user_id=?", (user_id,))
        result = await cursor.fetchone()
        return result[0] if result else 0

async def update_points(user_id: int, points_to_add: int):
    async with db.get_connection() as conn:
        await conn.execute(
            "UPDATE users SET points=points+?, total_earned=total_earned+?, last_active=? WHERE user_id=?",
            (points_to_add, points_to_add, datetime.now().isoformat(), user_id)
        )
        await conn.commit()

async def can_checkin(user_id: int) -> bool:
    today = datetime.now().strftime('%Y-%m-%d')
    async with db.get_connection() as conn:
        cursor = await conn.execute(
            "SELECT 1 FROM daily_checkin WHERE user_id=? AND check_date=?", 
            (user_id, today)
        )
        return not await cursor.fetchone()

async def add_checkin(user_id: int) -> int:
    today = datetime.now().strftime('%Y-%m-%d')
    async with db.get_connection() as conn:
        cursor = await conn.execute(
            "SELECT check_date, streak FROM daily_checkin WHERE user_id=? ORDER BY check_date DESC LIMIT 1", 
            (user_id,)
        )
        last = await cursor.fetchone()
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        streak = last[1] + 1 if last and last[0] == yesterday else 1
        
        await conn.execute("INSERT INTO daily_checkin(user_id, check_date, streak) VALUES(?,?,?)",
                          (user_id, today, streak))
        await conn.commit()
        return streak

# ================= COMMANDS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    # تسجيل المستخدم الجديد
    async with db.get_connection() as conn:
        await conn.execute(
            "INSERT OR IGNORE INTO users(user_id, username, first_name, joined_date, last_active) VALUES(?,?,?,?,?)",
            (user_id, user.username or "غير محدد", user.first_name or "مستخدم",
             datetime.now().strftime('%Y-%m-%d'), datetime.now().isoformat())
        )
        await conn.commit()
    
    points = await get_user_points(user_id)
    
    # القائمة الرئيسية الاحترافية
    keyboard = [
        [InlineKeyboardButton("🚀 الدخول للـ Mini App", web_app=WebAppInfo(url=MINI_APP_URL))],
        [InlineKeyboardButton("✅ تسجيل يومي", callback_data='daily_checkin'),
         InlineKeyboardButton("💰 رصيدي", callback_data='balance')],
        [InlineKeyboardButton("👥 دعوة أصدقاء", callback_data='referral'),
         InlineKeyboardButton("💳 سحب الأرباح", callback_data='withdraw')],
    ]
    if user_id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("⚙️ لوحة الإدارة", callback_data='admin_panel')])
    
    await update.message.reply_text(
        f"🎉 **أهلاً بك {user.first_name or 'مستخدم'}!**

"
        f"💰 **نقاطك الحالية:** `{points}` نقطة

"
        f"📱 **استخدم Mini App لكسب المزيد!**
"
        f"⚡ **شاهد إعلانات | عجلة الحظ | مهام يومية**",
        reply_markup=InlineKeyboardMarkup(keyboard), 
        parse_mode='Markdown'
    )

# ================= CALLBACK BUTTONS =================
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    # تسجيل يومي
    if data == 'daily_checkin':
        if await can_checkin(user_id):
            streak = await add_checkin(user_id)
            points_reward = 5 * streak
            await update_points(user_id, points_reward)
            points = await get_user_points(user_id)
            
            await query.edit_message_text(
                f"✅ **تم تسجيل الدخول اليومي!**

"
                f"🔥 **سلسلة:** `{streak}` يوم
"
                f"💰 **مكافأة:** `{points_reward}` نقطة
"
                f"📊 **إجمالي نقاطك:** `{points}`

"
                f"🎯 **استمر في الحضور اليومي لمكافآت أكبر!**",
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text("❌ **لقد سجلت الدخول اليوم بالفعل!**

⏳ **عد غداً للحصول على مكافأتك الجديدة**")
    
    # رصيد
    elif data == 'balance':
        points = await get_user_points(user_id)
        await query.edit_message_text(
            f"💰 **رصيدك الحالي:**

"
            f"`{points}` **نقطة**

"
            f"📌 **الحد الأدنى للسحب: 100 نقطة**",
            parse_mode='Markdown'
        )
    
    # دعوة أصدقاء
    elif data == 'referral':
        bot_username = context.bot.username
        ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
        await query.edit_message_text(
            f"👥 **نظام الدعوة الخاص بك:**

"
            f"🔗 **رابط الدعوة:**
"
            f"`{ref_link}`

"
            f"💰 **ستحصل على 10% من أرباح المدعوين!**
"
            f"📈 **كلما دعوت أكثر = كسبت أكثر**",
            parse_mode='Markdown'
        )
    
    # سحب الأرباح
    elif data == 'withdraw':
        points = await get_user_points(user_id)
        keyboard = [
            [InlineKeyboardButton("💳 فاوصة", callback_data='withdraw_fawry')],
            [InlineKeyboardButton("💰 فودافون كاش", callback_data='withdraw_vodafone')],
            [InlineKeyboardButton("◀️ رجوع", callback_data='back_main')]
        ]
        await query.edit_message_text(
            f"💳 **اختر طريقة السحب:**

"
            f"💰 **رصيدك:** `{points}` نقطة
"
            f"📌 **الحد الأدنى:** `100` نقطة",
            reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
        )

# ================= WEBAPP DATA (Mini App) =================
async def webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = update.message.text.strip()
    
    if data.startswith("watch_ad"):
        await update_points(user_id, 5)
        await update.message.reply_text(
            "✅ **شكراً لمشاهدتك الإعلان!**

"
            f"💰 **تم إضافة 5 نقاط** لرصيدك!",
            parse_mode='Markdown'
        )
    
    elif data.startswith("wheel_"):
        try:
            reward = int(data.split("_")[1])
            await update_points(user_id, reward)
            await update.message.reply_text(
                f"🎉 **مبروك الفوز!**

"
                f"💰 **حصلت على {reward} نقطة** من عجلة الحظ!",
                parse_mode='Markdown'
            )
        except:
            pass
    
    elif data.startswith("checkin"):
        streak = await add_checkin(user_id)
        await update_points(user_id, 5 * streak)
        await update.message.reply_text(
            f"✅ **تسجيل يومي ناجح!**
"
            f"🔥 سلسلة: {streak} يوم
"
            f"💰 مكافأة: {5 * streak} نقطة",
            parse_mode='Markdown'
        )

# ================= ADMIN PANEL =================
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    async with db.get_connection() as conn:
        cursor = await conn.execute("SELECT COUNT(*) FROM users")
        total_users = (await cursor.fetchone())[0]
        
        cursor = await conn.execute("SELECT SUM(points) FROM users")
        total_points = (await cursor.fetchone())[0] or 0
    
    await query.edit_message_text(
        f"⚙️ **لوحة الإدارة - Production Stats**

"
        f"👥 **إجمالي المستخدمين:** `{total_users}`
"
        f"💰 **إجمالي النقاط:** `{total_points}`
"
        f"🕐 **آخر تحديث:** `{datetime.now().strftime('%Y-%m-%d %H:%M')}`",
        parse_mode='Markdown'
    )

async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    
    async with db.get_connection() as conn:
        cursor = await conn.execute(
            "SELECT user_id, first_name, points FROM users ORDER BY points DESC LIMIT 10"
        )
        top_users = await cursor.fetchall()
    
    msg = "🏆 **أفضل 10 مستخدمين:**

"
    for i, (uid, name, points) in enumerate(top_users, 1):
        msg += f"{i}. **{name}** - `{points}` نقطة
"
    
    await update.message.reply_text(msg, parse_mode='Markdown')

# ================= MAIN PRODUCTION ENTRY =================
async def main():
    if not TOKEN:
        logging.error("❌ BOT_TOKEN غير موجود في Environment Variables")
        return
    
    # Initialize Production Database
    await db.init_db()
    
    # Production Bot Application
    app = Application.builder().token(TOKEN).build()
    
    # Production Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback, pattern='^(daily_checkin|balance|referral|withdraw|admin_panel)'))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), webapp_data))
    app.add_handler(CommandHandler("users", admin_users))
    
    logging.info("🚀 PROFIT BOT v2.0 - PRODUCTION READY")
    logging.info(f"🌐 Mini App: {MINI_APP_URL}")
    await app.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
