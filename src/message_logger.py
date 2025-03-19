# Server message logger - Log messages sent, edited, and deleted in a server/channel

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

logger = logging.getLogger("splat.message_logger")

class MessageLogger(commands.Cog):
    # Constants
    DEFAULT_CONFIG = """# Message logger configuration

# Define the channels to log messages in
channels:
  - id: 1234 # Channel ID
    description: "A note to yourself" # [Optional]
        
    # Events to log. Can be filtered by channel, user, or guild as well as by action
    monitors:
      - type: channel
        id: 1234
        log_message: "<@&1234> {event}" # [Optional] Additional message to include
        events:
          - messageDelete
          - messageUpdate
          - messageSend
    """
    MONITOR_TYPES = ["channel", "user", "guild"]
    EVENT_TYPES = ["messageDelete", "messageUpdate", "messageSend"]
    EMBED_TITLES = {
        "messageDelete": "Message Deleted",
        "messageUpdate": "Message Edited",
        "_messageUpdateBefore": "Originally",
        "messageSend": None,
    }
    EMBED_COLORS = {
        "messageDelete": discord.Color.red(),
        "messageUpdate": discord.Color.yellow(),
        "_messageUpdateBefore": discord.Color.light_grey(),
        "messageSend": discord.Color.blurple(),
    }
    EMBED_EMPTY_MESSAGE = "[Empty message]"
    
    def __init__(self, bot: squidcore.Bot):
        self.bot = bot
        logger.info("Hello from message_logger!")
        
        # Register shell
        # Command
        self.bot.shell.add_command(
            "msglog", cog="MessageLogger", description="Manage message logger"
        )
        
        # Configuration
        self.files = self.bot.filebroker.configure_cog(
            "MessageLogger",
            config_file=True,
            config_default=self.DEFAULT_CONFIG,
            config_do_cache=300,
            cache=True,
        )
        
        # Initialize the files
        self.files.init()
        self.config_success, self.config_error = self.init_config()
        

        if self.config_success:
            logger.info("Configuration loaded successfully.")
        else:
            logger.error(f"Configuration failed to load: {self.config_error}")
        
    def init_config(self, force=False):
        """Initializes the configuration"""
        self.config = self.files.get_config(cache=not force)    
        
        self.instances = {}
        
        # Verify configuration
        
        # Check if the configuration is a dictionary
        if not isinstance(self.config, dict):
            return (False, "Configuration is not a dictionary. (See default config)")
        channels = self.config.get("channels")

        # Check if channels is a list
        if not isinstance(channels, list):
            return (False, "Channels should be a list. (See default config)")
        if channels is None or len(channels) == 0:
            return (False, "Channels not defined. (See default config)")
        
        # Verify each channel
        for channel in channels:
            # Check if the channel is a dictionary
            if not isinstance(channel, dict):
                return (False, "Channel is not a dictionary. (See default config)")
            channel_id = channel.get("id")
            if not isinstance(channel_id, int):
                return (False, "Channel ID is not an integer. (See default config)")
            monitors = channel.get("monitors")
            if not isinstance(monitors, list):
                return (False, "Monitors should be a list. (See default config)")
            if monitors is None or len(monitors) == 0:
                return (False, "Monitors not defined. (See default config)")
            monitor_ids = []
            for monitor in monitors:
                if not isinstance(monitor, dict):
                    return (False, "Monitor is not a dictionary. (See default config)")
                monitor_type = monitor.get("type")
                if not isinstance(monitor_type, str):
                    return (False, "Monitor type is not a string. (See default config)")
                if monitor_type not in self.MONITOR_TYPES:
                    return (False, f"Monitor type is not valid. Choose from: {self.MONITOR_TYPES}")
                monitor_id = monitor.get("id")
                if not isinstance(monitor_id, int):
                    return (False, "Monitor ID is not an integer. It should be a Discord channel ID. (See default config)")
                if monitor_id in monitor_ids:
                    return (False, "Monitor ID is already defined. (See default config)")
                monitor_ids.append(monitor_id)
                events = monitor.get("events")
                if not isinstance(events, list):
                    return (False, "Events should be a list. (See default config)")
                if events is None or len(events) == 0:
                    return (False, "Events not defined. (See default config)")
                for event in events:
                    if not isinstance(event, str):
                        return (False, "Event is not a string. (See default config)")
                    if event not in self.EVENT_TYPES:
                        return (False, f"Event type is not valid. Choose from: {self.EVENT_TYPES}")
                                    
        # Load the configuration into a dictionary of instances
        self.instances = {}
        self.monitors = []
        for channel in channels:
            channel_id = channel.get("id")
            self.instances[channel_id] = channel
        
            for monitor in channel.get("monitors"):
                self.monitors.append((monitor.get("type"), monitor.get("id"), channel_id, monitor))

        logger.debug(f"Loaded instances: {self.instances}")
        
        # Config loaded
        return (True, None) # Success
    
    @commands.Cog.listener()
    async def on_ready(self):
        await asyncio.sleep(1)
        if not self.config_success:
            await self.bot.shell.log(
                f"Message Logger failed to load: {self.config_error}",
                title="Message Logger",
                msg_type="error",
                cog="MessageLogger",
            )
    
    async def shell_callback(self, command: squidcore.ShellCommand):

        logger.info(f"Received command: {command}")
        if command.name == "msglog":
            if command.query.startswith("reload"):
                edit = await command.log(
                    "Reloading configuration...",
                    title="Message Logger",
                    msg_type="info",
                )
                status, error = self.init_config(force=True)
                if status:
                    await command.log(
                        "Configuration reloaded successfully.",
                        title="Message Logger",
                        msg_type="success",
                        edit=edit,
                    )
                else:
                    await command.log(
                        f"Configuration failed to reload: {error}",
                        title="Message Logger",
                        msg_type="error",
                        edit=edit,
                    )
            else:
                # Display help
                await command.log(
                    "Listen for message events in a channel and log them to another channel. Use the config file at `/store/config/MessageLogger.yaml` to configure the logger.\n\n**Commands**:\n- `reload`: Reload the configuration",
                    title="Message Logger",
                    msg_type="info",
                )
        pass
    
    # Event listeners
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Pass the message to the handler
        await self.handle_message(message, "messageSend")
        
    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        # Pass the message to the handler
        await self.handle_message(message, "messageDelete")
    
    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        # Pass the message to the handler
        await self.handle_message(after, "messageUpdate", beforemessage=before)
        
    async def embed_message(self, message: discord.Message, event: str):
        """Creates an embed for a message event"""
        # Extract information
        title = self.EMBED_TITLES.get(event, "Message Event")
        content = message.content if message.content else self.EMBED_EMPTY_MESSAGE
        timestamp = message.created_at
        embeds = message.embeds if message.embeds else []
        
        # Create the embed
        embed = discord.Embed(
            title=title,
            description=content,
            color=self.EMBED_COLORS.get(event, discord.Color.default()),
            timestamp=timestamp,
        )
        embed.set_author(
            name=message.author.display_name,
            icon_url=message.author.avatar.url,
            url=message.jump_url,
        )
        embed.set_footer(
            text=f"ID: {message.id}",
        )
        
        # Inject embed to embeds
        embeds.insert(0, embed)
        
        return embeds
    
    async def handle_message(self, message: discord.Message, event: str, beforemessage: discord.Message = None):
        """Handles a message event"""
        # Search for monitors
        monitors = []
        for monitor_type, monitor_id, channel_id, monitor in self.monitors:
            if monitor_type == "channel" and monitor_id == message.channel.id:
                pass
            elif monitor_type == "user" and monitor_id == message.author.id:
                pass
            elif monitor_type == "guild" and monitor_id == message.guild.id:
                pass
            else:
                continue
            if event not in monitor.get("events"):
                continue
            # Monitor found
            monitors.append((channel_id, monitor))
            logger.info(f"Logging message event {event} in channel {channel_id}")
            
        # Create a message embed
        embeds = await self.embed_message(message, event)
        if beforemessage:
            embeds += await self.embed_message(beforemessage, "_messageUpdateBefore")
            
        # Send the embeds
        for channel_id, monitor in monitors:
            channel = self.bot.get_channel(channel_id)
            if channel is None:
                logger.warning(f"Channel {channel_id} not found.")
                continue
            
            
            log_message = monitor.get("log_message")
            if log_message:
                # Templates
                log_message = log_message.replace("{event}", self.EMBED_TITLES.get(event, "Message Event"))
                log_message = log_message.replace("{channel}", message.channel.mention)
                log_message = log_message.replace("{user}", message.author.mention)
                log_message = log_message.replace("{guild}", message.guild.name)
                
                await channel.send(content=log_message, embeds=embeds)
            else:
                await channel.send(embeds=embeds)