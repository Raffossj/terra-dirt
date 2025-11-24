import discord
from discord.ext import commands
import asyncio
import os
import random
from datetime import datetime, timedelta
from typing import Optional
import time
import secrets
import json
import hashlib
from key_system import KeySystem
from aiohttp import web

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='?', intents=intents, help_command=None)

ALLOWED_USER_ID = 1242093054932811919
bot_start_time = time.time()
afk_users = {}
active_games = {}
validation_tokens = {}  # Store {token: {'user_id': ..., 'key': ..., 'timestamp': ...}}

key_system = KeySystem()

async def validation_handler(request):
    try:
        data = await request.json()
        key_code = data.get('key')
        discord_id = data.get('discord_id')
        hwid = data.get('hwid')
        
        if not key_code:
            return web.json_response({'valid': False, 'code': 'MISSING_KEY', 'message': 'Key is required'}, status=400)
        
        result = await key_system.validate_key(key_code, discord_id, hwid)
        return web.json_response(result)
    except Exception as e:
        return web.json_response({'valid': False, 'code': 'ERROR', 'message': str(e)}, status=500)

async def start_http_server():
    app = web.Application()
    app.router.add_post('/validate', validation_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    print('HTTP validation server started on http://0.0.0.0:8080')

@bot.check
async def globally_block_users(ctx):
    return ctx.author.id == ALLOWED_USER_ID

@bot.command(name='message')
async def type_message(ctx, *, arg):
    if arg.startswith(':'):
        message_content = arg[1:].strip()
        async with ctx.channel.typing():
            typed_message = ''
            for char in message_content:
                typed_message += char
                await asyncio.sleep(0.05)
            await ctx.send(typed_message)
    else:
        await ctx.send("Please use the format ?message : \"your message\"")

@bot.command(name='embed')
async def create_embed(ctx, *, arg):
    if arg.startswith(':'):
        message_content = arg[1:].strip()
        embed = discord.Embed(
            description=message_content,
            color=discord.Color.blue()
        )
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
        await ctx.send(embed=embed)
    else:
        await ctx.send("Please use the format ?embed : \"your message\"")

@bot.command(name='coinflip')
async def coinflip(ctx):
    result = random.choice(['Heads', 'Tails'])
    embed = discord.Embed(
        title='🪙 Coin Flip',
        description=f'**{result}!**',
        color=discord.Color.gold()
    )
    await ctx.send(embed=embed)

@bot.command(name='roll')
async def roll_dice(ctx, dice: str = '1d6'):
    try:
        rolls, sides = map(int, dice.lower().split('d'))
        if rolls > 100 or sides > 1000:
            await ctx.send('Too many dice or sides! Maximum is 100d1000.')
            return
        
        results = [random.randint(1, sides) for _ in range(rolls)]
        total = sum(results)
        
        embed = discord.Embed(
            title='🎲 Dice Roll',
            description=f'Rolling {dice}',
            color=discord.Color.purple()
        )
        if len(results) <= 20:
            embed.add_field(name='Results', value=', '.join(map(str, results)), inline=False)
        embed.add_field(name='Total', value=f'**{total}**', inline=False)
        await ctx.send(embed=embed)
    except:
        await ctx.send('Invalid format! Use ?roll <number>d<sides> (e.g., ?roll 2d20)')

@bot.command(name='poll')
async def create_poll(ctx, *, question):
    embed = discord.Embed(
        title='📊 Poll',
        description=question,
        color=discord.Color.green(),
        timestamp=datetime.utcnow()
    )
    embed.set_footer(text=f'Poll by {ctx.author.display_name}')
    
    poll_msg = await ctx.send(embed=embed)
    await poll_msg.add_reaction('👍')
    await poll_msg.add_reaction('👎')
    await poll_msg.add_reaction('🤷')

@bot.command(name='8ball')
async def magic_8ball(ctx, *, question):
    responses = [
        'It is certain.', 'Without a doubt.', 'Yes - definitely.',
        'You may rely on it.', 'As I see it, yes.', 'Most likely.',
        'Outlook good.', 'Yes.', 'Signs point to yes.',
        'Reply hazy, try again.', 'Ask again later.', 'Better not tell you now.',
        'Cannot predict now.', 'Concentrate and ask again.',
        "Don't count on it.", 'My reply is no.', 'My sources say no.',
        'Outlook not so good.', 'Very doubtful.'
    ]
    
    embed = discord.Embed(
        title='🎱 Magic 8-Ball',
        color=discord.Color.dark_purple()
    )
    embed.add_field(name='Question', value=question, inline=False)
    embed.add_field(name='Answer', value=random.choice(responses), inline=False)
    await ctx.send(embed=embed)

@bot.command(name='serverinfo')
async def server_info(ctx):
    guild = ctx.guild
    embed = discord.Embed(
        title=f'{guild.name}',
        color=discord.Color.blue(),
        timestamp=datetime.utcnow()
    )
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    
    embed.add_field(name='Server ID', value=guild.id, inline=True)
    owner_value = guild.owner.mention if guild.owner else 'Unknown'
    embed.add_field(name='Owner', value=owner_value, inline=True)
    embed.add_field(name='Members', value=guild.member_count, inline=True)
    embed.add_field(name='Channels', value=len(guild.channels), inline=True)
    embed.add_field(name='Roles', value=len(guild.roles), inline=True)
    embed.add_field(name='Created', value=guild.created_at.strftime('%B %d, %Y'), inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name='userinfo')
async def user_info(ctx, member: Optional[discord.Member] = None):
    member = member or ctx.author
    
    embed = discord.Embed(
        title='User Information',
        color=member.color if member.color != discord.Color.default() else discord.Color.blue(),
        timestamp=datetime.utcnow()
    )
    
    if member.avatar:
        embed.set_thumbnail(url=member.avatar.url)
    
    embed.add_field(name='Username', value=f'{member.name}', inline=True)
    embed.add_field(name='Display Name', value=member.display_name, inline=True)
    embed.add_field(name='ID', value=member.id, inline=True)
    embed.add_field(name='Account Created', value=member.created_at.strftime('%B %d, %Y'), inline=False)
    embed.add_field(name='Joined Server', value=member.joined_at.strftime('%B %d, %Y') if member.joined_at else 'Unknown', inline=False)
    
    roles = [role.mention for role in member.roles[1:]]
    if roles:
        embed.add_field(name=f'Roles [{len(roles)}]', value=' '.join(roles) if len(roles) <= 10 else f'{len(roles)} roles', inline=False)
    
    await ctx.send(embed=embed)

@bot.command(name='ping')
async def ping(ctx):
    latency = round(bot.latency * 1000)
    embed = discord.Embed(
        title='🏓 Pong!',
        description=f'Latency: **{latency}ms**',
        color=discord.Color.green() if latency < 100 else discord.Color.orange() if latency < 200 else discord.Color.red()
    )
    await ctx.send(embed=embed)

@bot.command(name='avatar')
async def avatar(ctx, member: Optional[discord.Member] = None):
    member = member or ctx.author
    
    embed = discord.Embed(
        title=f"{member.display_name}'s Avatar",
        color=discord.Color.blue()
    )
    if member.avatar:
        embed.set_image(url=member.avatar.url)
        embed.add_field(name='Download', value=f'[Click Here]({member.avatar.url})')
    else:
        embed.description = 'This user has no avatar.'
    
    await ctx.send(embed=embed)

@bot.command(name='choose')
async def choose(ctx, *, choices):
    options = [choice.strip() for choice in choices.split(',')]
    
    if len(options) < 2:
        await ctx.send('Please provide at least 2 choices separated by commas!')
        return
    
    chosen = random.choice(options)
    
    embed = discord.Embed(
        title='🤔 I Choose...',
        description=f'**{chosen}**',
        color=discord.Color.blue()
    )
    embed.add_field(name='Options', value=', '.join(options), inline=False)
    await ctx.send(embed=embed)

@bot.command(name='reverse')
async def reverse_text(ctx, *, text):
    reversed_text = text[::-1]
    embed = discord.Embed(
        title='🔄 Reversed Text',
        description=reversed_text,
        color=discord.Color.purple()
    )
    await ctx.send(embed=embed)

@bot.command(name='say')
async def say(ctx, *, message):
    await ctx.message.delete()
    await ctx.send(message)

@bot.command(name='calc')
async def calculator(ctx, *, expression):
    try:
        if expression.replace(' ', '') == '2+2':
            result = 5
        else:
            safe_expr = expression.replace('^', '**')
            result = eval(safe_expr, {"__builtins__": {}}, {})
        
        embed = discord.Embed(
            title='🧮 Calculator',
            color=discord.Color.blue()
        )
        embed.add_field(name='Expression', value=expression, inline=False)
        embed.add_field(name='Result', value=f'**{result}**', inline=False)
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f'Invalid expression! Error: {str(e)}')

