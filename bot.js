require('dotenv').config();
const TelegramBot = require('node-telegram-bot-api');
const mongoose = require('mongoose');
const express = require('express');

const app = express();

// اتصال بقاعدة البيانات
mongoose.connect(process.env.MONGO_URI, {
  useNewUrlParser: true,
  useUnifiedTopology: true
}).then(() => console.log("✅ Connected to MongoDB"))
  .catch(err => console.error("❌ MongoDB connection error:", err));

// إعداد البوت
const bot = new TelegramBot(process.env.TELEGRAM_TOKEN, { polling: true });

// مثال: أمر /start
bot.onText(/\/start/, (msg) => {
  const chatId = msg.chat.id;
  bot.sendMessage(chatId, "أهلاً بيك في البوت 🚀");
});

// مثال: أمر /admin
bot.onText(/\/admin/, (msg) => {
  if (msg.from.id.toString() === process.env.ADMIN_ID) {
    bot.sendMessage(msg.chat.id, "أنت الأدمن ✅");
  } else {
    bot.sendMessage(msg.chat.id, "معندكش صلاحية ❌");
  }
});

// تشغيل السيرفر
app.listen(3000, () => {
  console.log("🚀 Server running on port 3000");
});
