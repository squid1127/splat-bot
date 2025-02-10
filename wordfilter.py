# Filter words and phrases from messages using a dynamic word filter.

from fuzzywuzzy import fuzz
import re

# Discord
import asyncio
import discord
from discord.ui import Select, View, Button
from discord import app_commands
from discord.ext import commands, tasks
from typing import Optional, Literal  # For command params
from datetime import timedelta, datetime  # For timeouts & timestamps
from enum import Enum  # For enums (select menus)
import core as squidcore
import timedelta

import json

import logging

logger = logging.getLogger("splat.wordfilter")

# Core Logic
FUZZY_METHODS = {
    "fuzz.ratio": fuzz.ratio,
    "fuzz.partial_ratio": fuzz.partial_ratio,
    "fuzz.token_sort_ratio": fuzz.token_sort_ratio,
    "fuzz.token_set_ratio": fuzz.token_set_ratio,
    "fuzz.partial_token_sort_ratio": fuzz.partial_token_sort_ratio,
    "fuzz.partial_token_set_ratio": fuzz.partial_token_set_ratio,
}


def process_query(query: str, filter: str, options: dict = {}) -> "WordFilterResult":

    # Compare the query and filter using the specified method
    score = 0
    logger.debug(f"Scan options: {options}")

    if len(query) < options.get("min_length", 0):
        return WordFilterResult(query, False, 0)

    if options["type"] == "fuzzy":
        # Get the fuzzy method
        if type(options["fuzzy_method"]) == str:
            fuzzy_methods = FUZZY_METHODS
            if "fuzzy_method" in options:
                options["fuzzy_method"] = fuzzy_methods.get(
                    options["fuzzy_method"], fuzz.ratio
                )
            else:
                logger.warning("Fuzzy method not specified, defaulting to fuzz.ratio")
                options["fuzzy_method"] = fuzz.ratio

        logger.debug("Fuzzy method: " + options["fuzzy_method"].__name__)

        score = options["fuzzy_method"](query, filter)
        if score >= options["threshold"]:
            return WordFilterResult(query, True, score)

    elif options["type"] == "exact":
        if query == filter:
            return WordFilterResult(query, True, 100)

    elif options["type"] == "contains":
        if filter in query:
            return WordFilterResult(query, True, 100)
    elif options["type"] == "regex":
        if re.search(filter, query):
            return WordFilterResult(query, True, 100)

    return WordFilterResult(query, False, score)


class WordFilterCore:
    def __init__(self, scan_options: dict = {}):
        self.scan_options = scan_options
        self.lists = []
        
        self.process_count = 0

    def add_list(
        self, name: str, description: str, scan_options: dict = {}
    ) -> "WordFilterList":
        new_list = WordFilterList(name, description, scan_options, self)
        self.lists.append(new_list)
        return new_list

    def evaluate(self, text: str) -> "WordFilterResult":
        triggers = []
        for list in self.lists:
            list_result = list.evaluate(text)
            triggers.extend(list_result)
        self.process_count += 1
        return triggers
    
    def generate_tree(self) -> str:
        """Create a tree representation of the word filter"""
        if len(self.lists) == 0:
            return "[ No Lists ]"
        
        tree = ""
        for list in self.lists:
            tree += f"*{list.name}:*\n"
            
            if len(list.words) == 0:
                tree += " [ No Entries ]\n\n"
                continue
            
            for word in list.words:
                tree += f"- {word.word}\n"
                for whitelist in word.whitelisted_words:
                    tree += f"  - {whitelist.word}\n"
            tree += "\n"
        return tree


class WordFilterList:
    def __init__(
        self,
        name: str,
        description: str,
        scan_options: dict = {},
        core: WordFilterCore = None,
    ):
        self.name = name
        self.description = description
        self.scan_options = scan_options if scan_options != {} else core.scan_options
        self.core = core
        self.words = []

    def add_word(self, query: str, scan_options: dict = {}) -> "WordFilterWord":
        new_word = WordFilterWord(query, self, scan_options)
        self.words.append(new_word)
        return new_word

    def evaluate(self, text: str) -> "WordFilterResult":
        triggers = []
        for word in self.words:
            word_result = word.evaluate(text)
            if word_result.triggered:
                triggers.append(word_result)
        return triggers