@bot.command(name='randomnumber')
async def random_number(ctx, min_num: int = 1, max_num: int = 100):
    if min_num >= max_num:
        await ctx.send('Minimum must be less than maximum!')
        return
    
    number = random.randint(min_num, max_num)
    
    embed = discord.Embed(
        title='🎰 Random Number',
        description=f'**{number}**',
        color=discord.Color.gold()
    )
    embed.add_field(name='Range', value=f'{min_num} - {max_num}')
    await ctx.send(embed=embed)

@bot.command(name='joke')
async def joke(ctx):
    jokes = [
        "Why do programmers prefer dark mode? Because light attracts bugs!",
        "Why did the developer go broke? Because he used up all his cache!",
        "How many programmers does it take to change a light bulb? None, it's a hardware problem!",
        "Why do Java developers wear glasses? Because they don't C#!",
        "What's a programmer's favorite hangout place? Foo Bar!",
        "Why did the programmer quit his job? He didn't get arrays!",
        "What do you call a programmer from Finland? Nerdic!",
        "Why do programmers always mix up Halloween and Christmas? Because Oct 31 == Dec 25!",
        "What's the object-oriented way to become wealthy? Inheritance!",
        "Why did the Python programmer not respond to the foreign mails? Because his interpreter was busy!",
    ]
    
    embed = discord.Embed(
        title='😂 Random Joke',
        description=random.choice(jokes),
        color=discord.Color.orange()
    )
    await ctx.send(embed=embed)

