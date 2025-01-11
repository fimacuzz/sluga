import discord
from discord.ext import commands
from discord import app_commands
import logging
import asyncio
import random
import sqlite3
from PIL import Image, ImageDraw, ImageFont
import io
import aiohttp
import datetime
import os

# Настройка логирования
logging.basicConfig(
    filename="messages.log",
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

if not os.path.exists("messages.log"):
    open("messages.log", "w").close()
    print("Файл messages.log создан.")

# Настройка бота
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.guild_messages = True
intents.voice_states = True
intents.members = True
bot = commands.Bot(command_prefix="/", intents=intents)

# Настройка базы данных
def db_setup():
    conn = sqlite3.connect('xp_database.db')
    c = conn.cursor()

    # Создаем таблицу users, если она не существует
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1
        )
    ''')

    # Создаем таблицу warns, если она не существует
    c.execute('''
        CREATE TABLE IF NOT EXISTS warns (
            warn_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            reason TEXT,
            moderator_id INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()
    print("База данных настроена.")

# Добавление XP
async def add_xp(user_id, amount):
    conn = sqlite3.connect('xp_database.db')
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (user_id,))
    c.execute('UPDATE users SET xp = xp + ? WHERE user_id = ?', (amount, user_id))

    # Увеличение уровня, если XP превышает порог
    c.execute('SELECT xp, level FROM users WHERE user_id = ?', (user_id,))
    xp, level = c.fetchone()
    if xp >= level * 100:
        level += 1
        c.execute('UPDATE users SET level = ? WHERE user_id = ?', (level, user_id))
        await bot.get_channel(TARGET_CHANNEL_ID).send(
            f"{bot.get_user(user_id).mention} достиг уровня {level}!"
        )

    conn.commit()
    conn.close()

    # Логирование с временем
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logging.info(f"Добавлено {amount} XP для пользователя {user_id}. Текущий XP: {xp + amount}, Уровень: {level}")

# Получение данных пользователя
def get_user_data(user_id):
    conn = sqlite3.connect('xp_database.db')
    c = conn.cursor()
    c.execute('SELECT xp, level FROM users WHERE user_id = ?', (user_id,))
    data = c.fetchone()
    conn.close()
    return data if data else (0, 1)

# Загрузка аватара
async def fetch_avatar(avatar_url):
    async with aiohttp.ClientSession() as session:
        async with session.get(avatar_url) as response:
            return await response.read()

# Генерация изображения уровня
async def generate_level_image(user_id, user_name, avatar_url):
    xp, level = get_user_data(user_id)
    current_level_xp = (level - 1) * 100
    next_level_xp = level * 100
    progress_percentage = min((xp - current_level_xp) / (next_level_xp - current_level_xp), 1)

    # Размеры изображения
    width, height = 800, 200

    # Фон
    img = Image.new("RGB", (width, height), color=(40, 40, 40))
    d = ImageDraw.Draw(img)

    # Круг для аватара
    circle_radius = 50
    circle_x, circle_y = 20, height // 3 - circle_radius

    avatar = Image.open(io.BytesIO(await fetch_avatar(avatar_url)))
    avatar = avatar.resize((circle_radius * 2, circle_radius * 2))
    img.paste(avatar, (circle_x, circle_y))

    # Шрифты
    font_large = ImageFont.truetype('Comfortaa-VariableFont_wght.ttf', 40)
    font_small = ImageFont.truetype('Comfortaa-VariableFont_wght.ttf', 40)

    text_x = circle_x + circle_radius * 2 + 20
    text_y = circle_y + 5

    d.text((text_x, text_y + 5), f"{user_name} | Уровень {level}", font=font_large, fill=(255, 255, 255))
    d.text((text_x, text_y + 55), f"XP: {xp}/{next_level_xp}", font=font_small, fill=(255, 255, 255))

    # Полоса прогресса
    bar_width, bar_height = 750, 30
    bar_x, bar_y = 20, height - 60
    filled_width = int(bar_width * progress_percentage)

    d.rounded_rectangle([bar_x, bar_y, bar_x + bar_width, bar_y + bar_height], radius=15, fill=(200, 200, 200))
    d.rounded_rectangle([bar_x, bar_y, bar_x + filled_width, bar_y + bar_height], radius=15, fill=(255, 165, 0))

    byte_io = io.BytesIO()
    img.save(byte_io, 'PNG')
    byte_io.seek(0)

    return byte_io

# Константы
TARGET_CHANNEL_ID = 1324438108183466046
VOICE_CHANNEL_NOTIFICATION_ID = 1324443284310982676
MUTE_ROLE_ID = 1324449149223178291
ADMIN_ROLE_ID = 1168187028563824680