class WordFilterWord:
    def __init__(self, word: str, list: WordFilterList, scan_options: dict = {}):
        self.word = word
        self.list = list

        self.core = list.core

        self.whitelisted_words = []

        if scan_options == {} or scan_options is None or scan_options == "":
            self.scan_options = list.scan_options
        else:
            self.scan_options = scan_options

    def evaluate(self, text: str) -> "WordFilterResult":
        score = 0
        triggered = False

        result = process_query(text, self.word, self.scan_options)
        result.word = self.word
        result.list = self.list
        result.scan_options = self.scan_options
        result.core = self.core

        result = self._check_triggered_word(text, result)
        if result.triggered:
            triggered_words = self._scan_triggered_words(text)
            whitelisted_words = self._check_whitelisted_words(triggered_words)
            if whitelisted_words:
                logger.debug(f"Whitelisted words: {whitelisted_words}")
                logger.debug(f"Nullifying trigger")
                result.triggered = False
        return result

    def _check_triggered_word(
        self, text: str, result: "WordFilterResult"
    ) -> "WordFilterResult":
        if result.triggered:
            logger.debug(f"Triggered word: {self.word} in text: {text}")
        return result

    def _scan_triggered_words(self, text: str) -> list:
        words = text.split()
        triggered_words = []
        for index, word in enumerate(words):
            if word == self.word:
                continue
            word_result = process_query(word, self.word, self.scan_options)
            if word_result.triggered:
                logger.debug(f"Triggered word: {word} at index {index} in text: {text}")
                triggered_words.append((word, index))
        if not triggered_words:
            triggered_words = self._scan_biwords(words)
        return triggered_words

    def _scan_biwords(self, words: list) -> list:
        triggered_words = []
        for index, word in enumerate(words):
            if index == 0:
                continue
            biword = words[index - 1] + " " + word
            word_result = process_query(biword, self.word, self.scan_options)
            if word_result.triggered:
                logger.debug(f"Triggered biword: {biword} at index {index}")
                triggered_words.append((biword, index))
        return triggered_words

    def _check_whitelisted_words(self, triggered_words: list) -> list:
        whitelisted_words = []
        for whitelisted_word in self.whitelisted_words:
            for word, index in triggered_words:
                word_result = process_query(
                    word, whitelisted_word.word, whitelisted_word.scan_options
                )
                if word_result.triggered:
                    logger.debug(f"Whitelisted word: {word} at index {index}")
                    whitelisted_words.append((word, index))
        return whitelisted_words

    def add_whitelisted_word(self, word: str, scan_options: dict = {}):
        # By default, use containing method
        if scan_options == {} or scan_options is None or scan_options == "":
            scan_options = {"type": "contains"}
        
        new_word = WordFilterWord(word, self.list, scan_options)
        self.whitelisted_words.append(new_word)
        return new_word


class WordFilterResult:
    def __init__(self, query: str, triggered: bool, score: int):
        self.query = query
        self.triggered = triggered
        self.score = score

        self.word = None
        self.list = None
        self.scan_options = None
        self.core = None

    def __str__(self):
        if not self.triggered:
            return f"No triggers detected in query:\n{self.query}"
        return f"Triggers detected in query:\n{self.query}\nScore: {self.score}"

    def __repr__(self):
        if not self.triggered:
            return f"WordFilterResult({self.word}, triggered=False)"

        return f"WordFilterResult({self.word}, triggered=True, score={self.score})"


