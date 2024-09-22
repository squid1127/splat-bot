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
import cryptography  # For database encryption

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
        await self.add_cog(self.Tasks(self)) # Tasks -> Random status
        await self.add_cog(self.SplatCommands(self)) # Misc commands -> Ping
        await self.add_cog(self.DMHandler(self)) # Handle DMs -> Forward to DM threads
        await self.add_cog(self.DatabaseHandler(self)) # Database <=> Discord Interactions -> Sync commands, test connections, perodic database tasks
        await self.add_cog(self.GuildsCheck(self)) # Guilds & Channels -> Register guilds and channels based on messages
        await self.add_cog(self.AntiBrainrot(self)) # Anti-Brainrot -> Banned words filter

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
            self.working = False
            self.data = self.DbData()

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
        async def auto_connect(self) -> aiomysql.Connection:
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
            print("[Database] Connecting to database...")
            try:
                conn = await self.auto_connect()
                if conn is None:
                    raise Exception("No working database connections")
            except Exception as e:
                print(f"[Database] Error connecting to database: {e}")
                return

            # Fetch all tables
            async with conn.cursor() as cur:
                await cur.execute("SHOW TABLES")
                tables = await cur.fetchall()
                await cur.close()
            tables = [table[0] for table in tables]
            print(f"[Database] Tables: {tables}")

            # Check if tables exist, create if not
            tables_created = 0
            tables_failed = 0

            # Check admins table
            if "admin_users" not in tables:
                print("[Database] Admins table not found, creating...")
                query = """
                DROP TABLE IF EXISTS admin_users;
                CREATE TABLE
                admin_users (
                    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                    discord_id BIGINT NOT NULL,
                    username VARCHAR(255) NOT NULL,
                    name VARCHAR(255) NOT NULL
                );
                """
                try:
                    await self.execute_query(query, conn)
                    print("[Database] Admins table created!")
                    tables_created += 1
                except Exception as e:
                    print(f"[Database] Error creating admins table: {e}")
                    tables_failed += 1

            # Check guilds table
            if ("guilds" not in tables) or ("channels" not in tables):
                print("[Database] Guilds and/or channels table not found, creating...")
                query = """
                DROP TABLE IF EXISTS channels;

                DROP TABLE IF EXISTS guilds;

                CREATE TABLE
                guilds (
                    guild_id BIGINT NOT NULL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    enable_owen_mode BOOLEAN DEFAULT FALSE,
                    enable_banned_words BOOLEAN DEFAULT FALSE,
                    admin_mode BOOLEAN DEFAULT FALSE
                );

                CREATE TABLE
                channels (
                    channel_id BIGINT NOT NULL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    guild_id BIGINT NOT NULL REFERENCES guilds(guild_id),
                    channel_mode VARCHAR(255),
                    disable_banned_words BOOLEAN DEFAULT FALSE
                );
                """
                try:
                    await self.execute_query(query, conn)
                    print("[Database] Guilds & Members tables created!")
                    tables_created += 1
                except Exception as e:
                    print(f"[Database] Error creating tables: {e}")
                    tables_failed += 1

            # Check banned words table
            if "banned_words" not in tables:
                print("[Database] Banned words table not found, creating...")
                query = """
                DROP TABLE IF EXISTS banned_words;
                CREATE TABLE
                banned_words (
                    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                    word VARCHAR(255) NOT NULL
                );
                """
                try:
                    await self.execute_query(query, conn)
                    print("[Database] Banned words table created!")
                    tables_created += 1
                except Exception as e:
                    print(f"[Database] Error creating banned words table: {e}")
                    tables_failed += 1

            # Check whitelist table
            if "whitelist" not in tables:
                print("[Database] Whitelist table not found, creating...")
                query = """
                DROP TABLE IF EXISTS whitelist;
                CREATE TABLE
                whitelist (
                    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                    word VARCHAR(255) NOT NULL
                );
                """
                try:
                    await self.execute_query(query, conn)
                    print("[Database] Whitelist table created!")
                    tables_created += 1
                except Exception as e:
                    print(f"[Database] Error creating whitelist table: {e}")
                    tables_failed += 1

            # Close connection
            print("[Database] Closing connection...")
            if conn is not None:
                conn.close()

            # Print summary
            print("[Database] Done checking database format!")
            if tables_created > 0:
                print(f"[Database] Created {tables_created} tables")
            if tables_failed > 0:
                print(f"[Database] ERROR: Failed to create {tables_failed} tables")
                return

            print("[Database] Database is good to go!")
            self.working = True

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
        
        async def add_entry(self, table: str, data: dict, conn: aiomysql.Connection):
            columns = ", ".join(data.keys())
            placeholders = ", ".join(["%s"] * len(data))
            values = tuple(data.values())
            query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})" 
            print(query)
            
            async with conn.cursor() as cur:
                await cur.execute(query, values)
                await conn.commit()
                await cur.close()
            
            #!await self.execute_query(query, conn) #! This doesn't work for some reason
 
            print(f"[Database] Added entry to {table}: {data}")
    
        async def update_entry(self, table: str, data: dict, conn: aiomysql.Connection):
            columns = ", ".join(data.keys())
            placeholders = ", ".join(["%s"] * len(data))
            values = tuple(data.values())
            query = f"UPDATE {table} SET {columns} = {placeholders}"
            
            await self.execute_query(query, conn, values)
            print(f"[Database] Updated entry in {table}: {data}")


        # Execute generic SQL query
        async def execute_query(self, query: str, conn: aiomysql.Connection, values: tuple = None):
            async with conn.cursor() as cur:
                await cur.execute(query, values)    
                result = await cur.fetchall()
                description = cur.description
                await cur.close()

            if result:
                try:
                    return await self.convert_to_dict(result, description)
                except:
                    pass
            return result

        async def convert_to_dict(self, result: list, description: list):
            return [
                dict(zip([column[0] for column in description], row)) for row in result
            ]

        # Read and update all tables
        async def read_all(self, conn: aiomysql.Connection):
            print("[Database] Reading all tables...")
            guilds = await self.read_table("guilds", conn)
            channels = await self.read_table("channels", conn)
            banned_words = await self.read_table("banned_words", conn)
            whitelist = await self.read_table("whitelist", conn)
            admins = await self.read_table("admin_users", conn)

            # Write to data object
            self.data.update(
                guilds=guilds,
                channels=channels,
                banned_words=banned_words,
                whitelist=whitelist,
                admins=admins,
            )

            print(f"[Database] Done reading all tables!\n{self.data}")
            
        # Autmatically connect and read all tables
        async def update_db(self):
            conn = await self.auto_connect()
            if conn is None:
                print("[Database] No working database connections")
                return
            await self.read_all(conn)
            conn.close()
            
        

        class DbData:
            def __init__(self):
                # Database tables
                self.guilds = []
                self.channels = []
                self.banned_words = []
                self.whitelist = []
                self.admins = []

                self.write_count = 0

            def __str__(self):
                return f"""Database Data:
Guilds: {self.guilds}
Channels: {self.channels}
Banned Words: {self.banned_words}
Whitelist: {self.whitelist}
Admins: {self.admins}"""

            def update(
                self,
                guilds: list = None,
                channels: list = None,
                banned_words: list = None,
                whitelist: list = None,
                admins: list = None,
            ):
                if guilds:
                    self.guilds = guilds
                if channels:
                    self.channels = channels
                if banned_words:
                    self.banned_words = banned_words
                if whitelist:
                    self.whitelist = whitelist
                if admins:
                    self.admins = admins
                self.write_count += 1

            def is_data_empty(self):
                if (
                    len(self.guilds) == 0
                    and len(self.channels) == 0
                    and len(self.banned_words) == 0
                    and len(self.whitelist) == 0
                    and len(self.admins) == 0
                ):
                    return True
                return False

            def clear(self):
                self.guilds = []
                self.channels = []
                self.banned_words = []
                self.whitelist = []
                self.admins = []
                self.write_count = 0

    # Facilitate database-related discord commands & interactions
    class DatabaseHandler(commands.Cog):
        def __init__(self, bot: "SplatBot"):
            self.bot = bot

        @commands.Cog.listener()
        async def on_ready(self):
            print("[Database Manager] Setting up database tasks...")
            # await self.test_connections.start()  #! For some reason nothing runs after this point
            print("[Database Manager] Listening for database commands...")

            # Check if the database is set up correctly, loop until it is
            while not self.bot.db.working:
                await self.test_connections()
                await self.check_then_format()
                if self.bot.db.working:
                    break
                print(
                    "[Database Manager] Database not set up correctly, retrying in 60 seconds..."
                )
                await asyncio.sleep(60)

            # Start periodic tasks
            print("[Database Manager] Database is working correctly! Starting tasks...")
            await self.pull_data.start()
            await self.test_connections.start()

        async def check_then_format(self):
            print("[Database Manager] Checking database format...")
            await self.bot.db.check_database()

        # Periodic task: Test all database connections
        @tasks.loop(hours=6)
        async def test_connections(self, periodic: bool = True):
            if periodic:
                print("[Database Manager] Running periodic task...")
            print("[Database Manager] Testing all database connections...")
            try:
                self.functioning_creds = await self.bot.db.test_all_connections()
            except Exception as e:
                print(f"[Database Manager] Error running periodic task: {e}")
            else:
                print("[Database Manager] Done running task!")

        # Periodic task: Pull all data from the database
        @tasks.loop(hours=8)
        async def pull_data(self, periodic: bool = True):
            if periodic:
                print("[Database Manager] Running periodic task...")
            print("[Database Manager] Pulling data from database...")
            conn = await self.bot.db.auto_connect()
            if conn is None:
                print("[Database Manager] No working database connections")
                return
            try:
                await self.bot.db.read_all(conn)
            except Exception as e:
                print(f"[Database Manager] Error pulling data: {e}")
            else:
                print("[Database Manager] Done pulling data!")
            conn.close()

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

    # Handle guilds and channels, sync with database
    class GuildsCheck(commands.Cog):
        def __init__(self, bot: "SplatBot"):
            self.bot = bot

        @commands.Cog.listener()
        async def on_message(self, message: discord.Message):
            # Ignore bot messages
            if message.author.bot:
                return

            if not self.bot.db.working:
                print("[Guilds] Message received but database not set up correctly, ignoring...")
                return

            db_changed = False
            # Check if guild is registered
            guild_data = None
            for guild in self.bot.db.data.guilds:
                if guild["guild_id"] == message.guild.id:
                    guild_data = guild
                    break
            if not guild_data:
                print(
                    f"[Guilds] Guild {message.guild.name} not registered, registering..."
                )
                if await self.add_guild(message.guild):
                    db_changed = True
                
                
            # Check if channel is registered
            channel_data = None
            for channel in self.bot.db.data.channels:
                if channel["channel_id"] == message.channel.id:
                    channel_data = channel
                    break
            if not channel_data:
                print(
                    f"[Channels] Channel {message.channel.name} not registered, registering..."
                )
                if await self.add_channel(message.channel):
                    db_changed = True
            
            if db_changed:
                print("[Guilds] Database changed, pulling data...")
                await self.bot.db.update_db()
                

            # # Check if the message contains any banned words
            # if await self.check_banned_words(message):
            #     return
        
        # Register a guild in the database
        async def add_guild(self, guild: discord.Guild, owen_mode: bool = False, banned_words: bool = False, admin_mode: bool = False):
            try:
                print(f"[Guilds] Adding guild {guild.name} to database...")
                conn = await self.bot.db.auto_connect()
                data = {
                    "guild_id": guild.id,
                    "name": guild.name,
                    "enable_owen_mode": int(owen_mode),
                    "enable_banned_words": int(banned_words),
                    "admin_mode": int(admin_mode),
                }
                await self.bot.db.add_entry("guilds", data, conn)
                print(f"[Guilds] Added guild {guild.name} to database")
                return True
            except Exception as e:
                print(f"[Guilds] Error adding guild {guild.name} to database: {e}")
                return False
        
        # Register a channel in the database
        async def add_channel(self, channel: discord.TextChannel, channel_mode: str = None, disable_banned_words: bool = False):
            try:
                print(f"[Channels] Adding channel {channel.name} to database...")
                conn = await self.bot.db.auto_connect()
                data = {
                    "channel_id": channel.id,
                    "name": channel.name,
                    "guild_id": channel.guild.id,
                    "channel_mode": channel_mode,
                    "disable_banned_words": int(disable_banned_words),
                }
                await self.bot.db.add_entry("channels", data, conn)
                print(f"[Channels] Added channel {channel.name} to database")
                return True
            except Exception as e:
                print(f"[Channels] Error adding channel {channel.name} to database: {e}")
                return False
            
    # Anti-Brainrot (Banned Words) Filter
    class AntiBrainrot(commands.Cog):
        def __init__(self, bot: "SplatBot"):
            self.bot = bot
            self.working = False
        
        @commands.Cog.listener()
        async def on_ready(self):
            if len(self.bot.db.data.banned_words) == 0:
                print("[Anti-Brainrot] No banned words found in database")
                print("[Anti-Brainrot] Waiting for banned words...")
                while len(self.bot.db.data.banned_words) == 0:
                    await asyncio.sleep(2)
                print("[Anti-Brainrot] Banned words found!")
            self.working = True
            print("[Anti-Brainrot] Listening for banned words...")
            
        @commands.Cog.listener()
        async def on_message(self, message: discord.Message):
            if not self.working:
                print("[Anti-Brainrot] Banned words not set up correctly, ignoring...")
                return
            
            # Scan message for banned words
            found = await self.is_banned(message.content.lower())
            
            if found == 0:
                return
            
            # Carry out punishment (5 minute timeout/detected word)
            timeout_length = len(found) * 5
            timeout = timedelta(minutes=timeout_length)
            embed = discord.Embed(
                title="Anti-Brainrot",
                description=f"Your message contained a banned brainrot phrase. You have been timed out for {timeout_length} minutes.",
                color=discord.Color.red(),
            )
            for phrase in found:
                embed.add_field(name="Matched", value=f"{phrase[0]} -> {phrase[1]}%", inline=False)
            embed.set_footer(text="This server has a zero-tolerance policy for brainrot. If you believe this is a mistake, use the /report-brainrot command once your timeout is over.")
            try:
                await message.reply("@everyone", embed=embed)
                await message.author.timeout(timeout, reason="Used brainrot")
            except Exception as e:
                embed.description = f"Your message contained a banned brainrot phrase. However, it appears you cannot be timed out. Please refrain from using brainrot in the future."
                await message.reply("@everyone", embed=embed)
            
            
        async def is_banned(self, phrase: str) -> int:
            # Scan using fuzzy matching
            fuzzy_threshold = 80
            fuzzy_method = fuzz.partial_ratio
            found_banned = []
            for word in self.bot.db.data.banned_words:
                if fuzzy_method(word["word"], phrase) >= fuzzy_threshold:
                    found_banned.append((word["word"], fuzzy_method(word["word"], phrase)))
            if len(found_banned) == 0:
                return 0
            
            # Scan for whitelist words
            for word in self.bot.db.data.whitelist:
                if word["word"] in phrase:
                    return 0
                
            # If we've reached this point, the phrase is banned
            print(f"[Anti-Brainrot] Banned phrase detected: {phrase} (Matched: {found_banned})")
            return len(found_banned)
            
            
            

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
