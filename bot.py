import logging
import sqlite3
from datetime import datetime
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

logging.basicConfig(
format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
level=logging.INFO
)

TOKEN = os.environ.get("BOT_TOKEN")

ADMIN_IDS = [1103784347]

DB = "profit_bot.db"

# ---------------- DATABASE ----------------

def init_db():

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users(
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        points INTEGER DEFAULT 0,
        joined_date TEXT,
        referrer INTEGER
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS ads(
        user_id INTEGER,
        ad_date TEXT,
        ad_count INTEGER DEFAULT 0,
        UNIQUE(user_id, ad_date)
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS checkin(
        user_id INTEGER,
        check_date TEXT,
        UNIQUE(user_id, check_date)
    )
    """)

    conn.commit()
    conn.close()


# ---------------- FUNCTIONS ----------------

def get_points(user_id):

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("SELECT points FROM users WHERE user_id=?", (user_id,))
    r = c.fetchone()

    conn.close()

    return r[0] if r else 0


def add_points(user_id, amount):

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("UPDATE users SET points = points + ? WHERE user_id=?", (amount, user_id))

    conn.commit()
    conn.close()


def add_ad(user_id):

    today = datetime.now().strftime("%Y-%m-%d")

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("SELECT ad_count FROM ads WHERE user_id=? AND ad_date=?", (user_id, today))
    r = c.fetchone()

    if r:
        c.execute("UPDATE ads SET ad_count = ad_count + 1 WHERE user_id=? AND ad_date=?", (user_id, today))
    else:
        c.execute("INSERT INTO ads VALUES(?,?,1)", (user_id, today))

    conn.commit()
    conn.close()


def can_checkin(user_id):

    today = datetime.now().strftime("%Y-%m-%d")

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("SELECT * FROM checkin WHERE user_id=? AND check_date=?", (user_id, today))

    r = c.fetchone()

    conn.close()

    return r is None


def add_checkin(user_id):

    today = datetime.now().strftime("%Y-%m-%d")

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("INSERT INTO checkin VALUES(?,?)", (user_id, today))

    conn.commit()
    conn.close()


# ---------------- START ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user
    ref = None

    if context.args:
        ref = int(context.args[0])

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("""
    INSERT OR IGNORE INTO users(user_id,username,first_name,joined_date,referrer)
    VALUES(?,?,?,?,?)
    """,
    (
        user.id,
        user.username,
        user.first_name,
        datetime.now().strftime("%Y-%m-%d"),
        ref
    ))

    conn.commit()
    conn.close()

    points = get_points(user.id)

    keyboard = [

        [
            InlineKeyboardButton(
                "🚀 فتح التطبيق",
                web_app=WebAppInfo(
                    url="https://earn-mini-appuprailwayapp-production.up.railway.app/"
                )
            )
        ],

        [
            InlineKeyboardButton(
                "💰 رصيدي",
                callback_data="balance"
            )
        ]

    ]

    await update.message.reply_text(

f"""
🎉 أهلاً {user.first_name}

💰 رصيدك: {points} نقطة
""",

reply_markup=InlineKeyboardMarkup(keyboard)

)


# ---------------- BALANCE ----------------

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    points = get_points(user_id)

    await query.edit_message_text(f"💰 رصيدك: {points} نقطة")


# ---------------- MINI APP HANDLER ----------------

async def webapp(update: Update, context: ContextTypes.DEFAULT_TYPE):

    data = update.message.web_app_data.data
    user_id = update.effective_user.id

    # مشاهدة اعلان

    if data == "watch_ad":

        add_ad(user_id)
        add_points(user_id, 1)

        await update.message.reply_text("📺 تمت مشاهدة الإعلان +1 نقطة")

    # تسجيل يومي

    elif data == "checkin":

        if not can_checkin(user_id):

            await update.message.reply_text("🎁 سجلت اليوم بالفعل")

            return

        add_checkin(user_id)

        add_points(user_id, 5)

        await update.message.reply_text("🎁 تسجيل يومي +5 نقاط")

    # الرصيد

    elif data == "balance":

        points = get_points(user_id)

        await update.message.reply_text(f"💰 رصيدك: {points}")

    # عجلة الحظ

    elif data.startswith("wheel_"):

        reward = int(data.split("_")[1])

        add_points(user_id, reward)

        await update.message.reply_text(f"🎡 ربحت {reward} نقاط")

    # دعوة الاصدقاء

    elif data == "refer":

        bot = await context.bot.get_me()

        link = f"https://t.me/{bot.username}?start={user_id}"

        await update.message.reply_text(f"👥 رابط الدعوة:\n{link}")


# ---------------- ADMIN ----------------

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id not in ADMIN_IDS:
        return

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM users")
    users = c.fetchone()[0]

    c.execute("SELECT SUM(points) FROM users")
    points = c.fetchone()[0]

    conn.close()

    await update.message.reply_text(

f"""
📊 الإحصائيات

👥 المستخدمين: {users}

💰 مجموع النقاط: {points}
"""

)


# ---------------- MAIN ----------------

def main():

    if not TOKEN:
        print("❌ BOT TOKEN NOT FOUND")
        return

    init_db()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(CommandHandler("stats", stats))

    app.add_handler(CallbackQueryHandler(balance, pattern="balance"))

    app.add_handler(
        MessageHandler(
            filters.StatusUpdate.WEB_APP_DATA,
            webapp
        )
    )

    print("✅ BOT RUNNING")

    app.run_polling()


if __name__ == "__main__":
    main()
