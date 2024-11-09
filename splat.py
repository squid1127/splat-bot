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


class Splat(core.Bot):
    def __init__(self, token:str, shell:int):
        super().__init__(token=token, shell_channel=shell, name="splat")
        
        
    def run(self):
        """Starts the bot"""
        if not self.has_db:
            print("[Splat] Error: Database not configured, exiting (Hint: Use add_db() to add a database)")
            return
        super().run()
        
    async def add_cogs(self):
        """Adds cogs to the bot"""
        await self.add_cog(DynamicWordFilter(self, self.db))
        
    async def on_ready(self):
        await super().on_ready()
        print(f"[Splat] Starting cogs")
        await self.add_cogs()
        print("[Splat] Cogs loaded")
        
        
class DynamicWordFilter(commands.Cog):
    def __init__(self, bot, db:core.DatabaseCore):
        self.bot = bot
        self.db = db
        
        self.schema = "splat"
        self.table = "wordfilter"
        self.format = f"""
        CREATE SCHEMA IF NOT EXISTS {self.schema};
        
        CREATE TABLE IF NOT EXISTS {self.schema}.{self.table} (
            id SERIAL PRIMARY KEY,
            word TEXT NOT NULL,
            type TEXT NOT NULL,
        );"""

    @commands.Cog.listener()
    async def on_ready(self):
        while not self.db.working:
            await asyncio.sleep(1)
        print("[DynamicWordFilter] Ready")
        
        # Create table
        await self.db.execute(self.format)
        print("[DynamicWordFilter] Tables Updated")
