const TelegramBot = require('node-telegram-bot-api');
const fs = require('fs');
const token = process.env.BOT_TOKEN;
const bot = new TelegramBot(token, { polling: true });

let users = JSON.parse(fs.readFileSync('users.json'));

function saveUsers() {
  fs.writeFileSync('users.json', JSON.stringify(users, null, 2));
}

bot.onText(/\/start/, (msg) => {
  const chatId = msg.chat.id;
  if (!users.find(u => u.id === chatId)) {
    users.push({ id: chatId, points: 0, invites: 0 });
    saveUsers();
  }
  bot.sendMessage(chatId, "🔥 أهلاً بيك في البوت الربحي! افتح التطبيق من هنا:", {
    reply_markup: {
      inline_keyboard: [[{ text: "فتح التطبيق", web_app: { url: "https://username.github.io/earn-bot-miniapp/" } }]]
    }
  });
});
