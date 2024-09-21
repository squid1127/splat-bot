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
        await self.add_cog(self.DMHandler(self))

    # Run the bot
    def run(self):
        super().run(self.token)

    # Database class for interacting with the database
    class CssDatabase:
        pass

    # Bot events (on_ready, on_message, etc.)
    class SplatEvents(commands.Cog):
        def __init__(self, bot: "SplatBot"):
            self.bot = bot

        @commands.Cog.listener()
        async def on_ready(self):
            print(f"Logged in as {self.bot.user}")
            await self.bot.change_presence(activity=discord.Game(name="Being a bot!"))

    # Bot commands
    class SplatCommands(commands.Cog):
        def __init__(self, bot: "SplatBot"):
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
            print(f"Received DM from {message.author}: {message.content}")

            # Get all threads and check if there is a thread titled with the user's ID
            threads = self.dm_channel.threads
            user_thread = None
            for thread in threads:
                if int(thread.name.split("&")[1]) == message.author.id:
                    user_thread = thread
                    break

            # If there is no thread, create one
            if user_thread is None:
                print("Creating new thread")
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

            print(f"Sending message to {user.name}: {message.content}")

            # Check if the message is a reply
            if message.reference:
                print("Message is a reply")
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
                    print("Found reference")
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
                print("No reference found, sending as normal")
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


splat = SplatBot()
splat.run()
