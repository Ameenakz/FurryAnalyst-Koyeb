import discord
import re
import os
from datetime import datetime, timedelta, timezone
from flask import Flask
from threading import Thread

# --- PART 1: FAKE WEB SERVER (Keep this for Koyeb) ---
app = Flask('')

@app.route('/')
def home():
    return "I am alive! The Analyst is watching."

def run_web_server():
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)

def start_server():
    t = Thread(target=run_web_server)
    t.start()

# --- PART 2: BOT CONFIGURATION ---
TOKEN = os.environ.get("DISCORD_TOKEN")

# UPDATE THESE IDS WITH YOUR REAL DISCORD CHANNEL IDS
CHANNELS = {
    'main': 1446110269301588090,      # #client-submission-alerts
    'system': 1453090765046681746,    # #system-errors
    'picasso': 1454853444493115522    # #picasso-workflow-failures
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
    
    if not channel:
        return found_names

    # Look back 24 hours
    after_date = datetime.now(timezone.utc) - timedelta(hours=24)

    async for msg in channel.history(limit=500, after=after_date):
        text_to_check = msg.content
        if msg.embeds:
            for embed in msg.embeds:
                text_to_check += " " + str(embed.title) + " " + str(embed.description)
        
        # Remove bolding for cleaner matching
        text_to_check = text_to_check.replace('*', '')

        # Regex Search
        match = re.search(search_pattern, text_to_check, re.IGNORECASE)
        if match:
            name = match.group(1).strip().lower()
            found_names.add(name)
            
    return found_names

async def generate_full_report(output_channel):
    await output_channel.send("🕵️‍♀️ conducting full audit across 3 channels... please wait.")

    # 1. SCAN MAIN CHANNEL (In and Out)
    submissions = await scan_channel(CHANNELS['main'], r"Pet:\s*(.*?)\s+Submission alert")
    delivered = await scan_channel(CHANNELS['main'], r"Pet:\s*(.*?)\s+page delivered")

    # 2. SCAN SYSTEM ERROR CHANNEL
    # Matches: "Pet: Casper ... Error" or "Failed"
    system_errors = await scan_channel(CHANNELS['system'], r"Pet:\s*(.*?)\s+.*(?:Error|Failed|Crash)")

    # 3. SCAN PICASSO CHANNEL
    # New Regex: Matches "PETNAME" followed by anything (like 🐶), then a colon, then the name
    picasso_failures = await scan_channel(CHANNELS['picasso'], r"PETNAME.*:\s*(.*)")

    # 4. STRICT MATH LOGIC
    # Combine all "Bad" outcomes
    all_failures = system_errors | picasso_failures
    
    # "Done" = Successfully Delivered OR Failed/Rejected
    all_finished_items = delivered | all_failures
    
    # "Pending" = Submitted items that are NOT in the finished list
    pending_real = submissions - all_finished_items

    # "Cleared" = Total received minus the ones still pending
    total_received = len(submissions)
    total_cleared = total_received - len(pending_real)
    
    success_rate = 0
    if total_received > 0:
        success_rate = round((total_cleared / total_received) * 100)

    # 5. GENERATE REPORT CARD
    embed = discord.Embed(title="📊 Daily Production Report", color=0x2b2d31)
    
    embed.add_field(name="📥 Received", value=str(total_received), inline=True)
    embed.add_field(name="✅ Processed", value=str(total_cleared), inline=True)
    embed.add_field(name="📈 Success Rate", value=f"{success_rate}%", inline=True)

    # Section for Picasso Failures (Client Errors)
    if picasso_failures:
        p_list = "\n".join([f"• {n.title()}" for n in picasso_failures])
        embed.add_field(name="🎨 Picasso Failures (Check Data)", value=p_list, inline=False)

    # Section for System Errors (Bot Crashes)
    if system_errors:
        s_list = "\n".join([f"• {n.title()}" for n in system_errors])
        embed.add_field(name="🚨 System Errors (Fix Bot)", value=s_list, inline=False)

    # Section for Pending
    if pending_real:
        pend_list = "\n".join([f"• {n.title()}" for n in pending_real])
        if len(pend_list) > 900: pend_list = pend_list[:900] + "..."
        embed.add_field(name=f"⏳ Pending Queue ({len(pending_real)})", value=pend_list, inline=False)
    else:
        embed.add_field(name="✨ Queue Status", value="All Clear! Zero pending.", inline=False)

    embed.set_footer(text="Analysis covers the last 24h across Main, Error, and Picasso channels.")
    await output_channel.send(embed=embed)

# --- START ---
start_server()
client.run(TOKEN)
