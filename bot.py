import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
import asyncio

# ===== НАСТРОЙКИ =====
BOT_TOKEN = "ВАШ_НОВЫЙ_ТОКЕН_СЮДА"
GUILD_ID = 1458298216461369573                 # ID сервера
APPLICATIONS_CHANNEL_ID = 1479584185524944927  # ID канала куда приходят заявки
APPROVED_ROLE_ID = 1477044728980836552         # ID роли которая выдаётся после одобрения
MODERATOR_ROLE_IDS = [1477036902644318451, 1477037399845507124, 1477039314427711600]
ANKETA_CHANNEL_ID = 1480013460401160496      # ID канала где удаляются все сообщения кроме первого
# =====================

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


# --- Модальное окно с вопросами ---
class ApplicationModal(Modal, title="Анкета вступления"):
    game_nick = TextInput(
        label="Ник в игре (только имя, без фамилии)",
        placeholder="Например: Lener",
        max_length=32
    )
    real_name = TextInput(
        label="Настоящее имя",
        placeholder="Например: Ленер",
        max_length=50
    )
    static_id = TextInput(
        label="Статик (Static ID)",
        placeholder="Например: 1100",
        max_length=20
    )
    hours = TextInput(
        label="Сколько часов в игре (примерно)",
        placeholder="Например: 500+",
        max_length=20
    )
    age = TextInput(
        label="Сколько лет",
        placeholder="Например: 18",
        max_length=5
    )

    async def on_submit(self, interaction: discord.Interaction):
        member = interaction.user

        # Получаем guild — если анкета открыта из ЛС, берём по ID
        guild = interaction.guild
        if guild is None:
            guild = bot.get_guild(GUILD_ID)

        if guild is None:
            await interaction.response.send_message(
                "❌ Ошибка: не удалось найти сервер. Обратись к администратору.",
                ephemeral=True
            )
            return

        # Получаем member из guild
        guild_member = guild.get_member(member.id)
        if guild_member is None:
            await interaction.response.send_message(
                "❌ Ошибка: ты не найден на сервере.",
                ephemeral=True
            )
            return

        game_nick = self.game_nick.value.strip()
        real_name = self.real_name.value.strip()
        static_id = self.static_id.value.strip()
        hours = self.hours.value.strip()
        age = self.age.value.strip()

        # Новый ник: Имя в игре | Имя в жизни | Статик
        new_nick = f"{game_nick} | {real_name} | {static_id}"

        # Меняем ник участника
        try:
            await guild_member.edit(nick=new_nick)
            nick_status = f"✅ Ник установлен: `{new_nick}`"
        except discord.Forbidden:
            nick_status = "⚠️ Не удалось сменить ник (нет прав или это владелец сервера)"

        # Отправляем заявку в канал модераторов
        apps_channel = guild.get_channel(APPLICATIONS_CHANNEL_ID)
        if apps_channel:
            embed = discord.Embed(
                title="📋 Новая заявка на вступление",
                color=discord.Color.gold()
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.add_field(name="👤 Участник", value=f"{member.mention} (`{member.id}`)", inline=False)
            embed.add_field(name="🎮 Ник в игре", value=game_nick, inline=True)
            embed.add_field(name="📛 Настоящее имя", value=real_name, inline=True)
            embed.add_field(name="🔢 Статик", value=static_id, inline=True)
            embed.add_field(name="⏱️ Часов в игре", value=hours, inline=True)
            embed.add_field(name="🎂 Возраст", value=age, inline=True)
            embed.add_field(name="🏷️ Ник на сервере", value=nick_status, inline=False)
            embed.set_footer(text=f"ID: {member.id}")

            view = ApproveView(member_id=member.id, guild_id=guild.id)
            await apps_channel.send(embed=embed, view=view)

        await interaction.response.send_message(
            "✅ Твоя заявка отправлена на рассмотрение! Ожидай одобрения от администрации.",
            ephemeral=True
        )


# --- Кнопки одобрить/отклонить ---
class ApproveView(View):
    def __init__(self, member_id: int, guild_id: int):
        super().__init__(timeout=None)
        self.member_id = member_id
        self.guild_id = guild_id

    def is_moderator(self, interaction: discord.Interaction) -> bool:
        user_role_ids = [role.id for role in interaction.user.roles]
        return any(rid in user_role_ids for rid in MODERATOR_ROLE_IDS)

    @discord.ui.button(label="✅ Одобрить", style=discord.ButtonStyle.success, custom_id="approve_btn")
    async def approve(self, interaction: discord.Interaction, button: Button):
        if not self.is_moderator(interaction):
            await interaction.response.send_message("❌ У тебя нет прав для этого действия.", ephemeral=True)
            return

        guild = bot.get_guild(self.guild_id)
        member = guild.get_member(self.member_id)

        if member is None:
            await interaction.response.send_message("⚠️ Участник покинул сервер.", ephemeral=True)
            return

        # Выдаём роль
        role = guild.get_role(APPROVED_ROLE_ID)
        if role:
            try:
                await member.add_roles(role)
            except discord.Forbidden:
                pass

        # Уведомляем участника
        try:
            await member.send(f"✅ Твоя заявка на сервере **{guild.name}** была **одобрена**! Добро пожаловать!")
        except discord.Forbidden:
            pass

        # Обновляем embed
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.green()
        embed.add_field(name="📌 Статус", value=f"✅ Одобрено модератором {interaction.user.mention}", inline=False)

        self.approve.disabled = True
        self.reject.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="❌ Отклонить", style=discord.ButtonStyle.danger, custom_id="reject_btn")
    async def reject(self, interaction: discord.Interaction, button: Button):
        if not self.is_moderator(interaction):
            await interaction.response.send_message("❌ У тебя нет прав для этого действия.", ephemeral=True)
            return

        guild = bot.get_guild(self.guild_id)
        member = guild.get_member(self.member_id)

        if member:
            try:
                await member.send(f"❌ Твоя заявка на сервере **{guild.name}** была **отклонена**. Попробуй снова или обратись к администрации.")
            except discord.Forbidden:
                pass

        embed = interaction.message.embeds[0]
        embed.color = discord.Color.red()
        embed.add_field(name="📌 Статус", value=f"❌ Отклонено модератором {interaction.user.mention}", inline=False)

        self.approve.disabled = True
        self.reject.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)


