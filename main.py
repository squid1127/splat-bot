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
    def __init__(self):
        # Initialize the bot
        super().__init__(command_prefix="splat ", intents=discord.Intents.all())

        # Add the cogs
        asyncio.run(self.addCogs())

        load_dotenv()
        self.token = os.getenv("BOT_TOKEN")
        self.db_host = os.getenv("DB_HOST")
        self.db_user = os.getenv("DB_USER")
        self.db_pass = os.getenv("DB_PASS")

    # Add the cogs (commands and events)
    async def addCogs(self):
        await self.add_cog(self.SplatEvents(self))
        await self.add_cog(self.SplatCommands(self))

    # Run the bot
    def run(self):
        super().run(self.token)
        
    # Database class for interacting with the database
    class CssDatabase:
        pass
        
    # Bot events (on_ready, on_message, etc.)
    class SplatEvents(commands.Cog):
        def __init__(self, bot: 'SplatBot'):
            self.bot = bot

        @commands.Cog.listener()
        async def on_ready(self):
            print(f"Logged in as {self.bot.user}")
            await self.bot.change_presence(activity=discord.Game(name="Being a bot!"))

    # Bot commands
    class SplatCommands(commands.Cog):
        def __init__(self, bot: 'SplatBot'):
            self.bot = bot

        # Sync commands on bot ready
        @commands.Cog.listener()
        async def on_ready(self):
            print("Syncing application commands...")
            self.commands_list = await self.bot.tree.sync()
            print(f"Synced {len(self.commands_list)} commands")

        @app_commands.command(name="ping", description="Check if bot is online")
        async def ping(self, interaction: discord.Interaction):
            await interaction.response.send_message("Pong!")



splat = SplatBot()
splat.run()
