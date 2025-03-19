# Core
import core

# Discord
import asyncio
import discord
from discord.ui import Select, View, Button
from discord import app_commands
from discord.ext import commands, tasks
from typing import Optional, Literal  # For command params
from datetime import timedelta, datetime  # For timeouts & timestamps
from enum import Enum  # For enums (select menus)

import logging
logger = logging.getLogger("splat")

# Submodules
from wordfilter import WordFilterCore, WordFilterCog
from commands import SplatCommands
from message_logger import MessageLogger

class Splat(core.Bot):
    def __init__(self, token: str, shell: int):
        super().__init__(token=token, shell_channel=shell, name="splat")
        
        logger.info("Loading cogs...")
        asyncio.run(self.add_cogs())
        logger.info("Cogs loaded")
        
        
    def run(self):
        """Starts the bot"""
        if not self.has_db:
            logger.error(
                "Error: Database not configured, exiting (Hint: Use add_db() to add a database)"
            )
            return
        super().run()

    async def add_cogs(self):
        """Adds cogs to the bot"""
        await self.add_cog(WordFilterCog(self))
        await self.add_cog(SplatCommands(self))
        await self.add_cog(MessageLogger(self))