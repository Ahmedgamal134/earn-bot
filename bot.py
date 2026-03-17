import sqlite3
from datetime import datetime
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
    c.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, points INTEGER DEFAULT 0)")
    c.execute("CREATE TABLE IF NOT EXISTS daily_checkin (user_id INTEGER, check_date TEXT)")
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
    c.execute("INSERT OR IGNORE INTO users (user_id, points) VALUES (?, 0)", (user_id,))
    c.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (points_to_add, user_id))
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
    c.execute("INSERT INTO daily_checkin (user_id, check_date) VALUES (?, ?)", (user_id, today))
    conn.commit()
    conn.close()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    update_points(user_id, 0)
    
    points = get_user_points(user_id)
    name = user.first_name or "User"
    
    msg = "Welcome " + name + "!"
    msg = msg + " Points: " + str(points)
    
    keyboard = [
        [InlineKeyboardButton("Mini App", web_app=WebAppInfo(url=MINI_APP_URL))],
        [InlineKeyboardButton("Daily", callback_data='daily'), InlineKeyboardButton("Balance", callback_data='balance')],
        [InlineKeyboardButton("Refer", callback_data='refer'), InlineKeyboardButton("Withdraw", callback_data='withdraw')]
    ]
    
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    
    if data == 'daily':
        if can_checkin(user_id):
            add_checkin(user_id)
            update_points(user_id, 5)
            points = get_user_points(user_id)
            msg = "Daily checkin OK! +5 points. Total: " + str(points)
            await query.edit_message_text(msg)
        else:
            await query.edit_message_text("Daily already done today")
    
    elif data == 'balance':
        points = get_user_points(user_id)
        msg = "Balance: " + str(points) + " points"
        await query.edit_message_text(msg)

async def webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = update.message.text
    
    if "watch_ad" in data:
        update_points(user_id, 5)
        await update.message.reply_text("Ad watched +5 points")
    
    elif "wheel_" in data:
        parts = data.split("_")
        if len(parts) > 1:
            try:
                reward = int(parts[1])
                update_points(user_id, reward)
                await update.message.reply_text("Wheel win + " + str(reward) + " points")
            except:
                pass

def main():
    if not TOKEN:
        print("No TOKEN")
        return
    
    init_db()
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, webapp_data))
    
    print("Bot started")
    app.run_polling()

if __name__ == "__main__":
    main()