# Проверка роли администратора
def has_admin_role(interaction: discord.Interaction) -> bool:
    return any(role.id == ADMIN_ROLE_ID for role in interaction.user.roles)

# Событие on_ready
@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"Синхронизировано {len(synced)} команд.")
    except Exception as e:
        print(f"Ошибка синхронизации команд: {e}")

    activity = discord.Game(name="Jägermeister")
    await bot.change_presence(activity=activity)
    print(f"{bot.user.name} подключился к Discord")

# Событие on_message
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    log_message = f"[{message.guild.name} - #{message.channel.name}] {message.author.name}: {message.content}"
    logging.info(log_message)

    target_channel = bot.get_channel(TARGET_CHANNEL_ID)
    if target_channel:
        embed = discord.Embed(title="Новое сообщение", description=message.content, color=discord.Color.blue())
        embed.set_author(name=message.author.name, icon_url=message.author.avatar.url)
        embed.add_field(name="Канал", value=f"#{message.channel.name}", inline=False)
        embed.set_footer(text=f"ID пользователя: {message.author.id}")
        await target_channel.send(embed=embed)

    await add_xp(message.author.id, random.randint(5, 15))
    await bot.process_commands(message)

# Команда /level
@bot.tree.command(name="level", description="Показывает ваш текущий уровень и XP")
async def level(interaction: discord.Interaction):
    user_id = interaction.user.id
    user_name = interaction.user.name
    avatar_url = interaction.user.avatar.url
    level_image = await generate_level_image(user_id, user_name, avatar_url)
    await interaction.response.send_message(file=discord.File(level_image, filename='level.png'))

# Команда /ping
@bot.tree.command(name="ping", description="Проверка работоспособности бота")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("Pong!")

# Команда /roll
@bot.tree.command(name="roll", description="Бросает кубик с указанным количеством сторон")
@app_commands.describe(sides="Количество сторон кубика")
async def roll(interaction: discord.Interaction, sides: int = 6):
    if sides < 1:
        await interaction.response.send_message("Количество сторон должно быть положительным числом.")
        return
    result = random.randint(1, sides)
    await interaction.response.send_message(f"Вы бросили кубик с {sides} сторонами и получили: **{result}**")

# Команда /vladosik
@bot.tree.command(name="vladosik", description="Показывает какой мамонт крутой")
async def vladosik(interaction: discord.Interaction):
    await interaction.response.send_message(file=discord.File('vlados.png'))
    await interaction.followup.send("Он очень крутой!")
    await interaction.followup.send("Самый лучший")
    await interaction.followup.send("Но лучше Костика никого нету))))")

# Команда /quote
@bot.tree.command(name="quote", description="Показывает случайную цитату")
async def quote(interaction: discord.Interaction):
    quotes = [
        "Волк не тот кто волк, а тот кто волк", "Мирон долбаеб",
        "Артем долбаеб", "Соня свинья", "Агнесса дура АУФФФФФ",
        "Волк не тот кто даун, а тот кто волк", "Жизнь пиздатая вещь",
        "Get busy YEAT YA3 NAXYYYI", "Макан ван лав"
    ]
    quote = random.choice(quotes)
    await interaction.response.send_message(f"**Цитата:** {quote}")

