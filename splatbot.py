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
import tabulate  # For tabular data
import cryptography  # For database encryption

# For web frontend
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn

# For random status
import random

# For forbidden word finder
from fuzzywuzzy import fuzz

# Downtime warning
import downreport

import re

# Database code
from database import Database

class SplatBot(commands.Bot):
    def __init__(self, token: str, shell: int, db_creds: list, web_port: int = None):
        # Initialize the bot
        super().__init__(command_prefix="splat:", intents=discord.Intents.all())

        # Variables
        self.shell_commands = {
            "help": {
                "cog": "ShellManager",
                "description": "Show help message",
            },
            "db": {
                "cog": "DatabaseHandler",
                "description": "Perform database maintenance tasks.",
            },
            "brainrot": {
                "cog": "AntiBrainrot",
                "description": "Manage banned words and whitelist.",
            },
            "br": {
                "cog": "AntiBrainrot",
                "description": "Alias for `brainrot`",
            },
            "guilds": {
                "cog": "GuildsCheck",
                "description": "Manage guilds and admin-config",
            },
            "channels": {
                "cog": "GuildsCheck",
                "description": "Manage channels and channel-config",
            },
            "config": {
                "cog": "Config",
                "description": "Manage bot configuration",
            },
        }

        self.token = token
        self.db = Database(db_creds)
        self.perms = self.Permissions(self)
        self.shell = self.Shell(self, shell)

        self.docker = self.is_docker()

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
            self.ShellManager(self, self.shell, self.shell_commands)
        )  # Shell -> Manage shell commands and input
        await self.add_cog(self.Config(self))  # Config -> Manage bot configuration

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
            raise ConnectionError("Database failed after multiple attempts")
        print("[Core] Starting bot & web server...")
        asyncio.run(self.start())

    async def start(self):
        await super().start(self.token)

    # Bot ready event
    async def on_ready(self):
        print("[Core] Bot is ready!")
        print(f"[Core] Logged in as {self.user}")

    # Check for docker
    def is_docker(self) -> bool:
        """Check if the bot is running in a docker container"""
        try:
            with open("/proc/1/cgroup", "rt") as ifh:
                return "docker" in ifh.read()
        except:
            return False

    # * Classes & Cogs
    # Discord shell
    class Shell:
        def __init__(self, bot: "SplatBot", channel_id: int):
            self.bot = bot

            self.channel_id = channel_id
            self.interactive_mode = None

        # Start the shell
        async def start(self):
            try:
                self.channel = self.bot.get_channel(self.channel_id)
                print("[Shell] Shell channel found!")
                print("[Shell] Starting logging...")
                await asyncio.sleep(1)
                await self.log(
                    f"Bot has successfully started. **Database**: {'working' if self.bot.db.working else 'not working'} **Docker**: {'yes' if self.bot.docker else 'no'}",
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

            if msg_type == "error" or msg_type == "fatal_error":
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
            plain_text: str = None,
        ):
            embed = await self.create_embed(message, title, msg_type, cog)
            await self.channel.send(
                (
                    plain_text
                    if plain_text
                    else ("@everyone" if msg_type == "fatal_error" else "")
                ),
                embed=embed,
            )

        class ShellCommand:
            def __init__(
                self,
                name: str,
                cog: str,
                shell: "SplatBot.Shell",
                channel: discord.TextChannel = None,
            ):
                self.name = name
                self.cog = cog
                self.shell = shell
                if channel:
                    self.channel = channel
                else:
                    self.channel = self.shell.channel

            async def info(
                self,
                description: str,
                title: str,
                fields: list = None,
                footer: str = None,
            ):
                embed = await self.shell.create_embed(
                    description, title, "info", self.cog
                )
                if fields:
                    for field in fields:
                        embed.add_field(
                            name=field["name"],
                            value=field["value"],
                            inline=field.get("inline", False),
                        )
                if footer:
                    embed.set_footer(text=footer)
                await self.channel.send(embed=embed)

            async def success(
                self,
                description: str,
                title: str,
                fields: list = None,
                footer: str = None,
            ):
                embed = await self.shell.create_embed(
                    description, title, "success", self.cog
                )
                if fields:
                    for field in fields:
                        embed.add_field(
                            name=field["name"],
                            value=field["value"],
                            inline=field.get("inline", False),
                        )
                if footer:
                    embed.set_footer(text=footer)
                await self.channel.send(embed=embed)

            async def error(
                self,
                description: str,
                title: str,
                fields: list = None,
                footer: str = None,
            ):
                embed = await self.shell.create_embed(
                    description, title, "error", self.cog
                )
                if fields:
                    for field in fields:
                        embed.add_field(
                            name=field["name"],
                            value=field["value"],
                            inline=field.get("inline", False),
                        )
                if footer:
                    embed.set_footer(text=footer)
                await self.channel.send(embed=embed)

            async def warning(
                self,
                description: str,
                title: str,
                fields: list = None,
                footer: str = None,
            ):
                embed = await self.shell.create_embed(
                    description, title, "warning", self.cog
                )
                if fields:
                    for field in fields:
                        embed.add_field(
                            name=field["name"],
                            value=field["value"],
                            inline=field.get("inline", False),
                        )
                if footer:
                    embed.set_footer(text=footer)

                await self.channel.send(embed=embed)

            async def raw(self, *args, **kwargs):
                await self.channel.send(*args, **kwargs)

    # Shell commands
    class ShellManager(commands.Cog):
        def __init__(
            self, bot: "SplatBot", shell: "SplatBot.Shell", shell_commands: dict
        ):
            self.bot = bot
            self.shell = shell
            self.shell_commands = shell_commands

        @commands.Cog.listener()
        async def on_ready(self):
            print("[Shell Handler] Starting shell...")
            await self.shell.start()

            # # Regester shell commands
            # await self.bot.add_command(self.shell_command)
            # await self.bot.add_command(self.stop_bot)

        # Shell command listener
        @commands.Cog.listener()
        async def on_message(self, message: discord.Message):
            if message.author.bot:
                return
            if message.channel.id != self.bot.shell.channel_id:
                return

            await self.process_shell(message)

        # Shell command listener but message edited
        @commands.Cog.listener()
        async def on_message_edit(
            self, before: discord.Message, after: discord.Message
        ):
            if before.author.bot:
                return
            if before.channel.id != self.bot.shell.channel_id:
                return
            await self.process_shell(after)

        # Process shell commands
        async def process_shell(self, message: discord.Message):
            if self.shell.interactive_mode:
                if message.content == "~exit":
                    self.shell.interactive_mode = None
                    await self.shell.log(
                        "Exited interactive mode",
                        title="Interactive Mode",
                        msg_type="info",
                    )
                    return
                try:
                    cog = self.shell.interactive_mode[0]

                    await self.bot.cogs[cog].shell_callback(
                        self.shell.interactive_mode[1],
                        message.content,
                        self.shell.ShellCommand(
                            self.shell.interactive_mode[1],
                            cog,
                            self.shell,
                            message.channel,
                        ),
                    )
                except Exception as e:
                    print(f"[Shell Manager] Shell interactive_mode error: {e}")
                    await self.shell.log(
                        f"Failed to execute command in interactive mode: {e}\n Use ~exit to exit interactive mode",
                        title="Interactive Mode Error",
                        msg_type="error",
                        cog="ShellManager",
                    )
                return

            if message.content.lower() == "splat":
                await self.shell.log(
                    "Please provide a command to run. Use `splat help` for a list of commands.",
                    title="No Command Provided",
                    msg_type="error",
                    cog="ShellManager",
                )
                return

            if not message.content.startswith("splat "):
                return

            command = message.content.split(" ")[1]
            query = " ".join(message.content.split(" ")[2:])

            if command not in self.shell_commands:
                await self.shell.log(
                    f"Unknown command: `{command}`",
                    title="Unknown Command",
                    msg_type="error",
                    cog="Shell Manager",
                )
                return

            cog = self.shell_commands[command]["cog"]

            await self.bot.cogs[cog].shell_callback(
                command,
                query,
                self.shell.ShellCommand(command, cog, self.shell, message.channel),
            )

        async def enforce_shell_channel(self, ctx: commands.Context):
            if ctx.channel.id != self.bot.shell.channel_id:
                return False
            return True

        async def shell_callback(
            self, command: str, query: str, shell_command: "SplatBot.Shell.ShellCommand"
        ):
            print(f"[Shell Manager] Recieved shell command: {command} | Query: {query}")

            if command == "help":
                print("[Shell Manager] Help command received")
                commands = "\n".join(
                    [
                        f"**{cmd}**: {self.shell_commands[cmd]['description']}"
                        for cmd in self.shell_commands
                    ]
                )

                fields = [{"name": "Commands", "value": commands, "inline": False}]
                try:
                    await shell_command.info(
                        "To run my shell functions, use `splat [command]`. See below for possible options",
                        title="Shell Help",
                        fields=fields,
                    )
                except Exception as e:
                    print(f"[Shell Manager] Error fetching help: {e}")
                    await shell_command.error(
                        f"An error was encountered when fetching help: {e}",
                        title="Help Error",
                    )

        @commands.Cog.listener()
        async def on_error(self, event, *args, **kwargs):
            print(f"[Shell Manager] Error in event {event}: {args[0]}")
            await self.shell.log(
                f"Error in event {event}: {args[0]}",
                title="Unhandled Error",
                msg_type="error",
                cog="ShellManager",
            )

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

    # Facilitate database-related discord commands & interactions
    class DatabaseHandler(commands.Cog):
        def __init__(self, bot: "SplatBot"):
            self.bot = bot

        # Run prior to bot start
        async def setup(self):
            print("[Database Manager] Executing pre-run database setup...")

            # Check if the database is set up correctly, loop until it is
            attempts = 0
            while not self.bot.db.working:
                print(f"[Database Manager] Attempt {attempts + 1}")
                try:
                    await self.test_connections(
                        False
                    )  # Test all connections & credentials
                    await self.check_then_format()  # Check database is formatted correctly
                    await self.bot.db.update_all_auto()  # Pull data from the database
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
                await self.bot.db.update_all_conn(conn)
            except Exception as e:
                print(f"[Database Manager] Error pulling data: {e}")
            else:
                print("[Database Manager] Done pulling data!")
            conn.close()

        # # Test command: fetch raw data from a table
        # @app_commands.command(
        #     name="fetch-data", description="Fetch raw data from a database table"
        # )
        # async def test_fetch(self, interaction: discord.Interaction, table: str):
        #     print(f"[Database Manager] Command: Fetching data from table: {table}")
        #     conn = await self.bot.db.auto_connect()
        #     if conn is None:
        #         await interaction.response.send_message(
        #             "No working database connections"
        #         )
        #         return
        #     try:
        #         result = await self.bot.db.read_table(table, conn)
        #     except Exception as e:
        #         if e.args[0] == 1146:
        #             await interaction.response.send_message(
        #                 f"Table `{table}` not found"
        #             )
        #             return
        #         await interaction.response.send_message(f"Error fetching data: {e}")
        #         return
        #     await interaction.response.send_message(
        #         f"**Result**: \n```python\n{result}\n```"
        #     )
        #     conn.close()
        #     print(f"[Database Manager] Done fetching data from table: {table}")

        async def shell_callback(
            self, command: str, query: str, shell_command: "SplatBot.Shell.ShellCommand"
        ):
            print(
                f"[Database Manager] Recieved shell command: {command} | Query: {query}"
            )
            if command == "db":
                if query.startswith("pull") or query.startswith("update"):
                    print("[Database Manager] DB Pull command received")
                    try:
                        conn = await self.bot.db.auto_connect()
                        await self.bot.db.update_all_conn(conn)
                    except Exception as e:
                        try:
                            conn.close()
                        except:
                            pass
                        print(f"[Database Manager] Error pulling database: {e}")
                        await shell_command.error(
                            f"An error was encountered when pulling the database: {e}",
                            title="Database Pull Error",
                        )
                    else:
                        print("[Database Manager] Database pulled!")
                        await shell_command.success(
                            "All database data has been successfully pulled from MYSQL.",
                            title="Database Updated",
                        )
                        conn.close()
                        return
                elif query.startswith("test") or query.startswith("connections"):
                    print("[Database Manager] Test command received")

                    try:
                        await self.bot.db.test_all_connections()
                    except Exception as e:
                        print(f"[Database Manager] Error testing connections: {e}")
                        await shell_command.error(
                            f"An error was encountered when testing database connections: {e}",
                            title="Database Test Error",
                        )
                    else:
                        print("[Database Manager] Done testing connections!")
                        connections = ""
                        for i in self.bot.db.creds:
                            if i in self.bot.db.functioning_creds:
                                if i == self.bot.db.last_used_cred:
                                    connections += (
                                        f"**{i['name']}**: Working (Last used)\n"
                                    )
                                else:
                                    connections += f"**{i['name']}**: Working\n"
                            else:
                                connections += f"**{i['name']}**: Not working\n"

                        fields = [
                            {
                                "name": "Connections",
                                "value": connections,
                                "inline": False,
                            }
                        ]

                        await shell_command.success(
                            "All database connections have been successfully tested.",
                            title="Database Connections Tested",
                            fields=fields,
                        )
                        return

                if query.startswith("exec"):
                    print("[Database Manager] Exec command received")
                    query = query.split("exec ")[1]

                    try:
                        conn = await self.bot.db.auto_connect()
                        result = await self.bot.db.execute_query(query, conn)
                    except Exception as e:
                        try:
                            conn.close()
                        except:
                            pass
                        print(f"[Database Manager] Error executing query: {e}")
                        await shell_command.error(
                            f"An error was encountered when executing the query: {e}",
                            title="Database Query Error",
                        )
                        return
                    else:
                        print("[Database Manager] Query executed!")
                        conn.close()

                        await shell_command.success(
                            "Query executed.\n```python\n" + result + "\n```",
                            title="Query Executed",
                        )
                        return
                if query.startswith("shell"):
                    print("[Database Manager] DB Shell command received")
                    await shell_command.info(
                        "You are now in the database shell. Type `~exit` to exit.",
                        title="Database Shell",
                    )

                    self.bot.shell.interactive_mode = (
                        "DatabaseHandler",
                        "db_shell_callback",
                    )

                    return

                # if query.startswith("list") or query.startswith("ls"):
                #     print("[Database Manager] List command received")
                #     try:
                #         conn = await self.bot.db.auto_connect()
                #         tables = await self.bot.db.execute_query("SHOW TABLES", conn)
                #     except Exception as e:
                #         try:
                #             conn.close()
                #         except:
                #             pass
                #         print(f"[Database Manager] Error listing tables: {e}")
                #         await shell_command.error(
                #             f"An error was encountered when listing tables: {e}",
                #             title="Database List Error",
                #         )
                #         return
                #     else:
                #         print("[Database Manager] Tables listed!")
                #         fields = self.bot.db.data.embed_fields()
                #         print(fields)
                #         await shell_command.success(
                #             "Tables listed successfully.",
                #             title="Tables Listed",
                #             fields=fields,
                #         )
                #         conn.close()
                #         return

                if query.startswith("check-format"):
                    print("[Database Manager] Check format command received")
                    await self.check_then_format()
                    await shell_command.success(
                        "Database format checked and updated.",
                        title="Database Format Checked",
                    )
                    return

                if query.startswith("help"):
                    print("[Database Manager] Help command received")
                    fields = [
                        {
                            "name": "Commands",
                            "value": "**pull**: Pull data from the database\n**test**: Test all database connections\n**exec [query]**: Execute a query\n**list**: List all tables & data in the database\n**shell**: Enter the database shell\n**check-format**: Check and format the database tables",
                            "inline": False,
                        }
                    ]
                    await shell_command.info(
                        "To run my database functions, use `splat db [command]`. See below for possible options",
                        title="Database Help",
                        fields=fields,
                    )
                    return

                # If no command specified, do status summary

                print("[Database Manager] Status summary triggered (default)")
                print("[Database Manager] Testing all connections...")
                try:
                    await self.bot.db.test_all_connections()
                except Exception as e:
                    print(f"[Database Manager] Error testing connections: {e}")
                    if e.args[0] == "No working database connections found":
                        fields = []
                        for i in self.bot.db.creds:
                            fields.append(
                                {
                                    "name": i["name"],
                                    "value": f"Host: {i['host']}\nUser: {i['user']}\nDatabase: {i['db']}",
                                    "inline": False,
                                }
                            )
                        await shell_command.error(
                            "No working database connections found. Below are all of the connections",
                            title="Database Status - No Connections",
                            fields=fields,
                        )
                        return
                    await shell_command.error(
                        f"An error was encountered when testing database connections: {e}",
                        title="Database Status - Connection Error",
                    )
                    return

                print("[Database Manager] Done testing connections!")
                connections = ""
                for i in self.bot.db.creds:
                    if i in self.bot.db.functioning_creds:
                        if i == self.bot.db.last_used_cred:
                            connections += f"**{i['name']}**: Working (Last used)\n"
                        else:
                            connections += f"**{i['name']}**: Working\n"
                    else:
                        connections += f"**{i['name']}**: Not working\n"

                print("[Database Manager] Pulling data from database...")

                try:
                    conn = await self.bot.db.auto_connect()
                    await self.bot.db.update_all_conn(conn)
                except Exception as e:
                    try:
                        conn.close()
                    except:
                        pass
                    print(f"[Database Manager] Error pulling database: {e}")
                    await shell_command.error(
                        f"An error was encountered when pulling the database: {e}",
                        title="Database Status - Pull Error",
                    )
                else:
                    conn.close()

                entires = f"**Guilds**: {len(self.bot.db.data.guilds)}\n**Channels**: {len(self.bot.db.data.channels)}\n**Banned Words**: {len(self.bot.db.data.brainrot)}\n**Whitelist**: {len(self.bot.db.data.whitelist)}\n**Admins**: {len(self.bot.db.data.admins)}\n**Config**: {len(self.bot.db.data.config)}"

                debug = f"**Write Count**: {self.bot.db.data.write_count}\nDatabase Username{self.bot.db.last_used_cred['user']}\nDatabase db: {self.bot.db.last_used_cred['db']}"

                fields = [
                    {
                        "name": "Connections",
                        "value": connections,
                        "inline": False,
                    },
                    {
                        "name": "Entries",
                        "value": entires,
                        "inline": False,
                    },
                ]

                if self.bot.db.data.is_data_empty():
                    summary = "Database is operational, but no data was found. This is likely due to a database error."
                else:
                    summary = "Backend database is operational and up to date. Use `splat help db` for database commands."

                await shell_command.info(
                    summary,
                    title="Database Status",
                    fields=fields,
                )

            # Interactive mode -> Database shell
            elif command == "db_shell_callback":
                try:
                    conn = await self.bot.db.auto_connect()
                    result = await self.bot.db.execute_query(
                        query, conn, pretty_table=True
                    )
                    try:
                        await conn.commit()
                    except:
                        print("[Database Manager] No commit needed (Commit failed)")
                    else:
                        print("[Database Manager] Commit successful")
                except Exception as e:
                    try:
                        conn.close()
                    except:
                        pass
                    print(f"[Database Manager] Error executing query: {e}")
                    possible_errors = {
                        1064: "Syntax Error",
                        1146: "Table Not Found",
                        1045: "Access Denied",
                    }

                    error = possible_errors.get(e.args[0])
                    if error:
                        message = f'{error} ({e.args[0]}): "{e.args[1]}"'
                    else:
                        message = f'Error {e.args[0]}: "{e.args[1]}"'
                    await shell_command.raw(
                        "```python\n"
                        + message
                        + "\n```\nTip: To exit the shell, type `~exit`"
                    )
                    return
                else:
                    print("[Database Manager] Query executed!")
                    # is result a list?
                    if isinstance(result, list):
                        print("[Database Manager] Result is a list")
                        print(result)
                        result = tabulate.tabulate(result, tablefmt="simple_grid")
                    if isinstance(result, tuple):
                        print("[Database Manager] Result is a tuple")
                        print(result)
                        if result == ([], None):
                            result = "Query executed successfully"
                        else:
                            result = f"Result: {result[0]}\nDescription: {result[1]}"
                    await shell_command.raw("```\n" + result + "\n```")
                    conn.close()
                    return

    # Manage Config
    class Config(commands.Cog):
        def __init__(self, bot: "SplatBot"):
            self.bot = bot
            
        async def get_entry(self, name: str, conn: aiomysql.Connection):
            """Get a config entry value (Requires a connection)"""
            for entry in self.bot.db.data.config:
                if entry["name"] == name:
                    return (entry["value"], entry["hidden"])
            return None
        
        async def set_entry(self, name: str, value: str, conn: aiomysql.Connection):
            """Set a config entry value (Requires a connection)"""
            for entry in self.bot.db.data.config:
                if entry["name"] == name:
                    await self.bot.db.update_entry("config", {"name": name}, {"value": value}, conn)
                    return True
            await self.bot.db.add_entry("config", {"name": name, "value": value}, conn)
            return True
            
        def key_syntax_check(self, key: str) -> bool:
            """Check if a key is valid for a config entry
            - Must be alphanumeric or underscore
            - Must be lowercase
            """
            pattern = re.compile(r'^[a-z0-9_]+$')
            return bool(pattern.match(key))
        
        # Shell callback
        async def shell_callback(self, command: str, query: str, shell_command: "SplatBot.Shell.ShellCommand"):
            if command == "config":
                
                if query.startswith("wizard"):
                    print("[Config Manager] Wizard command received")
                    
                    self.bot.shell.interactive_mode = ("Config", "config_shell_callback")
                    self.wizard_state = "home"
                    self.wizard_key = None
                    await shell_command.info("You are now in the config wizard. Type `~exit` to exit.", title="Config Wizard")
                    await shell_command.raw(
                        "home> Welcome to the config wizard! Enter a config setting to get or set its value, or use `list` to list all keys. Type `~exit` to exit."
                    )
                
                if query.startswith("get"):
                    print("[Config Manager] Get command received")
                    key = query.split("get ")[1]
                    try:
                        conn = await self.bot.db.auto_connect()
                        await self.bot.db.update_all_conn(conn)
                        get = await self.get_entry(key, conn)
                    except Exception as e:
                        print(f"[Config Manager] Error getting entry: {e}")
                        await shell_command.error(
                            f"An error was encountered when getting the entry: {e}",
                            title="Config Get Error",
                        )
                    else:
                        value = get[0]
                        if get[1]:
                            await shell_command.error(
                                f"Value for {key} is hidden",
                                title="Config Get Hidden",
                            )
                        await shell_command.success(
                            f"Value for {key}: {value}",
                            title="Config Get Success",
                        )
                    finally:
                        conn.close()
                    return

                if query.startswith("set"):
                    print("[Config Manager] Set command received")
                    key = query.split("set ")[1]
                    try:
                        conn = await self.bot.db.auto_connect()
                        await self.set_entry(key, "True", conn)
                        await self.bot.db.update_all_conn(conn)
                    except Exception as e:
                        print(f"[Config Manager] Error setting entry: {e}")
                        await shell_command.error(
                            f"An error was encountered when setting the entry: {e}",
                            title="Config Set Error",
                        )
                    else:
                        await shell_command.success(
                            f"Value for {key} set to True",
                            title="Config Set Success",
                        )
                    finally:
                        conn.close()
                    return
                        
                print("[Config Manager] List command received")
                await shell_command.info(
                    "Here are all of the config options:\n- " + "\n- ".join([entry["name"] for entry in self.bot.db.data.config]),
                    title="Config Keys",
                )
            
            if command == "config_shell_callback":
                try:
                        conn = await self.bot.db.auto_connect()
                    # while True:
                        # Home state
                        if self.wizard_state == "home":
                            if query == "list":
                                await shell_command.info(
                                    "Here are all of the config options:\n- " + "\n- ".join([entry["name"] for entry in self.bot.db.data.config]),
                                    title="Config Keys",
                                )
                                return
                            if query in [entry["name"] for entry in self.bot.db.data.config]:
                                self.wizard_key = query
                                get = await self.get_entry(query, conn)
                                if get[1]:
                                    await shell_command.raw(
                                        f"{query}> Found setting {query}, but its value is hidden. ]"
                                    )
                                else:
                                    await shell_command.raw(
                                        f"{query}> Found setting {query}.\n```\n{value}\n```"
                                    )
                                await shell_command.raw("Would you like to set a new value? (yes/no)")
                                self.wizard_state = "key_selected"
                                return
                            
                            self.wizard_key = query
                            await shell_command.raw(
                                f"{query}> Setting {query} not found. Would you like to create a new setting? (yes/no)"
                            )
                            self.wizard_state = "key_new"
                            return

                        if self.wizard_state == "key_selected":
                            if query == "yes":
                                await shell_command.raw(f"{self.wizard_key}> Enter a new value for {self.wizard_key}")
                                self.wizard_state = "key_set"
                                return
                            if query == "no":
                                await shell_command.raw("home> Enter a config setting to get or set its value, or use `list` to list all keys. Type `~exit` to exit.")
                                self.wizard_state = "home"
                                return
                            await shell_command.raw(f"{self.wizard_key}> Invalid input: {query}")
                            return
                        if self.wizard_state == "key_new":
                            if query == "yes":
                                await shell_command.raw(f"{self.wizard_key}> Enter a new value for {self.wizard_key}")
                                self.wizard_state = "key_set"
                                return
                            if query == "no":
                                await shell_command.raw("home> Enter a config setting to get or set its value, or use `list` to list all keys. Type `~exit` to exit.")
                                self.wizard_state = "home"
                                return
                            await shell_command.raw(f"{self.wizard_key}> Invalid input: {query}")
                            return
                        if self.wizard_state == "key_set":
                            await self.set_entry(self.wizard_key, query, conn)
                            await self.bot.db.update_all_conn(conn)
                            await shell_command.raw(f"{self.wizard_key}> Value for {self.wizard_key} set to {query}")
                            await shell_command.raw("home> Enter a config setting to get or set its value, or use `list` to list all keys. Type `~exit` to exit.")
                            self.wizard_state = "home"
                            return
                        
                except Exception as e:
                    await shell_command.error(
                        f"An unknown error encountered: {e}",
                        title="Config Wizard - Error",
                    )
                
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
            self.commands_info = [
                {
                    "name": "ping",
                    "description": "Check if bot is online",
                },
                {
                    "name": "help-splat",
                    "description": "Get help with Splat commands",
                },
                {
                    "name": "dev-excuse",
                    "description": "Get a random developer excuse",
                },
                {
                    "name": "joke",
                    "description": "Get a random joke",
                },
                {
                    "name": "random-verse",
                    "description": "Get a random Bible verse",
                },
                {
                    "name": "cat",
                    "description": "Get a random cat picture",
                },
                {
                    "name": "cat-fact",
                    "description": "Get a random cat fact",
                },
            ]
            self.help_fields = [
                {
                    "name": "Running Commands",
                    "description": "To run a command, type `/[command]`",
                },
                {
                    "name": "Commands",
                    "special": "commands",
                },
                {
                    "name": "Splat in your server",
                    "description": "You can use me in your own server! To do so, click on my profile and select 'Add App!'",
                },
            ]

        async def report_error(self, command: str, error: Exception):
            await self.bot.shell.log(
                f"[Commands] Error running command: {command} | {error}",
                title="Application Command Error",
                cog="SplatCommands",
                msg_type="error",
            )

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

        @app_commands.command(
            name="help-splat", description="Get help with Splat commands"
        )
        async def help_splat(self, interaction: discord.Interaction):
            embed = discord.Embed(
                title="Splat-Bot Help",
                description="Splat-bot (The 2nd), the general purpose bot featuring random commands, extensive server-management, brainrot enforcement, and so much more! Built in Python.",
                color=discord.Color.blurple(),
            )
            commands_field = ""
            for command in self.commands_info:
                commands_field += f"`{command['name']}`: {command['description']}\n"
            for field in self.help_fields:
                if field.get("special") == "commands":
                    embed.add_field(
                        name=field["name"], value=commands_field, inline=False
                    )
                else:
                    embed.add_field(
                        name=field["name"], value=field["description"], inline=False
                    )
            embed.set_footer(text="Made with love by CubbScratchStudios ❤️")
            await interaction.response.send_message(embed=embed)

        # Random api command: Get dev excuses
        @app_commands.command(
            name="dev-excuse", description="Get a random developer excuse"
        )
        async def dev_excuse(self, interaction: discord.Interaction):
            api = "https://api.devexcus.es/"
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(api) as response:
                        data = await response.json()
                        excuse = data["text"]

                embed = discord.Embed(
                    title="Developer Excuse",
                    description=excuse,
                    color=discord.Color.blurple(),
                )
                embed.set_footer(text="Powered by devexcus.es")
                await interaction.response.send_message(embed=embed)
                return
            except Exception as e:
                print(f"[Commands] Error fetching dev excuse: {e}")
                embed = discord.Embed(
                    title="Developer Excuse: Error",
                    description=f"Error fetching excuse: {e}",
                    color=discord.Color.red(),
                )
                await interaction.response.send_message(embed=embed)
                await self.report_error("dev-excuse", e)
                return

        # Random api command: Get random joke
        @app_commands.command(name="joke", description="Get a random joke")
        async def joke(self, interaction: discord.Interaction):
            api = "https://official-joke-api.appspot.com/random_joke"
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(api) as response:
                        data = await response.json()
                        setup = data["setup"]
                        punchline = data["punchline"]

                embed = discord.Embed(
                    title="Random Joke",
                    description=setup,
                    color=discord.Color.blurple(),
                )
                embed.add_field(name="Punchline", value="||" + punchline + "||")
                embed.set_footer(text="Powered by official-joke-api.appspot.com")
                await interaction.response.send_message(embed=embed)
                return
            except Exception as e:
                embed = discord.Embed(
                    title="Random Joke: Error",
                    description=f"Error fetching joke: {e}",
                    color=discord.Color.red(),
                )
                await interaction.response.send_message(embed=embed)
                await self.report_error("joke", e)
                return

        # Random api command: Bible verse :)
        @app_commands.command(
            name="random-verse", description="Get a random Bible verse"
        )
        async def random_verse(self, interaction: discord.Interaction):
            api = "https://beta.ourmanna.com/api/v1/get/?format=json"
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(api) as response:
                        data = await response.json()
                        verse = data["verse"]["details"]["text"]
                        reference = data["verse"]["details"]["reference"]

                embed = discord.Embed(
                    title="Random Bible Verse",
                    description=verse,
                    color=discord.Color.blurple(),
                )
                embed.set_footer(text=f"{reference} | Powered by ourmanna.com")
                await interaction.response.send_message(embed=embed)
                return
            except Exception as e:
                embed = discord.Embed(
                    title="Random Bible Verse: Error",
                    description=f"Error fetching verse: {e}",
                    color=discord.Color.red(),
                )
                await interaction.response.send_message(embed=embed)
                await self.report_error("random-verse", e)
                return

        # Random api command: Get random cat fact
        @app_commands.command(name="cat-fact", description="Get a random cat fact")
        async def cat_fact(self, interaction: discord.Interaction):
            api = "https://catfact.ninja/fact"
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(api) as response:
                        data = await response.json()
                        fact = data["fact"]

                embed = discord.Embed(
                    title="Random Cat Fact",
                    description=fact,
                    color=discord.Color.blurple(),
                )
                embed.set_footer(text="Powered by catfact.ninja")
                await interaction.response.send_message(embed=embed)
                return
            except Exception as e:
                embed = discord.Embed(
                    title="Random Cat Fact: Error",
                    description=f"Error fetching fact: {e}",
                    color=discord.Color.red(),
                )
                await interaction.response.send_message(embed=embed)
                await self.report_error("cat-fact", e)
                return

        # Random api command: Get cat image :)
        @app_commands.command(name="cat", description="Get a random cat image")
        async def cat(self, interaction: discord.Interaction):
            api = "https://api.thecatapi.com/v1/images/search"
            api_key = await self.bot.db.config_get("cat_api_key")
            if api_key:
                headers = {"x-api-key": api_key}
            else:
                headers = None

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(api, headers=headers) as response:
                        data = await response.json()
                        image = data[0]["url"]

                embed = discord.Embed(
                    title="Meow :3", description="Here's a cat!", color=0x9D948D
                )
                embed.set_image(url=image)
                embed.set_footer(text="Powered by thecatapi.com")
                await interaction.response.send_message(embed=embed)
                return
            except Exception as e:
                embed = discord.Embed(
                    title="Random Cat Image: Error",
                    description=f"Error fetching image: {e}",
                    color=discord.Color.red(),
                )
                await interaction.response.send_message(embed=embed)
                await self.report_error("cat", e)
                return

    # Handle DMs using threads
    class DMHandler(commands.Cog):
        def __init__(self, bot: "SplatBot"):
            self.bot = bot
            self.dm_channel_id = self.bot.shell.channel_id

        # Handle incoming DMs
        async def handle_dm_in(self, message: discord.Message):
            self.dm_channel = self.bot.get_channel(self.dm_channel_id)
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

                print(
                    f"[DMs] No thread found for {message.author.name}, creating one..."
                )

                embed = discord.Embed(
                    title=f"DM from {message.author.name}",
                    description=f"Creating thread for DM with {message.author.name}",
                    color=discord.Color.blurple(),
                )
                embed.set_footer(text="Incoming DM")
                embed.set_author(name="DMHandler")
                create_message = await self.dm_channel.send(embed=embed)

                print(f"[DMs] Creating thread for {message.author.name}")
                try:
                    user_thread = await self.dm_channel.create_thread(
                        name=f"{message.author.name}&{message.author.id}",
                        message=create_message,
                    )
                except Exception as e:
                    print(f"[DMs] Error creating thread: {e}")
                    return

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
                reply_embed.set_footer(text="Reply")
                await user_thread.send(embed=reply_embed)

            msg = f"||%%id&{message.id}%%||\n{message.content}"
            await user_thread.send(
                msg,
                allowed_mentions=discord.AllowedMentions.none(),
                files=[
                    await attachment.to_file() for attachment in message.attachments
                ],
            )

            await self.bot.shell.log(
                f"[DMs] Incoming DM from {message.author.name}, view in {user_thread.mention}",
                title="Incoming DM",
                cog="DMHandler",
                msg_type="info",
                plain_text="<@&1286884945851056191>",
            )

        # Handle outgoing to DMs
        async def handle_dm_out(self, message: discord.Message):
            dm_channel = self.bot.get_channel(self.dm_channel_id)
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

            print("[DMs] Sending message to user")
            msg = message.content
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
            elif (
                isinstance(message.channel, discord.Thread)
                and message.channel.parent_id == self.dm_channel_id
            ):
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
                await self.bot.db.update_all_auto()

            # # Check if the message contains any banned words
            # if await self.check_brainrot(message):
            #     return

        # Register a guild in the database
        async def add_guild(
            self,
            guild: discord.Guild,
            owen_mode: bool = False,
            brainrot: bool = False,
            admin_mode: bool = False,
        ):
            try:
                print(f"[Guilds] Adding guild {guild.name} to database...")
                conn = await self.bot.db.auto_connect()
                data = {
                    "guild_id": guild.id,
                    "name": guild.name,
                    "enable_owen_mode": int(owen_mode),
                    "enable_brainrot": int(brainrot),
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
            disable_brainrot: bool = False,
        ):
            try:
                print(f"[Channels] Adding channel {channel.name} to database...")
                conn = await self.bot.db.auto_connect()
                data = {
                    "channel_id": channel.id,
                    "name": channel.name,
                    "guild_id": channel.guild.id,
                    "channel_mode": channel_mode,
                    "disable_brainrot": int(disable_brainrot),
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
            disable_brainrot: bool = False,
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
            channel_data["disable_brainrot"] = int(disable_brainrot)
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
                await self.bot.db.update_all_auto()
            except Exception as e:
                await interaction.response.send_message(
                    f"Channel has be Channel successfully set to {mode} mode with banned words {'disabled' if disable_brainrot else 'enabled'}. However, the database could not be updated. Changes may take a while to reflect"
                )
                try:
                    conn.close()
                except:
                    pass
                return

            await interaction.response.send_message(
                f"Channel successfully set to {mode} mode with banned words {'disabled' if disable_brainrot else 'enabled'}"
            )
            conn.close()

    # Anti-Brainrot (Banned Words) Filter
    class AntiBrainrot(commands.Cog):
        def __init__(self, bot: "SplatBot"):
            self.bot = bot
            self.working = False

        @commands.Cog.listener()
        async def on_ready(self):
            if len(self.bot.db.data.brainrot) == 0:
                print("[Anti-Brainrot] No banned words found in database")
                print("[Anti-Brainrot] Waiting for banned words...")
                while len(self.bot.db.data.brainrot) == 0:
                    await asyncio.sleep(2)
                print("[Anti-Brainrot] Banned words found!")
            brainrot = False
            for key in self.bot.db.data.config:
                if key["name"] == "enable_brainrot":
                    brainrot = bool(key["value"])
                    break
            if not brainrot:
                print(
                    "[Anti-Brainrot] Brainrot filter disabled globally. To enable, use command `splat brainrot on` in the shell."
                )
            else:
                print("[Anti-Brainrot] Listening for banned words...")

            self.working = True

        @commands.Cog.listener()
        async def on_message(self, message: discord.Message):
            if not self.working:
                print("[Anti-Brainrot] Banned words not set up correctly, ignoring...")
                return

            if self.bot.db.data.config_get("enable_brainrot") == "0":
                # print(f"[Anti-Brainrot] (Debug) {self.bot.db.data.config_get('enable_brainrot')}")
                print("[Anti-Brainrot] Brainrot filter disabled globally, ignoring...")
                return

            # Ignore bot messages
            if message.author.bot:
                return

            # Scan message for banned words
            found = await self.is_banned(message.content.lower())
            if found == 0:
                return

            # Carry out punishment (5 minute timeout/detected word)
            timeout_length = len(found) * 5
            print(
                f"[Anti-Brainrot] Detected banned words in message, timing out for {timeout_length} minutes"
            )
            timeout = timedelta(minutes=timeout_length)
            embed = discord.Embed(
                title="Anti-Brainrot",
                description=f"Your message contained a banned brainrot phrase. You have been timed out for {timeout_length} minutes.",
                color=discord.Color.red(),
            )
            matched = "\n".join([f"{word[0]} ({word[1]}% match)" for word in found])
            embed.add_field(name="Matched Words", value=matched, inline=False)
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

            # Send report to shell
            await self.bot.shell.log(
                f"[Anti-Brainrot] Brainrot triggered {found} in message: {message.content}",
                title="Brainrot Triggered",
                cog="Anti-Brainrot",
            )

        async def is_banned(self, phrase: str) -> list | int:
            # Scan using fuzzy matching
            fuzzy_threshold = 80
            fuzzy_method = fuzz.partial_ratio
            found_banned = []
            min_length = 4

            if len(phrase) < min_length:
                return 0

            for word in self.bot.db.data.brainrot:
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

        async def is_whitelisted(self, phrase: str) -> list:
            # Scan using fuzzy matching

            found_whitelisted = []
            min_length = 4

            if len(phrase) < min_length:
                return []

            for word in self.bot.db.data.whitelist:
                if word["word"] in phrase:
                    found_whitelisted.append(word["word"])

            return found_whitelisted

        async def shell_callback(
            self, command: str, query: str, shell_command: "SplatBot.Shell.ShellCommand"
        ):
            print(f"[Anti-Brainrot] Recieved shell command: {command} | Query: {query}")
            if command == "brainrot" or command == "br":
                if (
                    query.startswith("ban")
                    or query.startswith("whitelist")
                    or query.startswith("wl")
                ):
                    if query.startswith("ban"):
                        table = "banned"
                    elif query.startswith("whitelist") or query.startswith("wl"):
                        table = "whitelist"
                    # if table not in ["banned", "whitelist"]:
                    #     await shell_command.error(
                    #         "Invalid list. Use `banned` or `whitelist`", title="Invalid List"
                    #     )
                    #     return
                    word = " ".join(query.split(" ")[1:])
                    print(f"[Anti-Brainrot] Adding banned word: {word}")
                    try:
                        conn = await self.bot.db.auto_connect()
                        await self.bot.db.add_entry(
                            "whitelist" if table == "whitelist" else "brainrot",
                            {"word": word},
                            conn=conn,
                        )
                        print(
                            f"[Anti-Brainrot] Word added to {table}, updating database..."
                        )
                        await self.bot.db.update_all_auto()
                    except Exception as e:
                        print(f"[Anti-Brainrot] Error adding word to {table}: {e}")
                        await shell_command.error(
                            f"Error adding word to {table}: {e}",
                            title="Failed to Add Word",
                        )
                        return

                    if table == "whitelist":
                        if not word in [
                            word["word"] for word in self.bot.db.data.whitelist
                        ]:
                            print(
                                f"[Anti-Brainrot] Word added but not found in database"
                            )
                            await shell_command.error(
                                f"An unknown error occured when adding the word to the database. Please try again. (Added but not found in database)",
                                title="Failed to Add Word",
                            )
                            return
                    else:
                        if not word in [
                            word["word"] for word in self.bot.db.data.brainrot
                        ]:
                            print(
                                f"[Anti-Brainrot] Word added but not found in database"
                            )
                            await shell_command.error(
                                f"An unknown error occured when adding the word to the database. Please try again. (Added but not found in database)",
                                title="Failed to Add Word",
                            )
                            return

                    print(f"[Anti-Brainrot] Word added to {table}")
                    await shell_command.success(
                        f"Word added to {table} list: {word}",
                        title=f"{'Whitelist' if table == 'whitelist' else 'Banned'} Word Added",
                    )

                elif query.startswith("reformat"):
                    print("[Anti-Brainrot] Reformatting banned words...")
                    shell_command.raw("Reformatting banned words...")
                    try:
                        # Connect to database
                        shell_command.raw("Connecting to database...")
                        conn = await self.bot.db.auto_connect()

                        # Pull data
                        await shell_command.raw(
                            "Connected to database, pulling data..."
                        )
                        await self.bot.db.update_all_conn(conn)

                        # Remove table
                        await shell_command.raw("Data pulled, removing old data...")
                        banned_words = self.bot.db.data.brainrot
                        whitelist_words = self.bot.db.data.whitelist
                        await self.bot.db.execute_query(
                            "DROP TABLE if exists brainrot", conn
                        )
                        await self.bot.db.execute_query(
                            "DROP TABLE if exists whitelist", conn
                        )
                        await conn.commit()

                        # Create new table by running check_database
                        await shell_command.raw(
                            "Old data removed, creating new table..."
                        )
                        await self.bot.db.check_database()
                        await shell_command.raw("Writing data to new table...")

                        # Add data
                        await shell_command.raw("New table created, adding data...")
                        for word in banned_words:
                            try:
                                await self.bot.db.add_entry("brainrot", word, conn)
                            except Exception as e:
                                print(
                                    f"[Anti-Brainrot] Error adding word to brainrot: {e}"
                                )
                                await shell_command.raw(
                                    f"Error adding word to brainrot: {e}",
                                )
                        for word in whitelist_words:
                            try:
                                await self.bot.db.add_entry("whitelist", word, conn)
                            except Exception as e:
                                print(
                                    f"[Anti-Brainrot] Error adding word to whitelist: {e}"
                                )
                                await shell_command.raw(
                                    f"Error adding word to whitelist: {e}",
                                )

                        # Pull data
                        await shell_command.raw("Data added, updating database...")
                        await self.bot.db.update_all_conn(conn)

                        # Success message
                        await shell_command.raw("Banned words reformatted successfully")

                        await conn.commit()
                        conn.close()

                    except Exception as e:
                        print(f"[Anti-Brainrot] Error reformating banned words: {e}")
                        await shell_command.error(
                            f"Error reformating banned words: {e}",
                            title="Failed to Reformat Words",
                        )
                        return
                    print("[Anti-Brainrot] Banned words reformatted!")
                    await shell_command.success(
                        "Banned words reformatted successfully",
                        title="Words Reformatted",
                    )

                # Check if a phrase is banned and suggest fixes
                elif query.startswith("check"):
                    query = query.split("check ")[1]

                    print(f"[Anti-Brainrot] Checking where phrase is banned: {query}")

                    found = await self.is_banned(query)

                    if found == 0:
                        is_whitelisted = await self.is_whitelisted(query)

                        if len(is_whitelisted) > 0:
                            await shell_command.info(
                                f"Phrase is whitelisted. Matched words: {is_whitelisted}",
                                title="Found Whitelisted Phrase",
                            )
                            print(
                                f"[Anti-Brainrot] Phrase is whitelisted. Matched words: {is_whitelisted}"
                            )

                            # Scan words
                            found_words = []
                            index = 0

                            print(
                                f"[Anti-Brainrot] Checking for word: {word} in {query}"
                            )

                            while index < len(query.split(" ")) + 1:
                                two_words = query.split(" ")[index : index + 2]
                                print(
                                    f"[Anti-Brainrot] Checking for words: {', '.join(two_words)} {index}-{index+2}"
                                )

                                two_words_found = await self.is_whitelisted(
                                    " ".join(two_words)
                                )

                                if len(two_words_found) > 0:
                                    found_words.append(
                                        f"Found word {word} in '{' '.join(two_words)}'"
                                    )

                                index += 1

                            if len(found_words) > 0:
                                found_words_md = "- " + "\n- ".join(found_words)
                                await shell_command.info(
                                    f"Found words: \n{found_words_md}",
                                    title="Found Words",
                                )
                            else:
                                await shell_command.info(
                                    f"Phrase is not banned or whitelisted",
                                    title="Phrase Not Found",
                                )

                            return
                        else:
                            await shell_command.info(
                                f"Phrase is not banned or whitelisted",
                                title="Phrase Not Found",
                            )
                            print(
                                f"[Anti-Brainrot] Phrase is not banned or whitelisted"
                            )
                            return

                    await shell_command.info(
                        f"Phrase is banned. Matched words: {found}",
                        title="Found Banned Phrase",
                    )

                    print(f"[Anti-Brainrot] Phrase is banned. Matched words: {found}")

                    # Scan words
                    found_words = []
                    index = 0

                    print(f"[Anti-Brainrot] Scanning by word: {query}")

                    while index < len(query.split(" ")) + 1:
                        two_words = query.split(" ")[index : index + 2]
                        print(
                            f"[Anti-Brainrot] Checking for words: {', '.join(two_words)} {index}-{index+2}"
                        )

                        two_words_found = await self.is_banned(" ".join(two_words))

                        if two_words_found != 0:
                            for word in two_words_found:
                                found_words.append(
                                    f"Found word {word[0]} ({word[1]}%) in '{' '.join(two_words)}'"
                                )

                        index += 1

                    if len(found_words) > 0:
                        found_words_md = "- " + "\n- ".join(found_words)
                        await shell_command.info(
                            f"Found words: \n{found_words_md}",
                            title="Found Words",
                        )
                    return

                elif query.startswith("remove") or query.startswith("rm"):
                    print("[Anti-Brainrot] Removing word from list")
                    query_word = " ".join(query.split(" ")[1:])
                    print(f"[Anti-Brainrot] Query word: {query_word}")
                    try:
                        if query_word in [
                            word["word"] for word in self.bot.db.data.brainrot
                        ]:
                            print("[Anti-Brainrot] Found word in banned list")
                            table = "brainrot"
                            for word in self.bot.db.data.brainrot:
                                if word["word"] == query_word:
                                    word_id = word["id"]
                                    break
                            else:
                                print(
                                    "[Anti-Brainrot] Word found in banned list, but not in database"
                                )
                                await shell_command.error(
                                    "An unexpected error occured when removing the word from the database. Please try again. (Word found in banned list, but not in database)",
                                    title="Failed to Remove Word",
                                )
                                return
                        elif query_word in [
                            word["word"] for word in self.bot.db.data.whitelist
                        ]:
                            print("[Anti-Brainrot] Found word in whitelist")
                            table = "whitelist"
                            for word in self.bot.db.data.whitelist:
                                if word["word"] == query_word:
                                    word_id = word["id"]
                                    break
                            else:
                                print(
                                    "[Anti-Brainrot] Word found in whitelist, but not in database"
                                )
                                await shell_command.error(
                                    "An unexpected error occured when removing the word from the database. Please try again. (Word found in whitelist, but not in database)",
                                    title="Failed to Remove Word",
                                )
                                return
                        else:
                            print("[Anti-Brainrot] Word not found in database")
                            await shell_command.error(
                                "Word not found in database", title="Word Not Found"
                            )
                            return
                        print(
                            f"[Anti-Brainrot] Removing word: {query_word} from {table} (ID: {word_id})"
                        )
                    except Exception as e:
                        print(f"[Anti-Brainrot] Error removing word from {table}: {e}")
                        await shell_command.error(
                            f"Error removing word from {table}: {e}",
                            title="Failed to Remove Word",
                        )
                        return

                    try:
                        conn = await self.bot.db.auto_connect()
                        await self.bot.db.delete_entry(
                            table,
                            {"id": word_id},
                            conn=conn,
                        )
                        print(
                            f"[Anti-Brainrot] Word removed from {table}, updating database..."
                        )
                        await self.bot.db.update_all_auto()

                    except Exception as e:
                        try:
                            conn.close()
                        except:
                            pass
                        print(f"[Anti-Brainrot] Error removing word from {table}: {e}")
                        await shell_command.error(
                            f"Error removing word from {table}: {e}",
                            title="Failed to Remove Word",
                        )
                        return

                    if table == "whitelist":
                        if word in [
                            word["word"] for word in self.bot.db.data.whitelist
                        ]:
                            print(
                                f"[Anti-Brainrot] Word removed but still found in database"
                            )
                            await shell_command.error(
                                f"An unknown error occured when removing the word from the database. Please try again. (Removed but still found in database)",
                                title="Failed to Remove Word",
                            )
                            return
                    else:
                        if word in [word["word"] for word in self.bot.db.data.brainrot]:
                            print(
                                f"[Anti-Brainrot] Word removed but still found in database"
                            )
                            await shell_command.error(
                                f"An unknown error occured when removing the word from the database. Please try again. (Removed but still found in database)",
                                title="Failed to Remove Word",
                            )
                            return

                    print(f"[Anti-Brainrot] Word removed from {table}")
                    await shell_command.success(
                        f"Word removed from {table} list: {word}",
                        title=f"{'Whitelist' if table == 'whitelist' else 'Banned'} Word Removed",
                    )

                elif query.startswith("on") or query.startswith("off"):
                    print(
                        f"[Anti-Brainrot] {'Enabling' if query.startswith('on') else 'Disabling'} brainrot filter"
                    )
                    try:
                        conn = await self.bot.db.auto_connect()
                        if self.bot.db.data.config_has("enable_brainrot"):
                            await self.bot.db.update_entry(
                                table="config",
                                target={"name": "enable_brainrot"},
                                data={"value": 1 if query.startswith("on") else 0},
                                conn=conn,
                            )
                        else:
                            print("[Anti-Brainrot] Config entry not found, adding...")
                            await self.bot.db.add_entry(
                                "config",
                                {
                                    "name": "enable_brainrot",
                                    "value": 1 if query.startswith("on") else 0,
                                },
                                conn=conn,
                            )
                        print(
                            "[Anti-Brainrot] Brainrot filter enabled, updating database..."
                        )
                        await self.bot.db.update_all_auto()
                    except Exception as e:
                        print(f"[Anti-Brainrot] Error enabling brainrot filter: {e}")
                        await shell_command.error(
                            f"Error enabling brainrot filter: {e}",
                            title="Failed to Enable Brainrot",
                        )
                        conn.close()
                        return
                    print(f"[Anti-Brainrot] Brainrot filter enabled")
                    await shell_command.success(
                        f"Brainrot filter {'enabled' if query.startswith('on') else 'disabled'}",
                        title="Brainrot Filter",
                    )
                    return

                # Help command
                if query == "help":
                    await shell_command.info(
                        "The brainrot filter is a system that detects and punishes users who use banned words. The filter can be enabled or disabled globally. Use the commands below to manage the filter.",
                        title="Anti-Brainrot Help",
                        fields=[
                            {
                                "name": "Commands",
                                "value": "- `ban <word>`: Ban a word\n- `whitelist <word>`: Whitelist a word\n- `reformat`: Reformat the banned words list\n- `check <phrase>`: Check if a phrase is banned\n- `remove <word>`: Remove a word from the list\n- `on`: Enable the brainrot filter\n- `off`: Disable the brainrot filter",
                                "inline": False,
                            },
                        ],
                    )
                    return

                # Defualt case: List all banned words
                banned = [word["word"] for word in self.bot.db.data.brainrot]
                whitelist = [word["word"] for word in self.bot.db.data.whitelist]

                fields = [
                    {
                        "name": "Banned Words",
                        "value": "- " + "\n- ".join(map(str, banned)),
                        "inline": False,
                    },
                    {
                        "name": "Whitelist",
                        "value": "- " + "\n- ".join(map(str, whitelist)),
                        "inline": False,
                    },
                ]

                await shell_command.info(
                    "Here are all the banned words in the database. (Use `splat brainrot help` for more commands)",
                    title="Anti-Brainrot List",
                    fields=fields,
                )
