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
    def __init__(self, token: str, shell: int):
        super().__init__(token=token, shell_channel=shell, name="splat")
        
        print("[Splat] Loading cogs...")
        asyncio.run(self.add_cogs())
        print("[Splat] Cogs loaded")
        
        
    def run(self):
        """Starts the bot"""
        if not self.has_db:
            print(
                "[Splat] Error: Database not configured, exiting (Hint: Use add_db() to add a database)"
            )
            return
        super().run()

    async def add_cogs(self):
        """Adds cogs to the bot"""
        await self.add_cog(DynamicWordFilter(self))

    async def on_ready(self):
        print("[Splat] Ready")


class WordFilterResult:
    """
    A class to represent the result of a word filter operation.

    Attributes:
        query (str): The query string that was checked for triggers.
        detected (bool): A flag indicating whether any triggers were detected in the query.
        triggers (list[tuple[str, str, float, int]]): A list of tuples representing the detected triggers. Each tuple contains
            - The trigger word (str)
            - The context or sentence where the trigger was found (str)
            - The confidence score of the detection (float)
            - The position of the trigger in the context (int)

    """

    def __init__(
        self, query: str, detected: bool, triggers: list[tuple[str, str, float, int]]
    ):
        self.detected = detected
        self.triggers = triggers
        self.query = query

    def __str__(self):
        if not self.detected:
            return f"No triggers detected in query:\n{self.query}"
        result = f"Triggers detected in query:\n{self.query}\nTriggers:\n"
        for trigger in self.triggers:
            result += f"Trigger: '{trigger[0]}' Found in '{trigger[1]}' at position {trigger[3]} with a confidence of {trigger[2]}\n"
        return result


class DynamicWordFilter(commands.Cog):
    def __init__(self, bot: Splat):
        self.bot = bot

        self.schema = "splat"
        self.table_words = "wordfilter"
        self.table_lists = "wordfilter_lists"
        self.format = f"""
        CREATE SCHEMA IF NOT EXISTS {self.schema};

        CREATE TABLE IF NOT EXISTS {self.schema}.{self.table_lists} (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            scan_options JSONB NOT NULL
        );
        
        CREATE TABLE IF NOT EXISTS {self.schema}.{self.table} (
            id SERIAL PRIMARY KEY,
            word TEXT NOT NULL,
            list_id INTEGER NOT NULL REFERENCES {self.schema}.{self.table_lists}(id) ON DELETE CASCADE
        );"""

        self.bot.shell.add_command(
            "wordfilter",
            cog="DynamicWordFilter",
            description="Manage the dynamic word filter",
        )

    @commands.Cog.listener()
    async def on_ready(self):
        print("[DynamicWordFilter] Loading...")
        while not self.bot.db.working:
            await asyncio.sleep(1)
        print("[DynamicWordFilter] Ready")

        # Create table
        await self.bot.db.execute(self.format)
        print("[DynamicWordFilter] Tables Updated")

    async def filter_query(self, query: str, word_lists: list[int]=None) -> WordFilterResult:
        """
        Filters a query for trigger words within specified word lists (in db).

        Args:
            query (str): The query string to filter.
            word_lists (list[int]): A list of word list IDs to filter the query against. If empty, all word lists will be used.

        Returns:
            WordFilterResult: An object representing the result of the filter operation.
        """
        
        db = self.bot.db

    async def fetch_lists(self, word_lists: list[int]=None) -> dict:
        """
        Fetches word lists from the database.

        Args:
            word_lists (list[int]): A list of word list IDs to fetch. If empty, all word lists will be fetched.

        Returns:
            dict: A dictionary containing the fetched word lists.
        """
        
        db = self.bot.db

        # Check all lists exist / fetch all lists if none specified
        schema, table, table_lists = self.get_table_schema()

        if word_lists:
            for list_id in word_lists:
                result = await table_lists.get({"id": list_id})
                if not result:
                    raise ValueError(f"Word list with ID {list_id} not found.")

        else:
            word_lists = []

            for row in await table_lists.get_data():
                word_lists.append(row["id"])


    def get_table_schema(self) -> tuple:
        """Returns the schema, table, and table_lists instances from the database."""
        self.schema_instance = self.bot.db.data.get_schema(self.schema)
        self.table_instance = self.schema_instance.get_table(self.table)
        self.table_lists_instance = self.schema_instance.get_table(self.table_lists)

        return self.schema_instance, self.table_instance, self.table_lists_instance