# Команда /avatar
@bot.tree.command(name="avatar", description="Показывает аватар пользователя")
@app_commands.describe(member="Пользователь, чей аватар вы хотите увидеть")
async def avatar(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    embed = discord.Embed(title=f"Аватар {member.name}", color=discord.Color.blue())
    embed.set_image(url=member.avatar.url)
    await interaction.response.send_message(embed=embed)

# Команда /serverinfo
@bot.tree.command(name="serverinfo", description="Показывает информацию о сервере")
@app_commands.check(has_admin_role)
async def serverinfo(interaction: discord.Interaction):
    guild = interaction.guild
    embed = discord.Embed(title=f"Информация о сервере: {guild.name}", color=discord.Color.green())
    embed.add_field(name="ID сервера", value=guild.id)
    embed.add_field(name="Создан", value=guild.created_at.strftime("%Y-%m-%d %H:%M:%S"))
    embed.add_field(name="Количество участников", value=guild.member_count)
    await interaction.response.send_message(embed=embed)

# Команда /userinfo
@bot.tree.command(name="userinfo", description="Показывает информацию о пользователе")
@app_commands.describe(member="Пользователь, информацию о котором вы хотите увидеть")
async def userinfo(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    embed = discord.Embed(title=f"Информация о пользователе: {member.name}", color=discord.Color.blue())
    embed.add_field(name="ID пользователя", value=member.id)
    embed.add_field(name="Создан", value=member.created_at.strftime("%Y-%m-%d %H:%M:%S"))
    embed.add_field(name="Присоединился", value=member.joined_at.strftime("%Y-%m-%d %H:%M:%S"))
    await interaction.response.send_message(embed=embed)

# Команда /say
@bot.tree.command(name="say", description="Отправляет сообщение от имени бота")
@app_commands.describe(message="Сообщение, которое вы хотите отправить")
@app_commands.check(has_admin_role)
async def say(interaction: discord.Interaction, message: str):
    if not has_admin_role(interaction):
        await interaction.response.send_message("У вас нет прав для использования этой команды.", ephemeral=True)
        return

    await interaction.response.send_message(message)

# Команда /clear
@bot.tree.command(name="clear", description="Удаляет указанное количество сообщений")
@app_commands.describe(amount="Количество сообщений для удаления")
@app_commands.check(has_admin_role)
async def clear(interaction: discord.Interaction, amount: int):
    if not has_admin_role(interaction):
        await interaction.response.send_message("У вас нет прав для использования этой команды.", ephemeral=True)
        return

    if amount <= 0:
        await interaction.response.send_message("Количество сообщений должно быть положительным числом.")
        return
    await interaction.channel.purge(limit=amount + 1)
    await interaction.response.send_message(f"Удалено {amount} сообщений.", delete_after=5)

# Команда /anons
@bot.tree.command(name="anons", description="Отправляет объявление")
@app_commands.describe(title="Заголовок объявления", message="Текст объявления")
@app_commands.check(has_admin_role)
async def anons(interaction: discord.Interaction, title: str, message: str):
    if not has_admin_role(interaction):
        await interaction.response.send_message("У вас нет прав для использования этой команды.", ephemeral=True)
        return

    embed = discord.Embed(title=title, description=message, color=discord.Color.red())
    await interaction.response.send_message(embed=embed)

# Команда /addxp
@bot.tree.command(name="addxp", description="Добавляет XP пользователю")
@app_commands.describe(member="Пользователь, которому нужно добавить XP", amount="Количество XP")
@app_commands.check(has_admin_role)
async def addxp(interaction: discord.Interaction, member: discord.Member, amount: int):
    if not has_admin_role(interaction):
        await interaction.response.send_message("У вас нет прав для использования этой команды.", ephemeral=True)
        return

    if amount <= 0:
        await interaction.response.send_message("Количество XP должно быть положительным числом.")
        return
    await add_xp(member.id, amount)
    await interaction.response.send_message(f"Добавлено {amount} XP пользователю {member.mention}.")

# Команда /mute
@bot.tree.command(name="mute", description="Мутит пользователя на указанное время")
@app_commands.describe(member="Пользователь, которого нужно замутить", time="Время в минутах", reason="Причина мута")
@app_commands.check(has_admin_role)
async def mute(interaction: discord.Interaction, member: discord.Member, time: int, reason: str):
    if not has_admin_role(interaction):
        await interaction.response.send_message("У вас нет прав для использования этой команды.", ephemeral=True)
        return

    role = interaction.guild.get_role(MUTE_ROLE_ID)
    if not role:
        await interaction.response.send_message("Роль для мута не найдена.")
        return

    await member.add_roles(role)
    embed = discord.Embed(
        title="Пользователь замучен",
        description=f"{member.mention} был замучен на **{time} минут**. Причина: *{reason}*.",
        color=discord.Color.red()
    )
    await interaction.response.send_message(embed=embed)

    try:
        dm_embed = discord.Embed(
            title="Вы получили мут",
            description=f"Вы были замучены на сервере **{interaction.guild.name}** на **{time} минут**.\nПричина: *{reason}*.",
            color=discord.Color.orange()
        )
        await member.send(embed=dm_embed)
    except discord.Forbidden:
        await interaction.followup.send(
            f"Не удалось отправить сообщение в ЛС пользователю {member.mention}. Возможно, он закрыл ЛС для бота.",
            ephemeral=True
        )
    except Exception as e:
        await interaction.followup.send(f"Произошла ошибка при отправке сообщения в ЛС: {e}", ephemeral=True)

    await asyncio.sleep(time * 60)
    await member.remove_roles(role)
    unmute_embed = discord.Embed(title="Пользователь размучен", description=f"{member.mention} был размучен.", color=discord.Color.green())
    await interaction.followup.send(embed=unmute_embed)

# Команда /unmute
@bot.tree.command(name="unmute", description="Снимает мут с пользователя")
@app_commands.describe(member="Пользователь, которого нужно размутить")
@app_commands.check(has_admin_role)
async def unmute(interaction: discord.Interaction, member: discord.Member):
    if not has_admin_role(interaction):
        await interaction.response.send_message("У вас нет прав для использования этой команды.", ephemeral=True)
        return

    role = interaction.guild.get_role(MUTE_ROLE_ID)
    if role:
        await member.remove_roles(role)
        embed = discord.Embed(title="Пользователь размучен", description=f"{member.mention} был размучен.", color=discord.Color.green())
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message("Роль для мута не найдена.")

# Команда /ban
@bot.tree.command(name="ban", description="Банит пользователя")
@app_commands.describe(member="Пользователь, которого нужно забанить", reason="Причина бана")
@commands.has_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "Не указана причина."):
    try:
        await member.ban(reason=reason)
        embed = discord.Embed(
            title="Пользователь забанен",
            description=f"{member.mention} был забанен.\nПричина: *{reason}*.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)
    except discord.Forbidden:
        await interaction.response.send_message("У меня нет прав, чтобы забанить этого пользователя.")
    except discord.HTTPException:
        await interaction.response.send_message("Не удалось забанить пользователя.")
    except Exception as e:
        await interaction.response.send_message(f"Произошла ошибка: {e}")
        logging.error(f"Ошибка при выполнении команды ban: {e}")

# Команда /grole
@bot.tree.command(name="grole", description="Запросить создание новой роли")
@app_commands.describe(role_name="Название новой роли")
async def grole(interaction: discord.Interaction, role_name: str):
    target_channel = bot.get_channel(1325242576353103956)  # Укажите реальный ID канала
    if not target_channel:
        await interaction.response.send_message("Канал для заявок не найден. Обратитесь к администратору.", ephemeral=True)
        return

    embed = discord.Embed(
        title="Новая заявка на создание роли",
        description=f"Пользователь {interaction.user.mention} запросил создание новой роли.",
        color=discord.Color.blue(),
    )
    embed.add_field(name="Название роли", value=role_name, inline=False)
    embed.set_footer(text=f"ID пользователя: {interaction.user.id}")

    try:
        await target_channel.send(embed=embed)
        await interaction.response.send_message(f"Ваша заявка на создание роли **{role_name}** отправлена администраторам.", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("У меня нет прав на отправку сообщений в канал для заявок.", ephemeral=True)
    except discord.HTTPException as e:
        await interaction.response.send_message(f"Произошла ошибка при отправке заявки: {e}", ephemeral=True)

# Команда /help
@bot.tree.command(name="help", description="Показывает список всех доступных команд")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(title="Список команд", color=discord.Color.blue())

    embed.add_field(name="/level", value="Показывает ваш текущий уровень и XP", inline=False)
    embed.add_field(name="/ping", value="Проверка работоспособности бота", inline=False)
    embed.add_field(name="/roll", value="Бросает кубик с указанным количеством сторон", inline=False)
    embed.add_field(name="/vladosik", value="Показывает какой мамонт крутой", inline=False)
    embed.add_field(name="/quote", value="Показывает случайную цитату", inline=False)
    embed.add_field(name="/avatar", value="Показывает аватар пользователя", inline=False)
    embed.add_field(name="/serverinfo", value="Показывает информацию о сервере", inline=False)
    embed.add_field(name="/userinfo", value="Показывает информацию о пользователе", inline=False)
    embed.add_field(name="/say", value="Отправляет сообщение от имени бота", inline=False)
    embed.add_field(name="/clear", value="Удаляет указанное количество сообщений", inline=False)
    embed.add_field(name="/anons", value="Отправляет объявление", inline=False)
    embed.add_field(name="/addxp", value="Добавляет XP пользователю", inline=False)
    embed.add_field(name="/mute", value="Мутит пользователя на указанное время", inline=False)
    embed.add_field(name="/unmute", value="Снимает мут с пользователя", inline=False)
    embed.add_field(name="/ban", value="Банит пользователя", inline=False)
    embed.add_field(name="/grole", value="Запросить создание новой роли", inline=False)
    embed.add_field(name="/help", value="Показывает этот список команд", inline=False)

    await interaction.response.send_message(embed=embed)

# Команда /warn
@bot.tree.command(name="warn", description="Выдать предупреждение пользователю")
@app_commands.describe(member="Пользователь, которому нужно выдать предупреждение", reason="Причина предупреждения")
@app_commands.check(has_admin_role)
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str):
    if not has_admin_role(interaction):
        await interaction.response.send_message("У вас нет прав для использования этой команды.", ephemeral=True)
        return

    conn = sqlite3.connect('xp_database.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO warns (user_id, reason, moderator_id)
        VALUES (?, ?, ?)
    ''', (member.id, reason, interaction.user.id))
    conn.commit()
    conn.close()

    embed = discord.Embed(
        title="Предупреждение выдано",
        description=f"Пользователь {member.mention} получил предупреждение.",
        color=discord.Color.orange()
    )
    embed.add_field(name="Причина", value=reason, inline=False)
    embed.add_field(name="Модератор", value=interaction.user.mention, inline=False)
    await interaction.response.send_message(embed=embed)

    try:
        dm_embed = discord.Embed(
            title="Вы получили предупреждение",
            description=f"Вы получили предупреждение на сервере **{interaction.guild.name}**.",
            color=discord.Color.red()
        )
        dm_embed.add_field(name="Причина", value=reason, inline=False)
        dm_embed.add_field(name="Модератор", value=interaction.user.name, inline=False)
        await member.send(embed=dm_embed)
    except discord.Forbidden:
        await interaction.followup.send(f"Не удалось отправить сообщение в ЛС пользователю {member.mention}. Возможно, он закрыл ЛС для бота.", ephemeral=True)

# Команда /unwarn
@bot.tree.command(name="unwarn", description="Снять последнее предупреждение с пользователя")
@app_commands.describe(member="Пользователь, с которого нужно снять предупреждение")
@app_commands.check(has_admin_role)
async def unwarn(interaction: discord.Interaction, member: discord.Member):
    if not has_admin_role(interaction):
        await interaction.response.send_message("У вас нет прав для использования этой команды.", ephemeral=True)
        return

    conn = sqlite3.connect('xp_database.db')
    c = conn.cursor()
    c.execute('''
        DELETE FROM warns
        WHERE warn_id = (
            SELECT warn_id FROM warns
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT 1
        )
    ''', (member.id,))
    conn.commit()
    conn.close()

    embed = discord.Embed(
        title="Предупреждение снято",
        description=f"С пользователя {member.mention} было снято последнее предупреждение.",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed)

    try:
        dm_embed = discord.Embed(
            title="Предупреждение снято",
            description=f"Ваше последнее предупреждение на сервере **{interaction.guild.name}** было снято.",
            color=discord.Color.green()
        )
        await member.send(embed=dm_embed)
    except discord.Forbidden:
        await interaction.followup.send(f"Не удалось отправить сообщение в ЛС пользователю {member.mention}. Возможно, он закрыл ЛС для бота.", ephemeral=True)

# Команда /mywarns
@bot.tree.command(name="mywarns", description="Показать ваши предупреждения")
async def mywarns(interaction: discord.Interaction):
    user_id = interaction.user.id

    conn = sqlite3.connect('xp_database.db')
    c = conn.cursor()
    c.execute('''
        SELECT reason, moderator_id, timestamp FROM warns
        WHERE user_id = ?
        ORDER BY timestamp DESC
    ''', (user_id,))
    warns_data = c.fetchall()
    conn.close()

    if not warns_data:
        await interaction.response.send_message("У вас нет предупреждений.", ephemeral=True)
        return

    embed = discord.Embed(title="Ваши предупреждения", color=discord.Color.orange())
    for i, (reason, moderator_id, timestamp) in enumerate(warns_data, start=1):
        moderator = interaction.guild.get_member(moderator_id)
        moderator_name = moderator.name if moderator else "Неизвестный модератор"
        embed.add_field(
            name=f"Предупреждение #{i}",
            value=f"**Причина:** {reason}\n**Модератор:** {moderator_name}\n**Дата:** {timestamp}",
            inline=False
        )

    await interaction.response.send_message(embed=embed, ephemeral=True)

# Команда /nick
@bot.tree.command(name="nick", description="Меняет ник пользователя")
@app_commands.describe(member="Пользователь, чей ник нужно изменить", nickname="Новый ник")
@commands.has_permissions(manage_nicknames=True)
async def nick(interaction: discord.Interaction, member: discord.Member, nickname: str):
    try:
        await member.edit(nick=nickname)
        await interaction.response.send_message(f"Ник пользователя {member.mention} изменен на **{nickname}**.")
    except discord.Forbidden:
        await interaction.response.send_message("У меня нет прав, чтобы изменить ник этого пользователя.")
    except discord.HTTPException:
        await interaction.response.send_message("Не удалось изменить никнейм пользователя.")


db_setup()
bot.run('your_token')