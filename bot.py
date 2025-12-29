import discord
import re
import os
from datetime import datetime, timedelta, timezone
from flask import Flask
from threading import Thread

# --- PART 1: THE FAKE WEB SERVER (To trick Koyeb) ---
app = Flask('')

@app.route('/')
def home():
    return "I am alive! The bot is running."

def run_web_server():
    # Koyeb expects the app to listen on Port 8000
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)

def start_server():
    t = Thread(target=run_web_server)
    t.start()

# --- PART 2: THE BOT CONFIGURATION ---
TOKEN = os.environ.get("DISCORD_TOKEN") 

# Channel IDs (Replace with your actual IDs)
CHANNELS = {
    'main': 1446110269301588090,      # #client-submission-alerts
    'rejection': 123456789012345678, # #rejection-alerts
    'system': 123456789012345678     # #system-errors
}

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')

@client.event
async def on_message(message):
    if message.content == '!report':
        await generate_full_report(message.channel)

async def scan_channel(channel_id, search_pattern):
    found_names = set()
    channel = client.get_channel(channel_id)
    if not channel: return found_names

    after_date = datetime.now(timezone.utc) - timedelta(hours=24)
    async for msg in channel.history(limit=500, after=after_date):
        text_to_check = msg.content
        if msg.embeds:
            for embed in msg.embeds:
                text_to_check += " " + str(embed.title) + " " + str(embed.description)
        
        text_to_check = text_to_check.replace('*', '')
        match = re.search(search_pattern, text_to_check, re.IGNORECASE)
        if match:
            name = match.group(1).strip().lower()
            found_names.add(name)
    return found_names

async def generate_full_report(output_channel):
    await output_channel.send("🕵️‍♀️ Analyzing the last 24 hours... please wait.")
    
    submissions = await scan_channel(CHANNELS['main'], r"Pet:\s*(.*?)\s+Submission alert")
    delivered = await scan_channel(CHANNELS['main'], r"Pet:\s*(.*?)\s+page delivered")
    rejected = await scan_channel(CHANNELS['rejection'], r"Pet:\s*(.*?)\s+.*(?:Rejected|Policy|Invalid)")
    errors = await scan_channel(CHANNELS['system'], r"Pet:\s*(.*?)\s+.*(?:Error|Failed|Crash)")

    all_finished_items = delivered | rejected | errors
    pending_real = submissions - all_finished_items
    total_received = len(submissions)
    total_cleared = total_received - len(pending_real)
    
    success_rate = 0
    if total_received > 0:
        success_rate = round((total_cleared / total_received) * 100)

    embed = discord.Embed(title="📊 Daily Production Report", color=0x2b2d31)
    embed.add_field(name="📥 Received (24h)", value=str(total_received), inline=True)
    embed.add_field(name="✅ Cleared", value=str(total_cleared), inline=True)
    embed.add_field(name="📈 Success Rate", value=f"{success_rate}%", inline=True)

    if errors:
        error_list = "\n".join([f"• {n.title()}" for n in errors])
        embed.add_field(name="🔥 Needs Fix (Errors)", value=error_list, inline=False)

    if pending_real:
        pend_list = "\n".join([f"• {n.title()}" for n in pending_real])
        if len(pend_list) > 900: pend_list = pend_list[:900] + "..."
        embed.add_field(name=f"⚠️ Pending ({len(pending_real)})", value=pend_list, inline=False)
    else:
        embed.add_field(name="✨ Queue Status", value="All Clear! No pending jobs.", inline=False)

    embed.set_footer(text="Analysis covers the last 24 hours.")
    await output_channel.send(embed=embed)

# --- START BOTH SYSTEMS ---
start_server()  # Starts the fake web server first
client.run(TOKEN) # Starts the bot second
