const { 
  Client, 
  GatewayIntentBits, 
  PermissionFlagsBits 
} = require('discord.js');

const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.GuildMembers,
    GatewayIntentBits.MessageContent
  ]
});

// 📌 ID salon logs
const LOG_CHANNEL_ID = "1501172466251468812";

// 📊 warns en mémoire
const warns = new Map();

// 🔧 fonction logs
function log(guild, text) {
  const channel = guild.channels.cache.get(LOG_CHANNEL_ID);
  if (channel) channel.send(text);
}

client.once('ready', () => {
  console.log(`🤖 Bot connecté : ${client.user.tag}`);
});

client.on('messageCreate', async (message) => {
  if (message.author.bot) return;

  const args = message.content.split(" ");
  const command = args[0].toLowerCase();

  // 🔨 BAN
  if (command === "!ban") {
    if (!message.member.permissions.has(PermissionFlagsBits.BanMembers))
      return message.reply("❌ Pas la permission.");

    const user = message.mentions.members.first();
    const reason = args.slice(2).join(" ") || "Aucune raison";

    if (!user) return message.reply("❌ Mentionne un utilisateur.");

    await user.ban({ reason });

    message.reply(`🔨 ${user.user.tag} banni`);

    log(message.guild,
      `🔨 BAN\nUser: ${user.user.tag}\nMod: ${message.author.tag}\nRaison: ${reason}`
    );
  }

  // 👢 KICK
  if (command === "!kick") {
    if (!message.member.permissions.has(PermissionFlagsBits.KickMembers))
      return message.reply("❌ Pas la permission.");

    const user = message.mentions.members.first();
    const reason = args.slice(2).join(" ") || "Aucune raison";

    if (!user) return message.reply("❌ Mentionne un utilisateur.");

    await user.kick(reason);

    message.reply(`👢 ${user.user.tag} kick`);

    log(message.guild,
      `👢 KICK\nUser: ${user.user.tag}\nMod: ${message.author.tag}\nRaison: ${reason}`
    );
  }

  // ⚠️ WARN
  if (command === "!warn") {
    const user = message.mentions.users.first();
    const reason = args.slice(2).join(" ") || "Aucune raison";

    if (!user) return message.reply("❌ Mentionne un utilisateur.");

    if (!warns.has(user.id)) warns.set(user.id, []);
    warns.get(user.id).push(reason);

    message.reply(`⚠️ Warn donné à ${user.username}`);

    log(message.guild,
      `⚠️ WARN\nUser: ${user.username}\nMod: ${message.author.tag}\nRaison: ${reason}`
    );

    // auto ban 3 warns
    if (warns.get(user.id).length >= 3) {
      const member = message.guild.members.cache.get(user.id);
      if (member) await member.ban({ reason: "3 warns atteints" });

      log(message.guild,
        `🚨 AUTO-BAN\nUser: ${user.username}\nRaison: 3 warns`
      );
    }
  }

  // 🔇 MUTE (timeout)
  if (command === "!mute") {
    if (!message.member.permissions.has(PermissionFlagsBits.ModerateMembers))
      return message.reply("❌ Pas la permission.");

    const user = message.mentions.members.first();
    const time = parseInt(args[2]) || 10;

    if (!user) return message.reply("❌ Mentionne un utilisateur.");

    await user.timeout(time * 60 * 1000);

    message.reply(`🔇 ${user.user.tag} mute ${time} min`);

    log(message.guild,
      `🔇 MUTE\nUser: ${user.user.tag}\nMod: ${message.author.tag}\nDurée: ${time} min`
    );
  }
});

client.login(process.env.DISCORD_TOKEN);
