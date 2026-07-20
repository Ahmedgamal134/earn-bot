const TelegramBot = require('node-telegram-bot-api');
const fs = require('fs');

// ضع التوكن بتاع البوت في متغير البيئة BOT_TOKEN
const token = process.env.BOT_TOKEN;
const bot = new TelegramBot(token, { polling: true });

let users = JSON.parse(fs.readFileSync('users.json'));

function saveUsers() {
  fs.writeFileSync('users.json', JSON.stringify(users, null, 2));
}

// أمر البداية
bot.onText(/\/start/, (msg) => {
  const chatId = msg.chat.id;

  // لو المستخدم مش موجود في قاعدة البيانات، أضفه
  if (!users.find(u => u.id === chatId)) {
    users.push({ id: chatId, points: 0, invites: 0 });
    saveUsers();
  }

  // رسالة الترحيب + زر فتح التطبيق
  bot.sendMessage(chatId, "🔥 أهلاً بيك في البوت الربحي! افتح التطبيق من هنا:", {
    reply_markup: {
      inline_keyboard: [
        [
          { 
            text: "فتح التطبيق", 
            web_app: { url: "https://ahmedgamal134.github.io/earn-bot/" } 
          }
        ]
      ]
    }
  });
});
