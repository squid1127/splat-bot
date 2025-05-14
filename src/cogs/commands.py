# Misc. Commands for splat

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

# Async / HTTP
import json
import aiohttp

# Logging
import logging

logger = logging.getLogger("splat.commands")


class SplatCommands(commands.Cog):
    def __init__(self, bot: squidcore.Bot):
        self.bot = bot

    # Ping command
    @app_commands.command(
        name="ping-splat",
        description="Check if Splat is alive",
    )
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message("Pong!")

    # Dev Excuse command
    @app_commands.command(
        name="dev-excuse",
        description="Get a random developer excuse",
    )
    async def dev_excuse(self, interaction: discord.Interaction):
        # Defer the response
        await interaction.response.defer()

        # Fetch the excuse
        api = "https://api.devexcus.es"
        key = "text"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api) as response:
                    data = await response.json()
                    excuse = data[key]
                    await interaction.followup.send(excuse)

        except Exception as e:
            logger.error(f"Error fetching dev excuse: {e}")
            await interaction.followup.send(
                embed=discord.Embed(
                    description="Error fetching dev excuse", color=discord.Color.red()
                )
            )

            # Report the error
            await self.bot.shell.log(
                f"Error fetching dev excuse: {e}",
                title="Commands | Dev Excuse",
                msg_type="error",
                cog="SplatCommands",
            )

    # Mention everyone command
    @app_commands.command(
        name="mention-everyone",
        description="Mention everyone in the server",
    )
    async def mention_everyone(self, interaction: discord.Interaction):
        # Defer the response
        await interaction.response.defer(ephemeral=True)

        logger.info(
            f"Got mention everyone command from {interaction.user} in {interaction.guild}"
        )

        # Check if user has permissions to mention everyone
        if not interaction.user.guild_permissions.mention_everyone:
            await interaction.followup.send(
                embed=discord.Embed(
                    description="You do not have permission to mention everyone",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return

        # List of members to mention
        members = interaction.guild.members
        mentions = [member.mention for member in members]

        logger.info(f"Mentioning {len(mentions)} members: {mentions}")

        # Mention everyone
        messages = []
        current = ""
        for mention in mentions:
            if current == "":
                current = mention
            elif len(current) + len(mention) < 2000:
                current += " " + mention
            else:
                messages.append(current)
                current = mention

        if current:
            messages.append(current)

        logger.info(f"Sending {len(messages)} messages")

        await interaction.followup.send("Mentioning everyone...")
        for message in messages:
            await interaction.channel.send(message)

    # Cat Image command
    @app_commands.command(
        name="cat",
        description="Get a picture of a cat! :3",
    )
    async def cat_image(self, interaction: discord.Interaction):
        # Defer the response
        await interaction.response.defer()

        # Fetch the cat image
        api = "https://api.thecatapi.com/v1/images/search?limit=1"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api) as response:
                    data = await response.json()
                    cat_image_url = data[0]["url"]
                    await interaction.followup.send(
                        embed=discord.Embed(
                            title="Here's a cat :3", color=0xE5B261
                        ).set_image(url=cat_image_url)
                    )

        except Exception as e:
            logger.error(f"Error fetching cat image: {e}")
            await interaction.followup.send(
                embed=discord.Embed(
                    description="Error fetching cat image", color=discord.Color.red()
                )
            )

            # Report the error
            await self.bot.shell.log(
                f"Error fetching cat image: {e}",
                title="Commands | Cat Image",
                msg_type="error",
                cog="SplatCommands",
            )

    # Dog Image command
    @app_commands.command(
        name="dog",
        description="Get a picture of a dog!",
    )
    async def dog_image(self, interaction: discord.Interaction):
        # Defer the response
        await interaction.response.defer()

        # Fetch the dog image
        api = "https://dog.ceo/api/breeds/image/random"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api) as response:
                    data = await response.json()
                    dog_image_url = data["message"]
                    await interaction.followup.send(
                        embed=discord.Embed(title="Woof!", color=0xE5B261).set_image(
                            url=dog_image_url
                        )
                    )

        except Exception as e:
            logger.error(f"Error fetching dog image: {e}")
            await interaction.followup.send(
                embed=discord.Embed(
                    description="Error fetching dog image", color=discord.Color.red()
                )
            )

            # Report the error
            await self.bot.shell.log(
                f"Error fetching dog image: {e}",
                title="Commands | Dog Image",
                msg_type="error",
                cog="SplatCommands",
            )

    # Help command
    @app_commands.command(
        name="help-splat",
        description="Get help with Splat",
    )
    async def help(self, interaction: discord.Interaction):

        description = "I'm Splat, a bot created by CubbScratchStudios! I am a general-purpose bot with a variety of commands as well as advanced moderation features."

        embed = discord.Embed(
            title="Splat Help", color=0xF0C195, description=description
        )
        
        embed.add_field(
            name="Commands",
            value="""
- `/ping-splat`: Check if Splat is alive
- `/dev-excuse`: Get a random developer excuse
- `/mention-everyone`: Mention everyone in the server (requires permissions)
- `/cat`: Get a picture of a cat
- `/dog`: Get a picture of a dog
- `/help-splat`: Get help with Splat (this command)
                """,
            inline=False,
        )
        
        embed.add_field(
            name="Community",
            value="Check out the [CubbScratchStudios Bot Community Server](https://je.fr.to/discord-bot-community) for more information about Splat and other bots, as well as support and discussion. (We're still setting things up, so please be patient!)",
            inline=False,
        )

        embed.set_footer(
            text="Brought to you by CubbScratchStudios",
            icon_url="https://je.fr.to/static/css_logo.PNG",
        )
        
        await interaction.response.send_message(embed=embed)

    async def cog_status(self):
        return "Just doing stuff idk"