# Project: Splat [Discord] Bot

# Packages & Imports
# Discord Packages
import discord
from discord.ui import Select, View, Button
from discord import app_commands
from discord.ext import commands, tasks
from typing import Optional, Literal  # For command params
from datetime import timedelta, datetime  # For timeouts & timestamps
from enum import Enum  # For enums (select menus)

# Async Packages
import asyncio
import aiohttp
import aiomysql

# For random status
import random

# For forbidden word finder
from fuzzywuzzy import fuzz

# Environment Variables
from dotenv import load_dotenv
import os


class SplatBot(commands.Bot):
    def __init__(self, token: str, db_creds: list):
        # Initialize the bot
        super().__init__(command_prefix="splat ", intents=discord.Intents.all())

        # Variables
        self.token = token
        self.db = self.Database(creds=db_creds)
        # Add cogs
        asyncio.run(self.addCogs())

        print("[Core] Welcome to Splat Bot!")

    # Add the cogs (commands and events)
    async def addCogs(self):
        await self.add_cog(self.Tasks(self))
        await self.add_cog(self.SplatCommands(self))
        await self.add_cog(self.DMHandler(self))
        await self.add_cog(self.DatabaseHandler(self))

    # Pre-run checks
    def pre_run_checks(self):
        print("[Core] Running pre-run checks...")
        if not self.db.creds_check():
            raise Exception("Database credentials not set")

    # Run the bot
    def run(self):
        self.pre_run_checks()
        print("[Core] Running bot...")
        super().run(self.token)

    # Bot ready event
    async def on_ready(self):
        print("[Core] Bot is ready!")
        print(f"[Core] Logged in as {self.user}")

    # * Classes & Cogs
    # Database class for interacting with the database
    class Database:
        def __init__(self, creds: list):
            self.creds = creds

        # Check if credentials are set (not empty)
        def creds_check(self) -> bool:
            if len(self.creds) > 0:
                return True
            return False

        # Periodic Task: Test all database connections
        async def test_all_connections(self):
            print("[Database] Testing all connections...")
            self.functioning_creds = []
            for cred in self.creds:
                try:
                    async with aiomysql.connect(
                        host=cred["host"],
                        port=cred.get("port", 3306),
                        user=cred["user"],
                        password=cred["password"],
                        db=cred["db"],
                    ) as conn:
                        async with conn.cursor() as cur:
                            await cur.execute("SELECT 1")
                            print(
                                f"[Database] Connection to {cred['name']} successful!"
                            )
                            self.functioning_creds.append(cred)
                        conn.close()
                except Exception as e:
                    if e.args[0] == 2003:
                        print(
                            f"[Database] Connection to {cred['name']} failed: Host not found"
                        )
                    else:
                        print(f"[Database] Connection to {cred['name']} failed: {e}")
            if len(self.functioning_creds) == 0:
                print("[Database] No working connections found!")
                raise Exception("No working database connections found")
            print(f"[Database] {len(self.functioning_creds)} connections working!")
            return self.functioning_creds

        # Connect to the database with specified credentials
        async def connect(self, cred: dict):
            try:
                conn = await aiomysql.connect(
                    host=cred["host"],
                    port=cred.get("port", 3306),
                    user=cred["user"],
                    password=cred["password"],
                    db=cred["db"],
                )
                return conn
            except Exception as e:
                print(f"[Database] Connection to {cred['name']} failed: {e}")
                return None

        # Auto-connect (Connect to the first working database)
        async def auto_connect(self):
            if not hasattr(self, "functioning_creds"):
                await self.test_all_connections()
            if len(self.functioning_creds) > 0:
                for cred in self.functioning_creds:
                    conn = await self.connect(cred)
                    if conn:
                        return conn
            return None

        # Check database format
        async def check_database(self):
            print("[Database] Checking database format...")
            conn = await self.auto_connect()
            async with conn.cursor() as cur:
                await cur.execute("SHOW TABLES")
                tables = await cur.fetchall()
                await cur.close()
            tables = [table[0] for table in tables[0]]
            print(f"[Database] Tables: {tables}")

        # Read data from a table
        async def read_table(self, table: str, conn: aiomysql.Connection):
            async with conn.cursor() as cur:
                await cur.execute(f"SELECT * FROM {table}")
                result = await cur.fetchall()
                description = cur.description
                await cur.close()

            if result:
                return await self.convert_to_dict(result, description)
            return result

        async def convert_to_dict(self, result: list, description: list):
            return [
                dict(zip([column[0] for column in description], row)) for row in result
            ]

    # Facilitate database-related discord commands & interactions
    class DatabaseHandler(commands.Cog):
        def __init__(self, bot: "SplatBot"):
            self.bot = bot

        @commands.Cog.listener()
        async def on_ready(self):
            print("[Database Manager] Setting up database tasks...")
            # await self.test_connections.start()  #! For some reason nothing runs after this point
            print("[Database Manager] Listening for database commands...")

            # Check if the database is set up correctly
            await self.test_connections()
            await self.check_then_format()

        async def check_then_format(self):
            print("[Database Manager] Checking database format...")
            await self.bot.db.check_database()

        # Periodic task: Test all database connections
        # @tasks.loop(hours=6) <- Disabled due to glitches
        async def test_connections(self):
            print("[Database Manager] Testing all database connections...")
            try:
                self.functioning_creds = await self.bot.db.test_all_connections()
            except Exception as e:
                print(f"[Database Manager] Error running periodic task: {e}")
            else:
                print("[Database Manager] Done running task!")

        # Test command: fetch raw data from a table
        @app_commands.command(
            name="fetch-data", description="Fetch raw data from a database table"
        )
        async def test_fetch(self, interaction: discord.Interaction, table: str):
            print(f"[Database Manager] Command: Fetching data from table: {table}")
            conn = await self.bot.db.auto_connect()
            if conn is None:
                await interaction.response.send_message(
                    "No working database connections"
                )
                return
            try:
                result = await self.bot.db.read_table(table, conn)
            except Exception as e:
                if e.args[0] == 1146:
                    await interaction.response.send_message(
                        f"Table `{table}` not found"
                    )
                    return
                await interaction.response.send_message(f"Error fetching data: {e}")
                return
            await interaction.response.send_message(
                f"**Result**: \n```python\n{result}\n```"
            )
            conn.close()
            print(f"[Database Manager] Done fetching data from table: {table}")

    # Bot events (on_ready, on_message, etc.)
    class Tasks(commands.Cog):
        def __init__(self, bot: "SplatBot"):
            self.bot = bot

        # Random status task (changes every 24 hours)
        @tasks.loop(hours=24)
        async def random_status(self):
            custom_messages = [
                {"label": "hit the unsell button", "type": "game"},
                {
                    "label": "That's a good question, one I'm not aware of myself",
                    "type": "custom",
                },
                {"label": "you procrastinate", "type": "watching"},
                {"label": "🥔", "type": "game"},
                {"label": "There is nothing we can do", "type": "custom"},
            ]
            new_status = random.choice(custom_messages)
            print(
                f"[Tasks] Changing status to ({new_status['type']}) {new_status['label']}"
            )
            if new_status["type"] == "game":
                await self.bot.change_presence(
                    activity=discord.Game(
                        name=new_status["label"],
                        image="https://squid1127.strangled.net/caddy/files/assets/Splat%20multi%20use.png",
                    )
                )
            elif new_status["type"] == "custom":
                await self.bot.change_presence(
                    activity=discord.CustomActivity(
                        name=new_status["label"], emoji=new_status.get("emoji")
                    )
                )
            elif new_status["type"] == "watching":
                await self.bot.change_presence(
                    activity=discord.Activity(
                        type=discord.ActivityType.watching, name=new_status["label"]
                    )
                )
            print(f"[Tasks] Done changing status!")

        @commands.Cog.listener()
        async def on_ready(self):
            print(f"[Tasks] Running tasks...")
            self.random_status.start()
            print(f"[Tasks] Tasks started!")

    # Bot commands
    class SplatCommands(commands.Cog):
        def __init__(self, bot: "SplatBot"):
            self.bot = bot

        # Sync commands on bot ready
        @commands.Cog.listener()
        async def on_ready(self):
            print("[Commands] Syncing commands...")
            self.commands_list = await self.bot.tree.sync()
            print(f"[Commands] {len(self.commands_list)} Commands synced!")

        @app_commands.command(name="ping", description="Check if bot is online")
        async def ping(self, interaction: discord.Interaction):
            await interaction.response.send_message("Pong!")

    # Handle DMs using threads
    class DMHandler(commands.Cog):
        def __init__(self, bot: "SplatBot"):
            self.bot = bot

        # Handle incoming DMs
        async def handle_dm_in(self, message: discord.Message):
            dm_channel_id = int(os.getenv("BOT_DM_CHANNEL_ID"))
            self.dm_channel = self.bot.get_channel(
                dm_channel_id
            )  # TODO get from database instead
            print(f"[DMs] Incoming DM from {message.author.name}: {message.content}")

            # Get all threads and check if there is a thread titled with the user's ID
            threads = self.dm_channel.threads
            user_thread = None
            for thread in threads:
                if int(thread.name.split("&")[1]) == message.author.id:
                    user_thread = thread
                    break

            # If there is no thread, create one
            if user_thread is None:
                print(f"[DMs] Creating thread for {message.author.name}")
                user_thread = await self.dm_channel.create_thread(
                    name=f"{message.author.name}&{message.author.id}"
                )

            if message.reference:
                ref_message = await message.channel.fetch_message(
                    message.reference.message_id
                )
                reply_embed = discord.Embed(
                    title=f"",
                    description=ref_message.content,
                    color=discord.Color.blurple(),
                )
                reply_embed.set_author(
                    name=ref_message.author.name, icon_url=ref_message.author.avatar.url
                )
                await user_thread.send(embed=reply_embed)

            msg = f"||%%id&{message.id}%%||\n{message.content}"
            await user_thread.send(
                msg,
                allowed_mentions=discord.AllowedMentions.none(),
                files=[
                    await attachment.to_file() for attachment in message.attachments
                ],
            )

            await self.dm_channel.send(
                f"<@&1286884945851056191> {user_thread.mention} from {message.author.name}"
            )

        # Handle outgoing to DMs
        async def handle_dm_out(self, message: discord.Message):
            dm_channel_id = int(os.getenv("BOT_DM_CHANNEL_ID"))
            dm_channel = self.bot.get_channel(dm_channel_id)
            user_id = int(message.channel.name.split("&")[1])
            user = self.bot.get_user(user_id)

            print(f"[DMs] Outgoing DM to {user.name}: {message.content}")

            # Check if the message is a reply
            if message.reference:
                print("[DMs] Reply detected")
                ref_message = await message.channel.fetch_message(
                    message.reference.message_id
                )
                ref_msg = ref_message.content
                ref_msg_header = ref_msg.split("\n")[0]

                # Get the message content and replace the bot mention with the user mention
                msg = message.content.replace(self.bot.user.mention, user.mention)

                # Check if the message is a reference, and if so, reply to the reference message
                if ref_msg_header.startswith("||%%id&") and ref_msg_header.endswith(
                    "%%||"
                ):
                    print("[DMs] Reference found, sending as reply")
                    # Get the reference message ID from the header
                    ref_msg_id = int(ref_msg_header.strip("%%||").split("&")[1])

                    # Fetch the reference message from the user's dm channel
                    if not user.dm_channel:
                        users_dm_channel = await user.create_dm()
                    else:
                        users_dm_channel = user.dm_channel
                    reply = await user.dm_channel.fetch_message(ref_msg_id)

                    # Send the reply to the reference message
                    await reply.reply(
                        msg,
                        files=[
                            await attachment.to_file()
                            for attachment in message.attachments
                        ],
                    )
                    return
                print("[DMs] Reference not found, sending as normal")
                await message.channel.send(
                    "Warning: Reply detected but no reference found. Sending as normal."
                )

            await user.send(
                msg,
                files=[
                    await attachment.to_file() for attachment in message.attachments
                ],
            )
            return

        # Listen for messages (both incoming and outgoing)
        @commands.Cog.listener()
        async def on_message(self, message: discord.Message):
            # Ignore bot messages
            if message.author.bot:
                return

            # DM Handler
            # Incoming -> Forward to DM channel threads
            if isinstance(message.channel, discord.DMChannel):
                await self.handle_dm_in(message)
                return
            # Outgoing -> Forward to DM
            elif isinstance(
                message.channel, discord.Thread
            ) and message.channel.parent_id == int(os.getenv("BOT_DM_CHANNEL_ID")):
                await self.handle_dm_out(message)
                return

        @commands.Cog.listener()
        async def on_ready(self):
            print("[DMs] Listening for DMs...")

            # Future on_ready code here


load_dotenv()
token = os.getenv("BOT_TOKEN")
db_creds = [
    {
        "name": "Dev Database (Docker)",
        "host": "mysql",
        "user": os.getenv("MYSQL_USER"),
        "password": os.getenv("MYSQL_PASSWORD"),
        "db": os.getenv("MYSQL_DATABASE"),
    },
    {
        "name": "Dev Database (localhost)",
        "host": "localhost",
        "user": os.getenv("MYSQL_USER"),
        "password": os.getenv("MYSQL_PASSWORD"),
        "db": os.getenv("MYSQL_DATABASE"),
    },
    {
        "name": "Dev Database (Tailscale)",
        "host": "casaos.golden-hamlet.ts.net",
        "user": os.getenv("MYSQL_USER"),
        "password": os.getenv("MYSQL_PASSWORD"),
        "db": os.getenv("MYSQL_DATABASE"),
    },
]

splat = SplatBot(token=token, db_creds=db_creds)
splat.run()
