import discord
import re
import os
from datetime import datetime, timedelta, timezone
from flask import Flask
from threading import Thread

# --- PART 1: FAKE WEB SERVER (For Koyeb) ---
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
    print('Available commands: !report (Daily), !weekly (7 Days)')

@client.event
async def on_message(message):
    # Daily Report Command
    if message.content == '!report':
        await generate_report(message.channel, days=1)
    
    # Weekly Report Command
    elif message.content == '!weekly':
        await generate_report(message.channel, days=7)

# --- SHARED SCANNING ENGINE ---
async def scan_channel(channel_id, search_pattern, days_back):
    found_names = set()
    channel = client.get_channel(channel_id)
    
    if not channel:
        return found_names

    # Dynamic Time Window
    start_date = datetime.now(timezone.utc) - timedelta(days=days_back)

    # Use limit=None to get EVERYTHING in that timeframe
    async for msg in channel.history(limit=None, after=start_date):
        text_to_check = msg.content
        if msg.embeds:
            for embed in msg.embeds:
                text_to_check += " " + str(embed.title) + " " + str(embed.description)
        
        # Clean Text
        text_to_check = text_to_check.replace('*', '')

        # Regex Match
        match = re.search(search_pattern, text_to_check, re.IGNORECASE)
        if match:
            name = match.group(1).strip().lower()
            if name:
                found_names.add(name)
            
    return found_names

# --- SHARED REPORT GENERATOR ---
async def generate_report(output_channel, days):
    title_text = "📊 Daily Production Report (24h)" if days == 1 else "🗓️ Weekly Production Report (7 Days)"
    await output_channel.send(f"🕵️‍♀️ Generating **{title_text}**... please wait.")

    # 1. SCAN CHANNELS
    submissions = await scan_channel(CHANNELS['main'], r"Pet:\s*(.*?)\s+Submission alert", days)
    delivered = await scan_channel(CHANNELS['main'], r"Pet:\s*(.*?)\s+page delivered", days)
    system_errors = await scan_channel(CHANNELS['system'], r"Pet:\s*(.*?)\s+.*(?:Error|Failed|Crash)", days)
    picasso_failures = await scan_channel(CHANNELS['picasso'], r"PETNAME.*:\s*(.*)", days)

    # 2. STRICT MATH LOGIC
    all_failures = system_errors | picasso_failures
    all_finished_items = delivered | all_failures
    
    # Pending = Submitted BUT NOT in finished list
    pending_real = submissions - all_finished_items

    # Cleared = Total received minus the ones still pending
    total_received = len(submissions)
    total_cleared = total_received - len(pending_real)
    
    success_rate = 0
    if total_received > 0:
        success_rate = round((total_cleared / total_received) * 100)

    # 3. GENERATE EMBED
    embed = discord.Embed(title=title_text, color=0x2b2d31)
    
    embed.add_field(name="📥 Received", value=str(total_received), inline=True)
    embed.add_field(name="✅ Processed", value=str(total_cleared), inline=True)
    embed.add_field(name="📈 Success Rate", value=f"{success_rate}%", inline=True)

    # Section for Picasso Failures
    if picasso_failures:
        p_list = "\n".join([f"• {n.title()}" for n in list(picasso_failures)[:15]])
        if len(picasso_failures) > 15: p_list += f"\n...and {len(picasso_failures)-15} more."
        embed.add_field(name="🎨 Picasso Rejections", value=p_list, inline=False)

    # Section for System Errors
    if system_errors:
        s_list = "\n".join([f"• {n.title()}" for n in list(system_errors)[:15]])
        if len(system_errors) > 15: s_list += f"\n...and {len(system_errors)-15} more."
        embed.add_field(name="🚨 System Errors", value=s_list, inline=False)

    # Section for Pending
    if pending_real:
        pend_list = "\n".join([f"• {n.title()}" for n in list(pending_real)[:20]])
        if len(pending_real) > 20: pend_list += f"\n...and {len(pending_real)-20} more."
        embed.add_field(name=f"⏳ Pending Queue ({len(pending_real)})", value=pend_list, inline=False)
    else:
        embed.add_field(name="✨ Queue Status", value="All Clear! Zero pending.", inline=False)

    embed.set_footer(text=f"Analysis period: Last {days} days")
    await output_channel.send(embed=embed)

# --- START ---
start_server()
client.run(TOKEN)
