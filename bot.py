import logging
import sqlite3
from datetime import datetime
import os
import asyncio

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo
)

from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)

# ---------------- CONFIG ----------------

TOKEN = os.environ.get("BOT_TOKEN")

ADMIN_IDS = [1103784347]

DB = "profit_bot.db"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

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
        joined_date TEXT
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

    conn.commit()
    conn.close()


# ---------------- FUNCTIONS ----------------

def get_points(user_id):

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute(
        "SELECT points FROM users WHERE user_id=?",
        (user_id,)
    )

    result = c.fetchone()

    conn.close()

    return result[0] if result else 0


def add_points(user_id, amount):

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute(
        "UPDATE users SET points = points + ? WHERE user_id=?",
        (amount, user_id)
    )

    conn.commit()
    conn.close()


def add_ad_watch(user_id):

    today = datetime.now().strftime("%Y-%m-%d")

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute(
        "SELECT ad_count FROM ads WHERE user_id=? AND ad_date=?",
        (user_id, today)
    )

    result = c.fetchone()

    if result:

        c.execute(
            "UPDATE ads SET ad_count = ad_count + 1 WHERE user_id=? AND ad_date=?",
            (user_id, today)
        )

    else:

        c.execute(
            "INSERT INTO ads VALUES(?,?,1)",
            (user_id, today)
        )

    conn.commit()
    conn.close()


# ---------------- START ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("""
    INSERT OR IGNORE INTO users(user_id,username,first_name,joined_date)
    VALUES(?,?,?,?)
    """,
    (
        user.id,
        user.username,
        user.first_name,
        datetime.now().strftime("%Y-%m-%d")
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
🎉 أهلا {user.first_name}

💰 رصيدك : {points} نقطة
        """,

        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ---------------- BUTTONS ----------------

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    points = get_points(user_id)

    await query.edit_message_text(
        f"💰 رصيدك الحالي: {points} نقطة"
    )


# ---------------- MINI APP DATA ----------------

async def webapp_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    data = update.message.web_app_data.data
    user_id = update.effective_user.id

    if data == "watch_ad":

        await update.message.reply_text("⏳ شاهد الإعلان لمدة 15 ثانية")

        await asyncio.sleep(15)

        add_ad_watch(user_id)

        add_points(user_id, 1)

        await update.message.reply_text("✅ تم إضافة +1 نقطة")

    elif data == "balance":

        points = get_points(user_id)

        await update.message.reply_text(
            f"💰 رصيدك: {points}"
        )

    elif data == "checkin":

        add_points(user_id, 5)

        await update.message.reply_text(
            "✅ تسجيل يومي +5 نقاط"
        )


# ---------------- ADMIN ----------------

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id not in ADMIN_IDS:
        return

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]

    c.execute("SELECT SUM(points) FROM users")
    total_points = c.fetchone()[0]

    conn.close()

    await update.message.reply_text(

        f"""
📊 الإحصائيات

👥 عدد المستخدمين: {total_users}

💰 مجموع النقاط: {total_points}
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

    app.add_handler(
        CallbackQueryHandler(
            balance,
            pattern="balance"
        )
    )

    app.add_handler(
        MessageHandler(
            filters.StatusUpdate.WEB_APP_DATA,
            webapp_handler
        )
    )

    print("✅ BOT RUNNING...")

    app.run_polling()


if __name__ == "__main__":
    main()
