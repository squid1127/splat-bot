# PriceTracker - Track prices of products on Amazon & other e-commerce websites and notify Discord users when the price drops and when items are back in stock. Uses beautifulsoup4 and requests to scrape the web.


# Discord
import asyncio
import discord
from discord.ui import Select, View, Button
from discord import app_commands
from discord.ext import commands, tasks
from typing import Optional, Literal  # For command params
from datetime import timedelta, datetime  # For timeouts & timestamps
from enum import Enum  # For enums (select menus)
import core as squidcore # Squidcore is the main module for the bot
import timedelta

import json

import logging

logger = logging.getLogger("splat.price_tracker")

class PriceTracker(commands.Cog):
    def __init__(self, bot: squidcore.Bot):
        self.bot = bot
        
        # Commands
        self.bot.shell.add_command(
            "pt",
            cog="PriceTracker",
            description="Manage the Price Tracker",
        )
        
    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("Waiting for database to be ready")
        while not self.bot.db.working:
            await asyncio.sleep(1)
        logger.info("Initializing Price Tracker")

        await self.init()
        
    # Database constants
    SCHEMA = "splat"
    TABLE = "price_tracker"
    
    INIT_SQL = f"""
    CREATE SCHEMA IF NOT EXISTS {SCHEMA};
    
    CREATE TABLE IF NOT EXISTS {SCHEMA}.{TABLE} (
        id SERIAL PRIMARY KEY,
        type VARCHAR(255) NOT NULL,
        url TEXT NOT NULL,
        price NUMERIC(10, 2),
        stock TEXT,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
        
    async def init(self):
        logger.info("Initializing database")
        await self.bot.db.execute(self.INIT_SQL)