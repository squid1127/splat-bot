"""
Splat-Bot
~~~~~~~~~
A general-purpose Discord bot build using discord.py, and MySQL.

:copyright: (c) 2024-present squid1127, warriordragonid
"""

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

# For web frontend
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn

# For random status
import random

# For forbidden word finder
from fuzzywuzzy import fuzz

# Environment Variables
from dotenv import load_dotenv
import os

# Downtime warning
import downreport


class SplatBot(commands.Bot):
    def __init__(self, token: str, shell: int, db_creds: list, web_port: int = None):
        # Initialize the bot
        super().__init__(command_prefix="splat ", intents=discord.Intents.all())

        # Variables
        self.token = token
        self.db = self.Database(creds=db_creds)
        self.perms = self.Permissions(self)
        self.web = self.WebUI(self, web_port)
        self.shell = self.Shell(self, shell)

        # Add cogs
        asyncio.run(self.addCogs())

        print("[Core] Welcome to Splat Bot!")

    # Add the cogs (commands and events)
    async def addCogs(self):
        await self.add_cog(self.Tasks(self))  # Tasks -> Random status
        await self.add_cog(self.SplatCommands(self))  # Misc commands -> Ping
        await self.add_cog(self.DMHandler(self))  # Handle DMs -> Forward to DM threads
        await self.add_cog(
            self.DatabaseHandler(self)
        )  # Database <=> Discord Interactions -> Sync commands, test connections, perodic database tasks
        await self.add_cog(
            self.GuildsCheck(self)
        )  # Guilds & Channels -> Register guilds and channels based on messages
        await self.add_cog(
            self.AntiBrainrot(self)
        )  # Anti-Brainrot -> Banned words filter
        await self.add_cog(
            self.ShellManager(self, self.shell)
        )  # Shell -> Manage shell commands and input

    # Pre-run checks
    def pre_run_checks(self):
        print("[Core] Running pre-run checks...")
        if not self.db.creds_check():
            raise Exception("Database credentials not set")

    # Run the bot
    def run(self):
        self.pre_run_checks()
        print("[Core] Setting up database...")
        db_success = asyncio.run(
            self.cogs["DatabaseHandler"].setup()
        )  # Set up the database before running the bot
        if db_success == 0:
            raise Exception("Database setup failed")
        print("[Core] Starting bot & web server...")
        asyncio.run(self.start())

    async def start(self):
        await asyncio.gather(self.web.run(), super().start(self.token))

    # Bot ready event
    async def on_ready(self):
        print("[Core] Bot is ready!")
        print(f"[Core] Logged in as {self.user}")

    # * Classes & Cogs
    # Discord shell
    class Shell:
        def __init__(self, bot: "SplatBot", channel_id: int):
            self.bot = bot

            self.channel_id = channel_id

        # Start the shell
        async def start(self):
            try:
                self.channel = self.bot.get_channel(self.channel_id)
                print("[Shell] Shell channel found!")
                print("[Shell] Starting logging...")
                await asyncio.sleep(1)
                await self.log(
                    f"Bot has successfully started. **Database**: {'working' if self.bot.db.working else 'not working'}",
                    title="Bot Started",
                    msg_type="success",
                    cog="Shell",
                )
            except:
                print("[Shell] Shell channel not found!")
                return

        async def create_embed(
            self,
            message: str,
            title: str = None,
            msg_type: str = "info",
            cog: str = None,
        ):

            if msg_type == "error":
                color = discord.Color.red()
            elif msg_type == "success":
                color = discord.Color.green()
            elif msg_type == "warning":
                color = discord.Color.orange()
            else:
                color = discord.Color.blurple()
            embed = discord.Embed(
                title=f"[{msg_type.upper()}] {title}",
                description=message,
                color=color,
            )
            embed.set_author(name=cog)
            embed.set_footer(text="Powered by Splat Bot")
            return embed

        # Send a log message
        async def log(
            self,
            message: str,
            title: str = None,
            msg_type: str = "info",
            cog: str = None,
        ):
            embed = await self.create_embed(message, title, msg_type, cog)
            await self.channel.send(
                ("@everyone" if msg_type == "error" else ""), embed=embed
            )

    # Shell commands
    class ShellManager(commands.Cog):
        def __init__(self, bot: "SplatBot", shell: "SplatBot.Shell"):
            self.bot = bot
            self.shell = shell

        @commands.Cog.listener()
        async def on_ready(self):
            print("[Shell Handler] Starting shell...")
            await self.shell.start()

            # Regester shell commands
            await self.bot.add_command(self.shell_command)
            await self.bot.add_command(self.stop_bot)

        @commands.Cog.listener()
        async def on_message(self, message: discord.Message):
            if message.author.bot:
                return
            if message.channel.id != self.bot.shell.channel_id:
                return

        async def enforce_shell_channel(self, ctx: commands.Context):
            if ctx.channel.id != self.bot.shell.channel_id:
                return False
            return True

        # Shell only commands
        # Manage db
        @commands.command(name="db")
        async def shell_command(self, ctx: commands.Context, *, command: str):
            if not await self.enforce_shell_channel(ctx):
                return

            # Pull data from the database
            if command.startswith("pull") or command.startswith("update"):
                command = command.split(" ")[1:]
                print("[Shell Manager] DB Pull command received")
                try:
                    conn = await self.bot.db.auto_connect()
                    await self.bot.db.pull_all(conn)
                except Exception as e:
                    print(f"[Shell Manager] Error pulling database: {e}")
                    embed = await self.shell.create_embed(
                        f"An error was encountered when pulling the database: {e}",
                        title="Database Pull Error",
                        msg_type="error",
                        cog="Shell Manager -> Database",
                    )
                    await ctx.send(embed=embed)
                else:
                    print("[Shell Manager] Database pulled!")
                    embed = await self.shell.create_embed(
                        "All database data has been successfully pulled from MYSQL.",
                        title="Database Updated",
                        msg_type="success",
                        cog="Shell Manager -> Database",
                    )
                    embed = self.bot.db.data.embed_fields(embed)
                    await ctx.send(embed=embed)
                conn.close()

                print("[Shell Manager] CMD Finished")
                return

            # List current database data
            if command.startswith("list") or command.startswith("ls"):
                print("[Shell Manager] DB List command received")
                embed = await self.shell.create_embed(
                    "Showing all database data...",
                    title="Database Data",
                    msg_type="info",
                    cog="Shell Manager -> Database",
                )
                embed = self.bot.db.data.embed_fields(embed)
                await ctx.send(embed=embed)
                print("[Shell Manager] CMD Finished")
                return

            # Test all database connections
            if command.startswith("test"):
                print("[Shell Manager] DB Test command received")
                try:
                    await self.bot.db.test_all_connections()
                except Exception as e:
                    print(f"[Shell Manager] Error testing database connections: {e}")
                    embed = await self.shell.create_embed(
                        f"An error was encountered when testing database connections: {e}",
                        title="Database Test Error",
                        msg_type="error",
                        cog="Shell Manager -> Database",
                    )
                    await ctx.send(embed=embed)
                else:
                    print("[Shell Manager] Database connections tested!")
                    embed = await self.shell.create_embed(
                        "Database connections tested successfully!",
                        title="Database Test Complete",
                        msg_type="success",
                        cog="Shell Manager -> Database",
                    )
                    functioning_creds = ""
                    for cred in self.bot.db.functioning_creds:
                        functioning_creds += f"\n- {cred['name']}{' <- In use' if cred['name'] == self.bot.db.last_used_cred['name'] else ''}"
                    embed.add_field(
                        name="Functioning Credentials",
                        value=functioning_creds,
                        inline=False,
                    )
                    await ctx.send(embed=embed)
                print("[Shell Manager] CMD Finished")
                return

            if command.startswith("add"):
                command = " ".join(command.split(" ")[1:])
                if not (command.startswith("banned") or command.startswith(
                    "whitelist"
                )):
                    embed = await self.shell.create_embed(
                        "Invalid command. Use `banned` or `whitelist` to add a word to the banned words or whitelist list. Example: `splat db add banned sigma`",
                        title="Syntax Error",
                        msg_type="error",
                        cog="Shell Manager -> Database",
                    )
                    await ctx.send(embed=embed)
                    return

                table = "banned_words" if command.startswith("banned") else "whitelist"

                command = " ".join(command.split(" ")[1:])
                conn = await self.bot.db.auto_connect()
                if conn is None:
                    embed = await self.shell.create_embed(
                        "No working database connections. To test connections, use `splat db test`.",
                        title="Database Error",
                        msg_type="error",
                        cog="Shell Manager -> Database",
                    )
                    await ctx.send(embed=embed)
                    return

                try:
                    await self.bot.db.add_entry(table, {"word": command}, conn)
                except Exception as e:
                    embed = await self.shell.create_embed(
                        f"An error was encountered when adding the word `{command}` to the banned words list: {e}",
                        title="Database Error",
                        msg_type="error",
                        cog="Shell Manager -> Database",
                    )
                    await ctx.send(embed=embed)
                    return
                try:
                    await self.bot.db.update_db()
                except Exception as e:
                    embed = await self.shell.create_embed(
                        f"Word `{command}` added to the banned words list, but an error was encountered when updating the database: {e}. Changes may not be reflected immediately.",
                        title="Database Error",
                        msg_type="error",
                        cog="Shell Manager -> Database",
                    )
                    await ctx.send(embed=embed)
                    return

                if table == "banned_words":
                    success = command in [
                        word["word"] for word in self.bot.db.data.banned_words
                    ]
                else:
                    success = command in [
                        word["word"] for word in self.bot.db.data.whitelist
                    ]

                if success:
                    embed = await self.shell.create_embed(
                        f"Word `{command}` added to the {'banned list' if table == 'banned_words' else 'whitelist'} successfully!",
                        title="Database Updated",
                        msg_type="success",
                        cog="Shell Manager -> Database",
                    )
                    await ctx.send(embed=embed)
                else:
                    embed = await self.shell.create_embed(
                        f"An unknown error was encountered when adding the word `{command}` to the {'banned list' if table == 'banned_words' else 'whitelist'}.",
                        title="Database Error",
                        msg_type="error",
                        cog="Shell Manager -> Database",
                    )
                    await ctx.send(embed=embed)
                    
                conn.close()
                return
            
            if command.startswith("remove") or command.startswith("rm"):
                command = " ".join(command.split(" ")[1:])
                if not (command.startswith("banned") or command.startswith(
                    "whitelist"
                )):
                    embed = await self.shell.create_embed(
                        "Invalid command. Use `banned` or `whitelist` to remove a word from the banned words or whitelist list. Example: `splat db remove banned sigma`",
                        title="Syntax Error",
                        msg_type="error",
                        cog="Shell Manager -> Database",
                    )
                    await ctx.send(embed=embed)
                    return

                table = "banned_words" if command.startswith("banned") else "whitelist"

                command = " ".join(command.split(" ")[1:])
                conn = await self.bot.db.auto_connect()
                if conn is None:
                    embed = await self.shell.create_embed(
                        "No working database connections. To test connections, use `splat db test`.",
                        title="Database Error",
                        msg_type="error",
                        cog="Shell Manager -> Database",
                    )
                    await ctx.send(embed=embed)
                    return

                if table == "banned_words":
                    words = [word["word"] for word in self.bot.db.data.banned_words]
                else:
                    words = [word["word"] for word in self.bot.db.data.whitelist]

                if command not in words:
                    embed = await self.shell.create_embed(
                        f"Word `{command}` not found in the {'banned list' if table == 'banned_words' else 'whitelist'}.",
                        title="Database Error",
                        msg_type="error",
                        cog="Shell Manager -> Database",
                    )
                    await ctx.send(embed=embed)
                    return

                try:
                    query = f"DELETE FROM {table} WHERE word = %s"
                    await self.bot.db.execute_query(query, conn, (command,))
                except Exception as e:
                    embed = await self.shell.create_embed(
                        f"An error was encountered when removing the word `{command}` from the {'banned list' if table == 'banned_words' else 'whitelist'}: {e}",
                        title="Database Error",
                        msg_type="error",
                        cog="Shell Manager -> Database",
                    )
                    await ctx.send(embed=embed)
                    return
                try:
                    await self.bot.db.update_db()
                except Exception as e:
                    embed = await self.shell.create

            embed = await self.shell.create_embed(
                "Preform datbase tasks.",
                title="Database Command Usage",
                msg_type="info",
                cog="Shell Manager -> Database",
            )
            embed.add_field(
                name="Commands",
                value="- `pull` - Pull all data from the database\n- `list` - List all data in the database without pulling\n- `test` - Test all database connections",
                inline=False,
            )
            await ctx.send(embed=embed)
            
        @commands.command(name="stop")
        async def stop_bot(self, ctx: commands.Context, *, command: str = None):
            if not command.startswith("**confirm**"):
                embed = await self.shell.create_embed(
                    "To stop the bot, use `splat stop **confirm**`.",
                    title="Stop Bot",
                    msg_type="warning",
                    cog="Shell Manager -> Bot",
                )
                await ctx.send(embed=embed)
                return
            
            embed = await self.shell.create_embed(
                "Bot stopping...",
                title="Bot Stopping",
                msg_type="warning",
                cog="Shell Manager -> Bot",
            )
            await ctx.send(embed=embed)
            print("[Shell Manager] Stopping bot...")
            await self.bot.close()

    # Manage Permissions
    class Permissions:
        def __init__(self, bot: "SplatBot"):
            self.admins = []
            self.bot = bot

        def bot_admins(self):
            return self.bot.db.data.admins

        async def handle_check_bot_admin(
            self,
            interaction: discord.Interaction,
            error_msg: str = "You must be an administator of splat-bot to use this command.",
        ) -> bool:
            bot_admins = self.bot_admins()
            if len(bot_admins) == 0:
                await interaction.response.send_message(
                    "Bot admin list is empty. This is likely due to a database error. Please try again later.",
                    ephemeral=True,
                )
                print("[Permissions] Bot admin list is empty")
                return False
            for admin in bot_admins:
                if admin["discord_id"] == interaction.user.id:
                    return True
            await interaction.response.send_message(error_msg, ephemeral=True)

        async def handle_check_perm(
            self, interaction: discord.Interaction, has_perm: bool
        ) -> bool:
            # Check if dm
            if interaction.guild is None:
                await interaction.response.send_message(
                    "This command can only be used in a server.", ephemeral=True
                )
                return False

            if interaction.user.guild_permissions.administrator:
                return True
            if has_perm:
                return True

            await interaction.response.send_message(
                "You do not have permission to use this command.", ephemeral=True
            )
            return False

    # Database class for interacting with the database
    class Database:
        def __init__(self, creds: list):
            self.creds = creds
            self.working = False
            self.data = self.DbData()
            self.last_used_cred = None

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
                self.last_used_cred = cred
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
                    channel_mode VARCHAR(255) DEFAULT 'Normal',
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
        async def execute_query(
            self, query: str, conn: aiomysql.Connection, values: tuple = None
        ):
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
        async def pull_all(self, conn: aiomysql.Connection):
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
            await self.pull_all(conn)
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

            def embed_fields(self, embed: discord.Embed = None):
                print("[Database Data] Generating embed fields...")
                try:
                    banned_words = [word["word"] for word in self.banned_words]
                    whitelist = [word["word"] for word in self.whitelist]
                    admins = [admin["name"] for admin in self.admins]
                    guilds = [guild["name"] for guild in self.guilds]
                    print(self.guilds, self.channels)
                    channels = [
                        f"{guild['name']} -> {channel['name']}"
                        for channel in self.channels
                        for guild in self.guilds
                        if guild["guild_id"] == channel["guild_id"]
                    ]
                except Exception as e:
                    print(f"[Database Data] Error generating embed fields: {e}")
                    return embed
                fields = [
                    {
                        "name": "Banned Words",
                        "value": "- " + "\n- ".join(map(str, banned_words)),
                        "inline": False,
                    },
                    {
                        "name": "Whitelist",
                        "value": "- " + "\n- ".join(map(str, whitelist)),
                        "inline": False,
                    },
                    {
                        "name": "Admins",
                        "value": "- " + "\n- ".join(map(str, admins)),
                        "inline": False,
                    },
                    {
                        "name": "Guilds",
                        "value": "- " + "\n- ".join(map(str, guilds)),
                        "inline": False,
                    },
                    {
                        "name": "Channels",
                        "value": "- " + "\n- ".join(map(str, channels)),
                        "inline": False,
                    },
                ]
                if embed:
                    for field in fields:
                        print(field)
                        embed.add_field(
                            name=field["name"], value=field["value"], inline=False
                        )
                    return embed
                print("[Database Data] Done generating embed fields!")
                return fields

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

        # Run prior to bot start
        async def setup(self):
            print("[Database Manager] Attempting to set up database...")

            # Check if the database is set up correctly, loop until it is
            attempts = 0
            while not self.bot.db.working:
                try:
                    await self.test_connections(
                        False
                    )  # Test all connections & credentials
                    await self.check_then_format()  # Check database is formatted correctly
                    await self.bot.db.update_db()  # Pull data from the database
                except Exception as e:
                    print(f"[Database Manager] Error setting up database: {e}")
                if self.bot.db.working:
                    break
                print(
                    "[Database Manager] Connection to database failed, retrying in 15 seconds..."
                )
                attempts += 1
                if attempts > 5:
                    print("[Database Manager] Database setup failed!")
                    return 0
                await asyncio.sleep(15)
            print("[Database Manager] Database setup complete!")

            if self.bot.db.data.is_data_empty():
                print(
                    "[Database Manager] Warning! No data found in database, potentially due to a database error."
                )
                return 1
            elif self.bot.db.working:
                print("[Database Manager] Database is fully operational!")
                return 2
            print("[Database Manager] Database setup failed!")
            return 0

        @commands.Cog.listener()
        async def on_ready(self):
            # Start periodic tasks
            print("[Database Manager] Starting tasks...")
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
                await self.bot.db.pull_all(conn)
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
            # Sync app commands
            self.commands_list = await self.bot.tree.sync()
            # Sync non-app commands
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
                print(
                    "[Guilds] Message received but database not set up correctly, ignoring..."
                )
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
        async def add_guild(
            self,
            guild: discord.Guild,
            owen_mode: bool = False,
            banned_words: bool = False,
            admin_mode: bool = False,
        ):
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
        async def add_channel(
            self,
            channel: discord.TextChannel,
            channel_mode: str = "Normal",
            disable_banned_words: bool = False,
        ):
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
                print(
                    f"[Channels] Error adding channel {channel.name} to database: {e}"
                )
                return False

        class ChannelModes(Enum):
            Normal = "Normal"
            BotAnnoucements = "Announcements"

        # Modify channel settings
        @app_commands.command(
            name="channel-modify", description="Admins: Modify channel modes, etc."
        )
        @app_commands.describe(
            channel="The channel to modify",
            mode="The mode to set the channel to. Options: Normal, Announcements (Recieve annoucements about splat-bot) (More to come). BOT ADMIN only: DM Log, System Log, System Shell",
        )
        async def modify_channel(
            self,
            interaction: discord.Interaction,
            channel: discord.TextChannel = None,
            mode: ChannelModes = ChannelModes.Normal,
            disable_banned_words: bool = False,
        ):
            if channel is None:
                channel = interaction.channel

            if not await self.bot.perms.handle_check_perm(
                interaction, interaction.user.guild_permissions.manage_channels
            ):
                return

            # Send bot is thinking indicator
            await interaction.response.defer()

            conn = await self.bot.db.auto_connect()
            if conn is None:
                await interaction.response.send_message(
                    "Could not connect to backend database", ephemeral=True
                )
                return
            channel_data = None
            for channel in self.bot.db.data.channels:
                if channel["channel_id"] == channel.id:
                    channel_data = channel
                    break
            if not channel_data:
                await interaction.response.send_message("Channel not found in database")
                try:
                    conn.close()
                except:
                    pass
                return

            channel_data["channel_mode"] = mode
            channel_data["disable_banned_words"] = int(disable_banned_words)
            try:
                await self.bot.db.update_entry("channels", channel_data, conn)
            except Exception as e:
                await interaction.response.send_message(
                    f"Error updating channel: {e}", ephemeral=True
                )
                try:
                    conn.close()
                except:
                    pass
                return

            try:
                await self.bot.db.update_db()
            except Exception as e:
                await interaction.response.send_message(
                    f"Channel has be Channel successfully set to {mode} mode with banned words {'disabled' if disable_banned_words else 'enabled'}. However, the database could not be updated. Changes may take a while to reflect"
                )
                try:
                    conn.close()
                except:
                    pass
                return

            await interaction.response.send_message(
                f"Channel successfully set to {mode} mode with banned words {'disabled' if disable_banned_words else 'enabled'}"
            )
            conn.close()

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
            if len(found) == 0:
                return

            # Carry out punishment (5 minute timeout/detected word)
            timeout_length = len(found) * 5
            print(f"[Anti-Brainrot] Detected banned words in message, timing out for {timeout_length} minutes")
            timeout = timedelta(minutes=timeout_length)
            print("debug 0")
            embed = discord.Embed(
                title="Anti-Brainrot",
                description=f"Your message contained a banned brainrot phrase. You have been timed out for {timeout_length} minutes.",
                color=discord.Color.red(),
            )
            print("debug 1")
            for phrase in found:
                print("debug 1.5")
                embed.add_field(
                    name="Matched", value=f"{phrase[0]} -> {phrase[1]}%", inline=False
                )
            print("debug 2")
            embed.set_footer(
                text="This server has a zero-tolerance policy for brainrot. If you believe this is a mistake, use the /report-brainrot command once your timeout is over."
            )
            print("[Anti-Brainrot] Attempting to time out user...")
            try:
                await message.author.timeout(timeout, reason="Used brainrot")
                await message.reply(embed=embed)
            except discord.Forbidden:
                embed.description = f"Your message contained a banned brainrot phrase. However, it appears you cannot be timed out. Please refrain from using brainrot in the future."
                await message.reply(embed=embed)

        async def is_banned(self, phrase: str) -> int:
            # Scan using fuzzy matching
            fuzzy_threshold = 80
            fuzzy_method = fuzz.partial_ratio
            found_banned = []
            for word in self.bot.db.data.banned_words:
                if fuzzy_method(word["word"], phrase) >= fuzzy_threshold:
                    found_banned.append(
                        (word["word"], fuzzy_method(word["word"], phrase))
                    )
            if len(found_banned) == 0:
                return 0

            # Scan for whitelist words
            for word in self.bot.db.data.whitelist:
                if word["word"] in phrase:
                    return 0

            # If we've reached this point, the phrase is banned
            print(
                f"[Anti-Brainrot] Banned phrase detected: {phrase} (Matched: {found_banned})"
            )
            return found_banned

    # Flask-based web UI
    class WebUI:
        def __init__(self, bot: "SplatBot", host: str = "0.0.0.0", port: int = 3000):
            self.bot = bot
            self.app = FastAPI()
            self.host = host
            self.port = port

            @self.app.get("/")
            async def read_root():
                return {"Hello": "World"}

        async def run(self):
            config = uvicorn.Config(self.app, host="0.0.0.0", port=8000)
            server = uvicorn.Server(config)
            await server.serve()