# Discord
class WordFilterCog(commands.Cog):
    def __init__(self, bot: squidcore.Bot):
        self.bot = bot
        self.core = WordFilterCore()

        # Database
        self.schema = "splat"
        self.table_words = "wordfilter"
        self.table_lists = "wordfilter_lists"
        self.table_whitelist = "wordfilter_whitelist"
        self.format = f"""
        CREATE SCHEMA IF NOT EXISTS {self.schema};

        CREATE TABLE IF NOT EXISTS {self.schema}.{self.table_lists} (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            scan_options JSONB NOT NULL
        );
        
        CREATE TABLE IF NOT EXISTS {self.schema}.{self.table_words} (
            id SERIAL PRIMARY KEY,
            word TEXT NOT NULL,
            list_id INTEGER NOT NULL REFERENCES {self.schema}.{self.table_lists}(id) ON DELETE CASCADE,
            scan_options JSONB
        );
        
        CREATE TABLE IF NOT EXISTS {self.schema}.{self.table_whitelist} (
            id SERIAL PRIMARY KEY,
            word TEXT NOT NULL,
            word_id INTEGER NOT NULL REFERENCES {self.schema}.{self.table_words}(id) ON DELETE CASCADE,
            scan_options JSONB
        );
        """

        # Commands
        self.bot.shell.add_command(
            "wordfilter",
            cog="WordFilterCog",
            description="Manage the dynamic word filter",
        )
        self.bot.shell.add_command(
            "wf",
            cog="WordFilterCog",
            description="Manage the dynamic word filter (alias)",
        )

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("Loading...")
        while not self.bot.db.working:
            await asyncio.sleep(1)
        logger.info("Ready")

        await self.init()

    async def init(self):
        # Create the database schema
        await self.bot.db.execute(self.format)

        # Fetch data from the database
        self.schema_object = self.bot.db.data.get_schema(self.schema)
        self.table_lists_object = self.schema_object.get_table(self.table_lists)
        self.table_words_object = self.schema_object.get_table(self.table_words)
        self.table_whitelist_object = self.schema_object.get_table(self.table_whitelist)

        # Load the lists
        lists = await self.table_lists_object.fetch()
        words = await self.table_words_object.fetch()
        whitelisted_words = await self.table_whitelist_object.fetch()

        # Drop the existing lists
        self.core.lists = []

        # Process the lists
        await self.process_lists(lists, words, whitelisted_words)

        # Debug
        logger.info("Loaded lists")

        logger.info(f"Tree:\n{self.core.generate_tree()}")

    async def process_lists(
        self, lists: list[dict], words: list[dict], whitelisted_words: list[dict]
    ):
        """
        Process the lists, words, and whitelisted words for the word filter, registering them with the core.
        """
        # Create the lists
        list_objects = {}  # Cache the list objects

        for list_item in lists:
            # Convert the scan options to a dictionary
            logger.debug(
                f"Scan options are of type {type(list_item['scan_options'])} -> {list_item['scan_options']}"
            )  # It's a string

            options = json.loads(list_item["scan_options"])
            if isinstance(options, str):
                try:
                    options = json.loads(options)
                except:
                    pass

            if not isinstance(options, dict):
                options = {}

            logger.debug(f"Scan options are now of type {type(options)} -> {options}")

            new_list = self.core.add_list(
                list_item["name"], list_item["description"], options
            )

            list_objects[list_item["id"]] = new_list

        # Create the words
        word_objects = {}
        for word in words:
            try:
                options = json.loads(word["scan_options"])
                if isinstance(options, str):
                    try:
                        options = json.loads(options)
                    except json.JSONDecodeError:
                        options = {}

                if not isinstance(options, dict):
                    options = {}
            except json.JSONDecodeError:
                options = {}

            word_list: WordFilterList = list_objects[word["list_id"]]
            word_list.add_word(word["word"], options)

            word_objects[word["id"]] = word_list.words[-1]

        # Add the whitelisted words
        for whitelist_word in whitelisted_words:
            try:
                options = json.loads(whitelist_word["scan_options"])
                if isinstance(options, str):
                    try:
                        options = json.loads(options)
                    except json.JSONDecodeError:
                        options = {}

                if not isinstance(options, dict):
                    options = {}
            except json.JSONDecodeError:
                options = {}

            word: WordFilterWord = word_objects[whitelist_word["word_id"]]
            word.add_whitelisted_word(whitelist_word["word"], options)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        await self.handle_message(message)

    class TimeoutView(View):
        def __init__(self, timeout: int, user: discord.Member):
            super().__init__(timeout=timeout)
            self.user = user

        @discord.ui.button(label="Unmute", style=discord.ButtonStyle.danger)
        async def unmute(
            self, interaction: discord.Interaction, button: discord.Button
        ):
            if not interaction.user.guild_permissions.moderate_members:
                await interaction.response.send_message(
                    "You do not have permission to unmute members.", ephemeral=True
                )
                return

            try:
                await self.user.edit(timed_out_until=None)
                await interaction.response.send_message(
                    "User has been unmuted.", ephemeral=True
                )
            except discord.Forbidden:
                await interaction.response.send_message(
                    "Failed to unmute user", ephemeral=True
                )

            embed = discord.Embed(
                title="Word Filter Triggered",
                description=f"User {self.user.mention} has been unmuted.",
                color=discord.Color.green(),
            )
            await interaction.message.edit(embed=embed, view=None)

    async def handle_message(self, message: discord.Message):
        result = self.core.evaluate(message.content.lower())
        if result:
            logger.info(f"Detected trigger in message from {message.author}: {result}")

            # Calculate timeout -> 5 minutes per trigger
            timeout = timedelta.Timedelta(minutes=len(result) * 5)

            try:
                await message.author.timeout(timeout, reason="Word filter triggered")
                success = True
            except discord.Forbidden:
                logger.error("Failed to mute user")
                success = False

            embed = discord.Embed(
                title="Word Filter Triggered",
                description=f"I've detected banned words or phrases in your message. {'You have been muted for ' + str(timeout.total_seconds() // 60) +  ' minutes.' if success else 'You are unable to be muted at this time.'}",
                color=discord.Color.red(),
            )
            embed.add_field(
                name="Triggered Words",
                value="\n".join(
                    [
                        f"1. {r.word} (**{r.score}**% match) ({r.list.name})"
                        for r in result
                    ]
                ),
            )

            view = self.TimeoutView(
                timeout=timeout.total_seconds(), user=message.author
            )
            if success:
                await message.reply(embed=embed, view=view)
            else:
                await message.reply(embed=embed)

    async def shell_callback(self, command: squidcore.ShellCommand):
        if command.name == "wordfilter" or command.name == "wf":
            if command.query.startswith("reload"):
                await self.init()
                await command.log(
                    "Successfully reloaded the word filter",
                    title="Word Filter",
                    msg_type="success",
                )
                return

            # List the lists
            if command.query == "lists":
                lists = "\n".join(
                    [f"{list.name} ({list.description})" for list in self.core.lists]
                )
                await command.log(
                    f"### Lists:\n{lists}", title="Word Filter", msg_type="info"
                )
                return
            
            # Generate a tree representation of the word filter
            if command.query == "tree":
                tree = self.core.generate_tree()
                await command.log(
                    tree, title="Word Filter: Tree", msg_type="info"
                )
                return
            
            # Default to help / tree
            fields = [
                {
                    "name": "Commands",
                    "value": """
- `lists` - List the word filter lists
- `tree` - Generate a tree representation of the word filter
- `reload` - Reload the word filter
                    """
                },
                {
                    "name": "Tree",
                    "value": self.core.generate_tree()
                }
            ]
            
            # Status: If working there should be at least one list with at least one word. Process count must be >0
            working = False
            if isinstance(self.core.lists, list) and len(self.core.lists) > 0:
                if isinstance(self.core.lists[0].words, list) and len(self.core.lists[0].words) > 0:
                    if self.core.process_count > 0:
                        working = True

            await command.log(
                "Word filter has passed status checks" if working else "Word filter has **failed** status checks", title="Word Filter", msg_type="info", fields=fields
            )
            return