@bot.command(name='timer')
async def timer(ctx, seconds: int):
    if seconds < 1 or seconds > 300:
        await ctx.send('Timer must be between 1 and 300 seconds (5 minutes)!')
        return
    
    embed = discord.Embed(
        title='⏲️ Timer Started',
        description=f'Timer set for **{seconds}** seconds',
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed)
    
    await asyncio.sleep(seconds)
    
    embed = discord.Embed(
        title='⏰ Time\'s Up!',
        description=f'{ctx.author.mention}, your **{seconds}** second timer is done!',
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

@bot.command(name='clear')
async def clear_messages(ctx, amount: int = 10):
    if amount < 1 or amount > 100:
        await ctx.send('Please provide a number between 1 and 100!')
        return
    
    deleted = await ctx.channel.purge(limit=amount + 1)
    
    embed = discord.Embed(
        title='🧹 Messages Cleared',
        description=f'Deleted **{len(deleted) - 1}** messages!',
        color=discord.Color.green()
    )
    msg = await ctx.send(embed=embed)
    await asyncio.sleep(3)
    await msg.delete()

@bot.command(name='meme')
async def meme(ctx):
    meme_texts = [
        "When you fix a bug but create 3 more 🐛",
        "It works on my machine ¯\\_(ツ)_/¯",
        "Stackoverflow has entered the chat 💬",
        "When the code works but you don't know why 🤔",
        "404: Motivation not found",
        "Ctrl+C, Ctrl+V - A programmer's best friend",
        "When you spend hours debugging only to find a missing semicolon 😭",
        "// TODO: Fix this later (Last edited: 3 years ago)",
        "Git commit -m 'stuff' 🚀",
        "There are only 10 types of people: those who understand binary and those who don't"
    ]
    
    embed = discord.Embed(
        title='😂 Programming Meme',
        description=random.choice(meme_texts),
        color=discord.Color.orange()
    )
    await ctx.send(embed=embed)

@bot.command(name='ascii')
async def ascii_art(ctx, *, text: Optional[str] = None):
    if not text or len(text) > 20:
        await ctx.send('Please provide text (max 20 characters)!')
        return
    
    ascii_styles = {
        'A': '░█████╗░', 'B': '██████╗░', 'C': '░█████╗░', 'D': '██████╗░',
        'E': '███████╗', 'F': '███████╗', 'G': '░██████╗░', 'H': '██╗░░██╗',
        'I': '██╗', 'J': '░░░░░██╗', 'K': '██╗░░██╗', 'L': '██╗░░░░░',
        'M': '███╗░░░███╗', 'N': '███╗░░██╗', 'O': '░█████╗░', 'P': '██████╗░',
        'Q': '░██████╗░', 'R': '██████╗░', 'S': '░██████╗', 'T': '████████╗',
        'U': '██╗░░░██╗', 'V': '██╗░░░██╗', 'W': '░██╗░░░░░░░██╗', 'X': '██╗░░██╗',
        'Y': '██╗░░░██╗', 'Z': '███████╗', ' ': '░░'
    }
    
    result = ''.join(ascii_styles.get(c.upper(), '?') for c in text[:10])
    await ctx.send(f'```\n{result}\n```')

@bot.command(name='quote')
async def quote(ctx):
    quotes = [
        "The only way to do great work is to love what you do. - Steve Jobs",
        "Code is like humor. When you have to explain it, it's bad. - Cory House",
        "First, solve the problem. Then, write the code. - John Johnson",
        "Experience is the name everyone gives to their mistakes. - Oscar Wilde",
        "Knowledge is power. - Francis Bacon",
        "Simplicity is the soul of efficiency. - Austin Freeman",
        "Make it work, make it right, make it fast. - Kent Beck",
        "Code never lies, comments sometimes do. - Ron Jeffries",
        "Fix the cause, not the symptom. - Steve Maguire",
        "Optimism is an occupational hazard of programming. - James Miller"
    ]
    
    embed = discord.Embed(
        title='💭 Inspirational Quote',
        description=random.choice(quotes),
        color=discord.Color.purple(),
        timestamp=datetime.utcnow()
    )
    await ctx.send(embed=embed)

@bot.command(name='fact')
async def random_fact(ctx):
    facts = [
        "The first computer bug was an actual bug - a moth found in a computer in 1947!",
        "The first programmer was Ada Lovelace, who wrote the first algorithm in 1843.",
        "The password for the computer controls of nuclear missiles was '00000000' for 8 years.",
        "About 70% of all coding jobs are in fields outside of technology.",
        "The first computer virus was created in 1983 by a 15-year-old student.",
        "CAPTCHA is an acronym: Completely Automated Public Turing test to tell Computers and Humans Apart.",
        "The first 1GB hard drive weighed over 500 pounds and cost $40,000 in 1980.",
        "Python is named after Monty Python, not the snake!",
        "The @ symbol in email was chosen by Ray Tomlinson in 1971.",
        "There are more than 700 programming languages in existence."
    ]
    
    embed = discord.Embed(
        title='🤓 Random Tech Fact',
        description=random.choice(facts),
        color=discord.Color.teal()
    )
    await ctx.send(embed=embed)

@bot.command(name='spam')
async def spam(ctx, amount: int, *, message: str):
    if amount < 1 or amount > 10:
        await ctx.send('Amount must be between 1 and 10!')
        return
    
    for _ in range(amount):
        await ctx.send(message)
        await asyncio.sleep(0.5)

@bot.command(name='countdown')
async def countdown(ctx, count: int = 5):
    if count < 1 or count > 10:
        await ctx.send('Countdown must be between 1 and 10!')
        return
    
    msg = await ctx.send(f'**{count}**')
    
    for i in range(count - 1, 0, -1):
        await asyncio.sleep(1)
        await msg.edit(content=f'**{i}**')
    
    await asyncio.sleep(1)
    await msg.edit(content='🎉 **GO!** 🎉')

@bot.command(name='rps')
async def rock_paper_scissors(ctx, choice: str):
    choices = ['rock', 'paper', 'scissors']
    choice = choice.lower()
    
    if choice not in choices:
        await ctx.send('Please choose rock, paper, or scissors!')
        return
    
    bot_choice = random.choice(choices)
    
    result = ''
    if choice == bot_choice:
        result = "It's a tie!"
        color = discord.Color.gold()
    elif (choice == 'rock' and bot_choice == 'scissors') or \
         (choice == 'paper' and bot_choice == 'rock') or \
         (choice == 'scissors' and bot_choice == 'paper'):
        result = 'You win!'
        color = discord.Color.green()
    else:
        result = 'I win!'
        color = discord.Color.red()
    
    embed = discord.Embed(
        title='🪨 Rock Paper Scissors',
        color=color
    )
    embed.add_field(name='Your Choice', value=choice.capitalize(), inline=True)
    embed.add_field(name='My Choice', value=bot_choice.capitalize(), inline=True)
    embed.add_field(name='Result', value=f'**{result}**', inline=False)
    await ctx.send(embed=embed)

@bot.command(name='guess')
async def guess_number(ctx):
    number = random.randint(1, 100)
    active_games[ctx.author.id] = {'number': number, 'attempts': 0, 'channel': ctx.channel.id}
    
    embed = discord.Embed(
        title='🎯 Guess the Number!',
        description='I\'m thinking of a number between 1 and 100!\nYou have 10 attempts. Use `?g [number]` to guess.',
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed)

@bot.command(name='g')
async def guess_attempt(ctx, number: int):
    if ctx.author.id not in active_games:
        await ctx.send('Start a game first with `?guess`!')
        return
    
    game = active_games[ctx.author.id]
    game['attempts'] += 1
    
    if number == game['number']:
        embed = discord.Embed(
            title='🎉 Congratulations!',
            description=f'You guessed it! The number was **{game["number"]}**\nAttempts: **{game["attempts"]}**',
            color=discord.Color.green()
        )
        del active_games[ctx.author.id]
        await ctx.send(embed=embed)
    elif game['attempts'] >= 10:
        embed = discord.Embed(
            title='😢 Game Over!',
            description=f'You ran out of attempts! The number was **{game["number"]}**',
            color=discord.Color.red()
        )
        del active_games[ctx.author.id]
        await ctx.send(embed=embed)
    elif number < game['number']:
        await ctx.send(f'📈 Higher! ({10 - game["attempts"]} attempts left)')
    else:
        await ctx.send(f'📉 Lower! ({10 - game["attempts"]} attempts left)')

@bot.command(name='hug')
async def hug(ctx, member: Optional[discord.Member] = None):
    if not member:
        await ctx.send('Who do you want to hug? Mention someone!')
        return
    
    if member.id == ctx.author.id:
        await ctx.send('You can\'t hug yourself! 🤗')
        return
    
    embed = discord.Embed(
        description=f'🤗 **{ctx.author.display_name}** hugs **{member.display_name}**!',
        color=discord.Color.pink()
    )
    await ctx.send(embed=embed)

@bot.command(name='slap')
async def slap(ctx, member: Optional[discord.Member] = None):
    if not member:
        await ctx.send('Who do you want to slap? Mention someone!')
        return
    
    if member.id == ctx.author.id:
        await ctx.send('Why would you slap yourself? 😅')
        return
    
    embed = discord.Embed(
        description=f'👋 **{ctx.author.display_name}** slaps **{member.display_name}**!',
        color=discord.Color.orange()
    )
    await ctx.send(embed=embed)

@bot.command(name='pat')
async def pat(ctx, member: Optional[discord.Member] = None):
    if not member:
        await ctx.send('Who do you want to pat? Mention someone!')
        return
    
    embed = discord.Embed(
        description=f'🖐️ **{ctx.author.display_name}** pats **{member.display_name}** on the head!',
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

@bot.command(name='afk')
async def set_afk(ctx, *, reason: Optional[str] = None):
    reason = reason or 'AFK'
    afk_users[ctx.author.id] = reason
    
    embed = discord.Embed(
        title='💤 AFK Status Set',
        description=f'Reason: {reason}',
        color=discord.Color.purple()
    )
    await ctx.send(embed=embed)

@bot.command(name='uptime')
async def uptime(ctx):
    current_time = time.time()
    uptime_seconds = int(current_time - bot_start_time)
    
    days = uptime_seconds // 86400
    hours = (uptime_seconds % 86400) // 3600
    minutes = (uptime_seconds % 3600) // 60
    seconds = uptime_seconds % 60
    
    uptime_str = f'{days}d {hours}h {minutes}m {seconds}s'
    
    embed = discord.Embed(
        title='⏰ Bot Uptime',
        description=f'I\'ve been online for: **{uptime_str}**',
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed)

@bot.command(name='rate')
async def rate(ctx, *, thing: str):
    rating = random.randint(0, 100)
    
    if rating >= 90:
        emoji = '🌟'
        comment = 'Amazing!'
    elif rating >= 70:
        emoji = '😊'
        comment = 'Pretty good!'
    elif rating >= 50:
        emoji = '😐'
        comment = 'Okay...'
    elif rating >= 30:
        emoji = '😕'
        comment = 'Not great...'
    else:
        emoji = '😢'
        comment = 'Oof...'
    
    embed = discord.Embed(
        title=f'{emoji} Rating',
        description=f'I rate **{thing}** a **{rating}/100**!\n{comment}',
        color=discord.Color.gold()
    )
    await ctx.send(embed=embed)

@bot.command(name='slots')
async def slots(ctx):
    emojis = ['🍒', '🍋', '🍊', '🍇', '⭐', '💎', '7️⃣']
    result = [random.choice(emojis) for _ in range(3)]
    
    if result[0] == result[1] == result[2]:
        if result[0] == '💎':
            message = '🎰 JACKPOT! Triple diamonds! 💰💰💰'
            color = discord.Color.gold()
        elif result[0] == '7️⃣':
            message = '🎰 TRIPLE 777! MEGA WIN! 🎉'
            color = discord.Color.gold()
        else:
            message = '🎰 Three of a kind! You win! 🎉'
            color = discord.Color.green()
    elif result[0] == result[1] or result[1] == result[2] or result[0] == result[2]:
        message = '🎰 Two of a kind! Small win! 🎊'
        color = discord.Color.blue()
    else:
        message = '🎰 No match. Try again!'
        color = discord.Color.red()
    
    embed = discord.Embed(
        title='🎰 Slot Machine',
        description=f'{result[0]} | {result[1]} | {result[2]}\n\n{message}',
        color=color
    )
    await ctx.send(embed=embed)

@bot.command(name='wyr')
async def would_you_rather(ctx):
    questions = [
        "Would you rather have unlimited money or unlimited time?",
        "Would you rather be able to fly or be invisible?",
        "Would you rather never use social media again or never watch another movie/TV show?",
        "Would you rather be fluent in all languages or be a master of every musical instrument?",
        "Would you rather live without music or without movies?",
        "Would you rather time travel to the past or to the future?",
        "Would you rather have the ability to read minds or see the future?",
        "Would you rather be famous when you're alive but forgotten when you die, or unknown when you're alive but famous after you die?",
        "Would you rather work more hours a day but have longer vacations or work fewer hours but have shorter vacations?",
        "Would you rather lose all your money and valuables or lose all the pictures you've ever taken?"
    ]
    
    embed = discord.Embed(
        title='🤔 Would You Rather...',
        description=random.choice(questions),
        color=discord.Color.purple()
    )
    await ctx.send(embed=embed)

@bot.command(name='trivia')
async def trivia(ctx):
    trivia_questions = [
        {"q": "What does HTML stand for?", "a": "HyperText Markup Language"},
        {"q": "Who created Python?", "a": "Guido van Rossum"},
        {"q": "What year was the first iPhone released?", "a": "2007"},
        {"q": "What does CPU stand for?", "a": "Central Processing Unit"},
        {"q": "What is the most popular programming language in 2024?", "a": "JavaScript or Python"},
        {"q": "What company developed Java?", "a": "Sun Microsystems"},
        {"q": "What does RAM stand for?", "a": "Random Access Memory"},
        {"q": "Who is the founder of Microsoft?", "a": "Bill Gates"},
        {"q": "What does AI stand for?", "a": "Artificial Intelligence"},
        {"q": "What is the name of Apple's voice assistant?", "a": "Siri"}
    ]
    
    question = random.choice(trivia_questions)
    
    embed = discord.Embed(
        title='🧠 Tech Trivia',
        description=f'**Question:** {question["q"]}',
        color=discord.Color.blue()
    )
    embed.set_footer(text=f'Answer: {question["a"]}')
    await ctx.send(embed=embed)

@bot.command(name='mock')
async def mock_text(ctx, *, text: str):
    mocked = ''.join(c.upper() if i % 2 else c.lower() for i, c in enumerate(text))
    await ctx.send(mocked)

@bot.command(name='clap')
async def clap_text(ctx, *, text: str):
    clapped = ' 👏 '.join(text.split())
    await ctx.send(clapped)

@bot.command(name='fortune')
async def fortune_cookie(ctx):
    fortunes = [
        "You will find success in unexpected places.",
        "A pleasant surprise is waiting for you.",
        "Your code will compile on the first try... eventually.",
        "The bug you seek is closer than you think.",
        "Your next commit will be your best work yet.",
        "Stack Overflow will have the answer you need.",
        "Good things come to those who debug.",
        "Your hard work will soon pay off.",
        "A new opportunity awaits in your next project.",
        "Trust your instincts, they are usually right.",
        "Adventure awaits those who take chances.",
        "Your creativity will solve the problem.",
        "The answer you seek is in the documentation.",
        "Patience will lead you to the solution."
    ]
    
    embed = discord.Embed(
        title='🥠 Fortune Cookie',
        description=random.choice(fortunes),
        color=discord.Color.gold()
    )
    await ctx.send(embed=embed)

@bot.command(name='flip')
async def flip_text(ctx, *, text: str):
    normal = 'abcdefghijklmnopqrstuvwxyz'
    flipped = 'ɐqɔpǝɟƃɥᴉɾʞlɯuodbɹsʇnʌʍxʎz'
    flip_dict = dict(zip(normal, flipped))
    flip_dict.update(dict(zip(normal.upper(), flipped.upper())))
    
    result = ''.join(flip_dict.get(c, c) for c in text)[::-1]
    await ctx.send(result)

@bot.command(name='randomcolor')
async def random_color(ctx):
    color_hex = '#{:06x}'.format(random.randint(0, 0xFFFFFF))
    color_int = int(color_hex[1:], 16)
    
    embed = discord.Embed(
        title='🎨 Random Color',
        description=f'**{color_hex.upper()}**',
        color=discord.Color(color_int)
    )
    embed.set_thumbnail(url=f'https://singlecolorimage.com/get/{color_hex[1:]}/100x100')
    await ctx.send(embed=embed)

@bot.command(name='botinfo')
async def bot_info(ctx):
    embed = discord.Embed(
        title='🤖 Bot Information',
        color=discord.Color.blue(),
        timestamp=datetime.utcnow()
    )
    
    embed.add_field(name='Bot Name', value=bot.user.name if bot.user else 'Unknown', inline=True)
    embed.add_field(name='Servers', value=len(bot.guilds), inline=True)
    total_users = sum(g.member_count for g in bot.guilds if g.member_count)
    embed.add_field(name='Users', value=total_users, inline=True)
    embed.add_field(name='Commands', value=len(bot.commands), inline=True)
    embed.add_field(name='Latency', value=f'{round(bot.latency * 1000)}ms', inline=True)
    
    uptime_seconds = int(time.time() - bot_start_time)
    days = uptime_seconds // 86400
    hours = (uptime_seconds % 86400) // 3600
    minutes = (uptime_seconds % 3600) // 60
    embed.add_field(name='Uptime', value=f'{days}d {hours}h {minutes}m', inline=True)
    
    if bot.user and bot.user.avatar:
        embed.set_thumbnail(url=bot.user.avatar.url)
    
    await ctx.send(embed=embed)

@bot.command(name='announce')
async def announce(ctx, *, message: str):
    embed = discord.Embed(
        title='📢 Announcement',
        description=message,
        color=discord.Color.red(),
        timestamp=datetime.utcnow()
    )
    embed.set_footer(text=f'Announced by {ctx.author.display_name}')
    await ctx.send(embed=embed)

@bot.command(name='remindme')
async def remind_me(ctx, seconds: int, *, reminder: str):
    if seconds < 1 or seconds > 3600:
        await ctx.send('Reminder time must be between 1 and 3600 seconds (1 hour)!')
        return
    
    embed = discord.Embed(
        title='⏰ Reminder Set',
        description=f'I\'ll remind you in **{seconds}** seconds!',
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed)
    
    await asyncio.sleep(seconds)
    
    embed = discord.Embed(
        title='⏰ Reminder!',
        description=reminder,
        color=discord.Color.green()
    )
    await ctx.send(f'{ctx.author.mention}', embed=embed)

@bot.command(name='binary')
async def to_binary(ctx, *, text: str):
    binary = ' '.join(format(ord(c), '08b') for c in text)
    
    if len(binary) > 2000:
        await ctx.send('Text too long to convert!')
        return
    
    embed = discord.Embed(
        title='🔢 Binary Converter',
        color=discord.Color.blue()
    )
    embed.add_field(name='Original', value=text, inline=False)
    embed.add_field(name='Binary', value=f'`{binary}`', inline=False)
    await ctx.send(embed=embed)

@bot.command(name='hex')
async def to_hex(ctx, *, text: str):
    hex_text = ' '.join(format(ord(c), 'x') for c in text)
    
    if len(hex_text) > 2000:
        await ctx.send('Text too long to convert!')
        return
    
    embed = discord.Embed(
        title='🔤 Hex Converter',
        color=discord.Color.purple()
    )
    embed.add_field(name='Original', value=text, inline=False)
    embed.add_field(name='Hex', value=f'`{hex_text}`', inline=False)
    await ctx.send(embed=embed)

@bot.command(name='yesno')
async def yes_or_no(ctx, *, question: str):
    answer = random.choice(['Yes', 'No', 'Maybe', 'Definitely', 'Absolutely not', 'Of course!', 'Never', 'Always', 'Sometimes'])
    
    embed = discord.Embed(
        title='❓ Yes or No',
        color=discord.Color.blue()
    )
    embed.add_field(name='Question', value=question, inline=False)
    embed.add_field(name='Answer', value=f'**{answer}**', inline=False)
    await ctx.send(embed=embed)

@bot.command(name='inspire')
async def inspire(ctx):
    messages = [
        "Believe in yourself!",
        "You can do it!",
        "Keep pushing forward!",
        "Never give up!",
        "Your potential is unlimited!",
        "Every expert was once a beginner!",
        "Progress, not perfection!",
        "You're doing great!",
        "Keep learning and growing!",
        "Success is a journey, not a destination!",
        "Coding is an art, and you're the artist!",
        "Debug your doubts and compile your dreams!",
        "The only way to learn is to do!",
        "Mistakes are proof that you're trying!"
    ]
    
    embed = discord.Embed(
        title='✨ Inspiration',
        description=random.choice(messages),
        color=discord.Color.gold()
    )
    await ctx.send(embed=embed)

@bot.command(name='passwordgen')
async def generate_password(ctx, length: int = 16):
    if length < 4 or length > 64:
        await ctx.send('Password length must be between 4 and 64!')
        return
    
    import string
    characters = string.ascii_letters + string.digits + string.punctuation
    password = ''.join(random.choice(characters) for _ in range(length))
    
    try:
        await ctx.author.send(f'Your generated password: `{password}`')
        await ctx.send('Password sent to your DMs! 📨')
    except:
        await ctx.send('I couldn\'t send you a DM! Please enable DMs from server members.')

@bot.command(name='emojify')
async def emojify(ctx, *, text: str):
    emoji_dict = {
        'a': '🅰️', 'b': '🅱️', 'c': '©️', 'd': '↩️', 'e': '📧',
        'f': '🎏', 'g': '🔀', 'h': '♓', 'i': 'ℹ️', 'j': '🗾',
        'k': '🎋', 'l': '👢', 'm': 'Ⓜ️', 'n': '🎵', 'o': '⭕',
        'p': '🅿️', 'q': '🔍', 'r': '®️', 's': '💲', 't': '✝️',
        'u': '⛎', 'v': '✌️', 'w': '〰️', 'x': '❌', 'y': '💴', 'z': '💤',
        '0': '0️⃣', '1': '1️⃣', '2': '2️⃣', '3': '3️⃣', '4': '4️⃣',
        '5': '5️⃣', '6': '6️⃣', '7': '7️⃣', '8': '8️⃣', '9': '9️⃣',
        '!': '❗', '?': '❓'
    }
    
    result = ' '.join(emoji_dict.get(c.lower(), c) for c in text)
    
    if len(result) > 2000:
        await ctx.send('Text too long to emojify!')
        return
    
    await ctx.send(result)

@bot.command(name='script')
async def manage_script(ctx, action: str = None, *, args: str = ''):
    if action == 'add':
        parts = args.split('|', 1)
        script_name = parts[0].strip()
        description = parts[1].strip() if len(parts) > 1 else ''
        
        result = await key_system.create_script(script_name, description)
        
        if result['success']:
            embed = discord.Embed(
                title='✅ Script Created',
                color=discord.Color.green()
            )
            embed.add_field(name='Script Name', value=script_name, inline=False)
            embed.add_field(name='Script ID', value=f'`{result["script_id"]}`', inline=False)
            if description:
                embed.add_field(name='Description', value=description, inline=False)
            await ctx.send(embed=embed)
        else:
            await ctx.send(f'❌ Error: {result["error"]}')
    
    elif action == 'list':
        scripts = await key_system.get_all_scripts()
        
        if not scripts:
            await ctx.send('No scripts found.')
            return
        
        embed = discord.Embed(
            title='📜 All Scripts',
            color=discord.Color.blue()
        )
        
        for script in scripts[:10]:
            embed.add_field(
                name=script['script_name'],
                value=f'ID: `{script["script_id"]}`\n{script.get("description", "No description")}',
                inline=False
            )
        
        await ctx.send(embed=embed)
    
    else:
        await ctx.send('Usage: `?script add [name] | [description]` or `?script list`')

@bot.command(name='genkey')
async def generate_key(ctx, script_id: str, days: int = 0, max_uses: int = -1, *, note: str = ''):
    result = await key_system.create_key(script_id, None, days if days > 0 else None, max_uses, note)
    
    if result['success']:
        embed = discord.Embed(
            title='🔑 Key Generated',
            color=discord.Color.gold()
        )
        embed.add_field(name='Key', value=f'||`{result["key"]}`||', inline=False)
        embed.add_field(name='Script ID', value=f'`{result["script_id"]}`', inline=True)
        
        if result['expires_at']:
            embed.add_field(name='Expires', value=result['expires_at'].strftime('%Y-%m-%d %H:%M:%S'), inline=True)
        else:
            embed.add_field(name='Expires', value='Never', inline=True)
        
        embed.add_field(name='Max Uses', value=str(max_uses) if max_uses > 0 else 'Unlimited', inline=True)
        
        if note:
            embed.add_field(name='Note', value=note, inline=False)
        
        await ctx.send(embed=embed)
    else:
        await ctx.send(f'❌ Error: {result["error"]}')

@bot.command(name='redeemkey')
async def redeem_key_command(ctx, key_code: str):
    result = await key_system.redeem_key(key_code, ctx.author.id)
    
    if result['success']:
        embed = discord.Embed(
            title='✅ Key Redeemed',
            description=result['message'],
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
    else:
        await ctx.send(f'❌ Error: {result["error"]}')

@bot.command(name='checkkey')
async def check_key(ctx, key_code: str):
    key_info = await key_system.get_key_info(key_code)
    
    if not key_info:
        await ctx.send('❌ Key not found')
        return
    
    embed = discord.Embed(
        title='🔍 Key Information',
        color=discord.Color.blue()
    )
    
    embed.add_field(name='Script', value=key_info['script_name'], inline=False)
    embed.add_field(name='Key', value=f'`{key_code}`', inline=False)
    embed.add_field(name='Status', value='✅ Active' if key_info['is_active'] else '❌ Inactive', inline=True)
    
    if key_info['discord_id']:
        embed.add_field(name='Discord ID', value=f'`{key_info["discord_id"]}`', inline=True)
    else:
        embed.add_field(name='Discord ID', value='Not redeemed', inline=True)
    
    if key_info['expires_at']:
        embed.add_field(name='Expires', value=key_info['expires_at'].strftime('%Y-%m-%d %H:%M:%S'), inline=True)
    else:
        embed.add_field(name='Expires', value='Never', inline=True)
    
    uses_text = f"{key_info['current_uses']}/{key_info['max_uses']}" if key_info['max_uses'] > 0 else f"{key_info['current_uses']}/Unlimited"
    embed.add_field(name='Uses', value=uses_text, inline=True)
    
    embed.add_field(name='Created', value=key_info['created_at'].strftime('%Y-%m-%d %H:%M:%S'), inline=True)
    
    if key_info['hwid_hash']:
        embed.add_field(name='HWID', value='Bound', inline=True)
    else:
        embed.add_field(name='HWID', value='Not bound', inline=True)
    
    if key_info.get('note'):
        embed.add_field(name='Note', value=key_info['note'], inline=False)
    
    await ctx.send(embed=embed)

@bot.command(name='mykeys')
async def my_keys(ctx):
    keys = await key_system.get_user_keys(ctx.author.id)
    
    if not keys:
        await ctx.send('You don\'t have any keys.')
        return
    
    embed = discord.Embed(
        title='🔑 Your Keys',
        color=discord.Color.purple()
    )
    
    for key in keys[:10]:
        status = '✅' if key['is_active'] else '❌'
        expires = key['expires_at'].strftime('%Y-%m-%d') if key['expires_at'] else 'Never'
        uses = f"{key['current_uses']}/{key['max_uses']}" if key['max_uses'] > 0 else f"{key['current_uses']}/∞"
        
        embed.add_field(
            name=f"{status} {key['script_name']}",
            value=f"Key: ||`{key['key_code']}`||\nExpires: {expires}\nUses: {uses}",
            inline=False
        )
    
    if len(keys) > 10:
        embed.set_footer(text=f'Showing 10 of {len(keys)} keys')
    
    await ctx.send(embed=embed)

@bot.command(name='allkeys')
async def all_keys(ctx):
    keys = await key_system.get_all_keys()
    
    if not keys:
        await ctx.send('No keys found in the system.')
        return
    
    embed = discord.Embed(
        title='🔑 All Keys',
        description=f'Total: {len(keys)} keys',
        color=discord.Color.blue()
    )
    
    for key in keys[:15]:
        status = '✅' if key['is_active'] else '❌'
        expires = key['expires_at'].strftime('%Y-%m-%d') if key['expires_at'] else 'Never'
        uses = f"{key['current_uses']}/{key['max_uses']}" if key['max_uses'] > 0 else f"{key['current_uses']}/∞"
        discord_id = f"`{key['discord_id']}`" if key['discord_id'] else 'Not redeemed'
        
        embed.add_field(
            name=f"{status} {key['script_name']}",
            value=f"Key: ||`{key['key_code']}`||\nUser: {discord_id}\nExpires: {expires} | Uses: {uses}",
            inline=False
        )
    
    if len(keys) > 15:
        embed.set_footer(text=f'Showing 15 of {len(keys)} keys')
    
    await ctx.send(embed=embed)

@bot.command(name='deletekey')
async def delete_key_command(ctx, key_code: str):
    result = await key_system.delete_key(key_code)
    
    if result['success']:
        await ctx.send(f'✅ Key `{key_code}` has been deleted.')
    else:
        await ctx.send(f'❌ Key not found or could not be deleted.')

@bot.command(name='resethwid')
async def reset_hwid_command(ctx, key_code: str):
    result = await key_system.reset_hwid(key_code)
    
    if result['success']:
        await ctx.send(f'✅ HWID reset for key `{key_code}`.')
    else:
        await ctx.send(f'❌ Key not found or could not reset HWID.')

@bot.command(name='validate')
async def validate_key_command(ctx, key_code: str):
    result = await key_system.validate_key(key_code)
    
    if result['valid']:
        # Generate validation token (32 hex chars = 16 bytes)
        validation_token = secrets.token_hex(16).upper()
        
        # Store token with metadata
        validation_tokens[validation_token] = {
            'user_id': ctx.author.id,
            'key': key_code[:8],
            'timestamp': time.time()
        }
        
        embed = discord.Embed(
            title='✅ Key Validation Successful',
            description=f'Your key has been validated!',
            color=discord.Color.green()
        )
        embed.add_field(name='Status', value='✅ Valid', inline=False)
        
        if result.get('data'):
            embed.add_field(name='Script', value=result['data'].get('script_name', 'Unknown'), inline=True)
            current = result['data'].get('current_uses', 0)
            max_uses = result['data'].get('max_uses', -1)
            uses_str = f"{current}/{max_uses}" if max_uses > 0 else f"{current}/∞"
            embed.add_field(name='Uses', value=uses_str, inline=True)
            if result['data'].get('expires_at'):
                embed.add_field(name='Expires', value=str(result['data']['expires_at'])[:10], inline=True)
        
        # Send validation token via DM
        dm_embed = embed.copy()
        dm_embed.add_field(name='🔑 Executor Token', value=f'`{validation_token}`\n\nCopy and paste this into your executor script.\nValid for 30 minutes.', inline=False)
        
        try:
            await ctx.author.send(embed=dm_embed)
            await ctx.send('✅ Check your DMs for the executor token!')
        except:
            embed.add_field(name='⚠️ Token', value=f'`{validation_token}`\n(Enable DMs for the token)', inline=False)
            await ctx.send(embed=embed)
            
    else:
        embed = discord.Embed(
            title='❌ Key Validation Failed',
            description=result.get('message', 'Invalid key'),
            color=discord.Color.red()
        )
        embed.add_field(name='Error Code', value=result.get('code', 'UNKNOWN'), inline=False)
        embed.set_footer(text=f'Attempted by {ctx.author.display_name}')
        await ctx.send(embed=embed)

@bot.command(name='checktoken')
async def check_token_command(ctx, token: str):
    """Check if a validation token is still valid"""
    token = token.upper().strip()
    
    if token in validation_tokens:
        token_data = validation_tokens[token]
        age = time.time() - token_data['timestamp']
        
        if age < 1800:  # 30 minutes
            await ctx.send(f'✅ Token is VALID (Age: {int(age)}s)')
        else:
            await ctx.send(f'⏰ Token EXPIRED')
            del validation_tokens[token]
    else:
        await ctx.send(f'❌ Token not found or invalid')

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    if message.author.id in afk_users:
        reason = afk_users.pop(message.author.id)
        await message.channel.send(f'Welcome back, {message.author.mention}! You are no longer AFK.')
    
    for mention in message.mentions:
        if mention.id in afk_users:
            reason = afk_users[mention.id]
            await message.channel.send(f'{mention.display_name} is currently AFK: {reason}')
    
    await bot.process_commands(message)

@bot.command(name='help')
async def help_command(ctx):
    embed = discord.Embed(
        title='🤖 Bot Commands Help',
        description='Here are all the available commands:',
        color=discord.Color.blue(),
        timestamp=datetime.utcnow()
    )
    
    embed.add_field(
        name='💬 Text Commands',
        value='`?message : text` - Typing effect\n'
              '`?embed : text` - Create embed\n'
              '`?say [text]` - Bot says text\n'
              '`?reverse [text]` - Reverse text\n'
              '`?spam [amount] [text]` - Spam (max 10)\n'
              '`?mock [text]` - mOcKiNg TeXt\n'
              '`?clap [text]` - Add 👏 between words\n'
              '`?flip [text]` - Flip text upside down\n'
              '`?emojify [text]` - Convert to emojis',
        inline=False
    )
    
    embed.add_field(
        name='🎮 Games',
        value='`?coinflip` - Flip a coin\n'
              '`?roll [dice]` - Roll dice\n'
              '`?8ball [question]` - Magic 8-ball\n'
              '`?rps [choice]` - Rock Paper Scissors\n'
              '`?guess` - Number guessing game\n'
              '`?g [number]` - Make a guess\n'
              '`?slots` - Slot machine\n'
              '`?trivia` - Tech trivia',
        inline=False
    )
    
    embed.add_field(
        name='🛠️ Utility',
        value='`?ping` - Bot latency\n'
              '`?calc [expression]` - Calculator\n'
              '`?timer [seconds]` - Set timer\n'
              '`?countdown [number]` - Countdown\n'
              '`?poll [question]` - Create poll\n'
              '`?clear [amount]` - Delete messages\n'
              '`?uptime` - Bot uptime\n'
              '`?afk [reason]` - Set AFK\n'
              '`?remindme [sec] [text]` - Reminder\n'
              '`?passwordgen [length]` - Password',
        inline=False
    )
    
    embed.add_field(
        name='ℹ️ Info & Social',
        value='`?serverinfo` - Server info\n'
              '`?userinfo [@user]` - User info\n'
              '`?avatar [@user]` - User avatar\n'
              '`?botinfo` - Bot stats\n'
              '`?hug [@user]` - Hug someone\n'
              '`?slap [@user]` - Slap someone\n'
              '`?pat [@user]` - Pat someone\n'
              '`?rate [thing]` - Rate something',
        inline=False
    )
    
    embed.add_field(
        name='🎨 Fun',
        value='`?joke` - Programming joke\n'
              '`?meme` - Programming meme\n'
              '`?quote` - Inspirational quote\n'
              '`?fact` - Tech fact\n'
              '`?fortune` - Fortune cookie\n'
              '`?inspire` - Inspiration\n'
              '`?yesno [question]` - Yes/No\n'
              '`?wyr` - Would you rather\n'
              '`?choose [opts]` - Pick option\n'
              '`?randomnumber [min] [max]`\n'
              '`?randomcolor` - Random color',
        inline=False
    )
    
    embed.add_field(
        name='🔧 Converters',
        value='`?binary [text]` - To binary\n'
              '`?hex [text]` - To hexadecimal\n'
              '`?ascii [text]` - ASCII art\n'
              '`?announce [text]` - Announcement',
        inline=False
    )
    
    embed.add_field(
        name='🔑 Key System',
        value='**Admin:**\n'
              '`?script add [name] | [desc]` - Add script\n'
              '`?script list` - List all scripts\n'
              '`?genkey [script_id] [days] [max_uses] [note]`\n'
              '`?allkeys` - View all keys\n'
              '`?deletekey [key]` - Delete key\n'
              '`?resethwid [key]` - Reset HWID\n\n'
              '**User:**\n'
              '`?redeemkey [key]` - Redeem key\n'
              '`?checkkey [key]` - Check key info\n'
              '`?mykeys` - View your keys',
        inline=False
    )
    
    embed.set_footer(text=f'Requested by {ctx.author.display_name}')
    await ctx.send(embed=embed)

@bot.event
async def on_ready():
    await key_system.init()
    asyncio.create_task(start_http_server())
    print(f'{bot.user} has connected to Discord!')

async def main():
    bot_token = os.getenv('DISCORD_BOT_TOKEN')
    if not bot_token:
        raise ValueError("DISCORD_BOT_TOKEN not found in environment variables. Please add it in the Secrets tab.")
    
    try:
        await bot.start(bot_token)
    finally:
        await key_system.close()

if __name__ == '__main__':
    asyncio.run(main())
