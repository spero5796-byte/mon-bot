const { Client, GatewayIntentBits } = require("discord.js");
const sqlite3 = require("sqlite3").verbose();

const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.MessageContent,
    GatewayIntentBits.GuildMembers
  ]
});

const TOKEN = process.env.DISCORD_TOKEN;
const LOG_CHANNEL_ID = "1501172466251468812";

// 🚨 mots interdits
const badWords = [
  "pute", "fdp", "connard", "connasse", "enculé",
  "salope", "ntm", "nique", "porn", "xxx", "sex"
];

// 📦 DB
const db = new sqlite3.Database("./warns.db");

db.run(`
CREATE TABLE IF NOT EXISTS warns (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  userId TEXT,
  guildId TEXT,
  reason TEXT
)
`);

// 📌 LOGS
function log(guild, text) {
  const channel = guild.channels.cache.get(LOG_CHANNEL_ID);
  if (channel) channel.send(text);
}

// 🚨 ANTI SPAM
const spamMap = new Map();

client.on("messageCreate", async (message) => {
  if (message.author.bot) return;

  const userId = message.author.id;
  const now = Date.now();

  // spam detection
  if (!spamMap.has(userId)) {
    spamMap.set(userId, []);
  }

  const timestamps = spamMap.get(userId);
  timestamps.push(now);

  const recent = timestamps.filter(t => now - t < 5000);
  spamMap.set(userId, recent);

  if (recent.length > 5) {
    await message.delete();
    return message.channel.send(`⚠️ ${message.author} anti-spam activé`);
  }

  // 🚨 bad words
  const content = message.content.toLowerCase();
  const bad = badWords.find(w => content.includes(w));

  if (!bad) return;

  await message.delete();

  db.run(
    `INSERT INTO warns (userId, guildId, reason)
     VALUES (?, ?, ?)`,
    [message.author.id, message.guild.id, bad]
  );

  db.all(
    `SELECT * FROM warns WHERE userId = ? AND guildId = ?`,
    [message.author.id, message.guild.id],
    async (err, rows) => {

      const count = rows.length;
      const member = await message.guild.members.fetch(message.author.id);

      if (count === 1) {
        message.channel.send(`⚠️ ${message.author} avertissement`);

      } else if (count === 2) {
        await member.timeout(10 * 60 * 1000);
        message.channel.send(`🔇 mute 10 min`);

      } else if (count === 3) {
        await member.kick("3 warns");
        message.channel.send(`👢 kick`);

      } else if (count >= 4) {
        await member.ban({ reason: "4 warns" });
        message.channel.send(`🔨 ban`);
      }

      log(message.guild, `🚨 MODERATION\nUser: ${message.author.tag}\nMot: ${bad}`);
    }
  );
});

// 🛡️ ANTI RAID (joins massifs)
const joinMap = new Map();

client.on("guildMemberAdd", async (member) => {
  const guild = member.guild;
  const now = Date.now();

  if (!joinMap.has(guild.id)) {
    joinMap.set(guild.id, []);
  }

  const joins = joinMap.get(guild.id);
  joins.push(now);

  const recent = joins.filter(t => now - t < 10000);
  joinMap.set(guild.id, recent);

  if (recent.length > 5) {
    log(guild, "🚨 RAID DETECTÉ - activation protection");

    guild.members.cache.forEach(async (m) => {
      if (!m.user.bot) {
        try {
          await m.timeout(10 * 60 * 1000);
        } catch {}
      }
    });
  }
});

// 🤖 READY
client.once("ready", () => {
  console.log(`🤖 Bot anti-raid en ligne : ${client.user.tag}`);
});

client.login(TOKEN);
