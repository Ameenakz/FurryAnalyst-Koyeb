import discord
from discord.ext import commands
from datetime import datetime, timedelta, timezone
import re


TOKEN = os.environ.get("DISCORD_TOKEN") 
CHANNEL_ID = 1446110269301588090  # Replace with your actual Channel ID

# Setup Bot
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')

@client.event
async def on_message(message):
    if message.content == '!report':
        await generate_daily_report(message.channel)

async def generate_daily_report(output_channel):
    target_channel = client.get_channel(CHANNEL_ID)
    
    if not target_channel:
        await output_channel.send("Error: Could not find the target channel.")
        return

    await output_channel.send("🔄 Analyzing chat history (Embeds) for the last 24 hours... please wait.")

    submissions = set()
    deliveries = set()
    
    # Time range: Last 24 Hours
    after_date = datetime.now(timezone.utc) - timedelta(hours=24)

    async for msg in target_channel.history(limit=500, after=after_date):
        # We need to look at both Plain Text AND Embeds
        content_to_check = msg.content

        # If the message has Embeds, add their Title and Description to the text we check
        if msg.embeds:
            for embed in msg.embeds:
                if embed.title:
                    content_to_check += " " + embed.title
                if embed.description:
                    content_to_check += " " + embed.description

        # --- LOGIC ---
        # Based on your screenshots: "Pet: Casper Submission alert" 
        
        # 1. Check for Submission
        if "Submission alert" in content_to_check:
            # Looks for text between "Pet:" and "Submission"
            # Handles bolding asterisks (**) if present
            match = re.search(r"Pet:\s*\**\s*(.*?)\s*\**\s+Submission alert", content_to_check, re.IGNORECASE)
            if match:
                pet_name = match.group(1).strip()
                submissions.add(pet_name)

        # 2. Check for Delivery
        # Based on screenshot: "Pet: Casper page delivered"
        elif "page delivered" in content_to_check:
            match = re.search(r"Pet:\s*\**\s*(.*?)\s*\**\s+page delivered", content_to_check, re.IGNORECASE)
            if match:
                pet_name = match.group(1).strip()
                deliveries.add(pet_name)

    # CALCULATE STATS
    pending = submissions - deliveries
    success_rate = 0
    if len(submissions) > 0:
        success_rate = round((len(deliveries) / len(submissions)) * 100)

    # REPORT
    embed = discord.Embed(title=f"📊 Daily Production Report", color=0x3498db)
    embed.add_field(name="Total Received", value=str(len(submissions)), inline=True)
    embed.add_field(name="Total Delivered", value=str(len(deliveries)), inline=True)
    embed.add_field(name="Success Rate", value=f"{success_rate}%", inline=True)

    if pending:
        pending_list = "\n".join([f"• {name}" for name in pending])
        # Discord field limit check
        if len(pending_list) > 1000: 
            pending_list = pending_list[:950] + "...(and more)"
        embed.add_field(name=f"⚠️ Pending ({len(pending)})", value=pending_list, inline=False)
    else:
        embed.add_field(name="✅ Status", value="All Clear! No pending jobs.", inline=False)

    embed.set_footer(text="Analysis based on Chat Embeds from last 24h")
    
    await output_channel.send(embed=embed)

client.run(TOKEN)
