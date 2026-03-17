import sqlite3
from datetime import datetime
import os
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

TOKEN = os.environ.get('BOT_TOKEN')
DB = "profit_bot.db"
MINI_APP_URL = "https://earn-mini-appuprailwayapp-production.up.railway.app/"

def init_db():
    conn = sqlite3.connect(DB, check_same_thread=False)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, points INTEGER DEFAULT 0)")
    c.execute("CREATE TABLE IF NOT EXISTS daily_checkin (user_id INTEGER, check_date TEXT, UNIQUE(user_id, check_date))")
    conn.commit()
    conn.close()

def get_points(user_id):
    conn = sqlite3.connect(DB, check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT points FROM users WHERE user_id=?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 0

def add_points(user_id, amount):
    conn = sqlite3.connect(DB, check_same_thread=False)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, points) VALUES (?, 0)", (user_id,))
    c.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (amount, user_id))
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

def do_checkin(user_id):
    today = datetime.now().strftime('%Y-%m-%d')
    conn = sqlite3.connect(DB, check_same_thread=False)
    c = conn.cursor()
    c.execute("INSERT INTO daily_checkin (user_id, check_date) VALUES (?, ?)", (user_id, today))
    conn.commit()
    conn.close()

def start(update, context):
    user_id = update.message.from_user.id
    points = get_points(user_id)
    
    keyboard = [
        [InlineKeyboardButton("Mini App", web_app=WebAppInfo(url=MINI_APP_URL))],
        [InlineKeyboardButton("Daily Check", callback_data='daily')],
        [InlineKeyboardButton("My Balance", callback_data='balance')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("Welcome! Points: " + str(points), reply_markup=reply_markup)

def button_callback(update, context):
    query = update.callback_query
    query.answer()
    user_id = query.from_user.id
    data = query.data
    
    if data == 'daily':
        if can_checkin(user_id):
            do_checkin(user_id)
            add_points(user_id, 5)
            points = get_points(user_id)
            query.edit_message_text("Daily check OK! +5 points. Total: " + str(points))
        else:
            query.edit_message_text("Daily check already done today")
    
    elif data == 'balance':
        points = get_points(user_id)
        query.edit_message_text("Your balance: " + str(points) + " points")

def handle_message(update, context):
    user_id = update.message.from_user.id
    data = update.message.text
    
    if "watch_ad" in data:
        add_points(user_id, 5)
        update.message.reply_text("Ad watched! +5 points")
    
    elif "wheel_" in data:
        try:
            parts = data.split("_")
            reward = int(parts[1])
            add_points(user_id, reward)
            update.message.reply_text("Wheel win! +" + str(reward) + " points")
        except:
            pass

def main():
    if not TOKEN:
        print("No BOT_TOKEN found")
        return
    
    init_db()
    updater = Updater(token=TOKEN, use_context=True)
    dp = updater.dispatcher
    
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(button_callback))
    dp.add_handler(MessageHandler(None, handle_message))
    
    print("Bot started successfully!")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
