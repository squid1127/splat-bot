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

# For random status
import random

# For forbidden word finder
from fuzzywuzzy import fuzz

# Downtime warning
import downreport

# For random status
import random

# For forbidden word finder
from fuzzywuzzy import fuzz

# Downtime warning
import downreport

import core

#* Main Bot
class SplatBot(core.Bot):
    def __init__(
        self,
        token: str,
        shell_channel: int,
        postgres_connection: str,
        postgres_password: str = None,
    ):
        self.name = "splat"
        
        # Initialize the bot core
        super().__init__(token, self.name, shell_channel)
        
        self.add_db(postgres_connection, postgres_password)
        asyncio.run(self.add_cogs())
            
    async def add_cogs(self):
        """Add cogs to the bot"""
        # Add cogs
        await self.add_cog(SplatDB(self, self.db))

    def run(self):
        """Start splat bot"""
        super().run()
    
    
class SplatDB(commands.Cog):
    def __init__(
        self,
        bot: core.Bot,
        db: core.DatabaseCore,
    ):
        self.bot = bot
        self.db = db
        
        self.bot.shell.add_command(command="db", cog="SplatDB", description="Perform database operations")

        
    # On ready message
    @commands.Cog.listener()
    async def on_ready(self):
        print("[SplatDB] Waiting for database connection")
        
        while not self.db.working:
            await asyncio.sleep(1)
            
        print("[SplatDB] Ready")
        
    async def cog_status(self) -> str:
        """Check the status of the cog"""
        if not self.db.working:
            return "Database not connected"
        return "Ready"
    
    async def shell_callback()
        
