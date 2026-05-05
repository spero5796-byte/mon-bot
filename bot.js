const { Client, GatewayIntentBits } = require('discord.js');

const client = new Client({
  intents: [GatewayIntentBits.Guilds]
});

client.once('ready', () => {
  console.log(`Bot connecté : ${client.user.tag}`);
  console.log("TOKEN =", process.env.DISCORD_TOKEN);
});

client.on('messageCreate', (message) => {
  if (message.author.bot) return;

  if (message.content === "!ping") {
    message.reply("Pong 🏓");
  }
});

client.login(process.env.DISCORD_TOKEN);