# --- Автоудаление сообщений в канале анкеты ---
@bot.event
async def on_message(message: discord.Message):
    # Игнорируем сообщения бота
    if message.author.bot:
        return

    # Если сообщение в канале анкеты — удаляем (кроме закреплённого)
    if message.channel.id == ANKETA_CHANNEL_ID:
        if message.id == 1480016173952274562:  # сообщение с описанием — не трогаем
            return
        try:
            await asyncio.sleep(1)
            await message.delete()
        except discord.Forbidden:
            pass
        except discord.NotFound:
            pass
        return

    await bot.process_commands(message)


# --- Приветствие при входе на сервер ---
@bot.event
async def on_member_join(member: discord.Member):
    try:
        embed = discord.Embed(
            title="👋 Добро пожаловать!",
            description=(
                f"Привет, {member.mention}!\n\n"
                "Для вступления на сервер необходимо заполнить **анкету**.\n"
                "Нажми кнопку ниже и ответь на несколько вопросов. "
                "После одобрения администрацией ты получишь доступ к серверу!"
            ),
            color=discord.Color.blurple()
        )
        embed.set_footer(text="Rose FamQ • Анкета вступления")

        view = StartApplicationView()
        await member.send(embed=embed, view=view)
    except discord.Forbidden:
        # Если ЛС закрыты — пишем в системный канал
        if member.guild.system_channel:
            await member.guild.system_channel.send(
                f"{member.mention}, добро пожаловать! Открой личные сообщения, "
                f"чтобы получить анкету для вступления, или используй команду `/анкета`."
            )


# --- Кнопка «Заполнить анкету» в ЛС ---
class StartApplicationView(View):
    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(label="📝 Заполнить анкету", style=discord.ButtonStyle.primary)
    async def start(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(ApplicationModal())


# --- Слэш-команда /анкета для повторного заполнения ---
@bot.tree.command(name="анкета", description="Заполнить анкету вступления")
async def slash_anketa(interaction: discord.Interaction):
    await interaction.response.send_modal(ApplicationModal())


@bot.event
async def on_ready():
    await bot.tree.sync()
    await bot.change_presence(activity=discord.Game(name="Rose FamQ | Анкеты"))
    print(f"✅ Бот запущен как {bot.user} (ID: {bot.user.id})")
    print("Слэш-команды синхронизированы.")


bot.run(BOT_TOKEN)
