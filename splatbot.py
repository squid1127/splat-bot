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
import asyncpg  # For PostgreSQL

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

# Core
import core.squidcore as core

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
        asyncio.run(self    .add_cogs())
        
        self.set_status(random_status=core.RandomStatus.FUNNY_MESSAGES)
            
    async def add_cogs(self):
        """Add cogs to the bot"""
        # Add cogs
        pass
    