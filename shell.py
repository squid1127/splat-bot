import asyncio
import discord
from discord.ext import commands

class Shell:
    def __init__(self, bot: commands.Bot, channel_id: int):
        self.bot = bot

        self.channel_id = channel_id
        self.interactive_mode = None

    # Start the shell
    async def start(self):
        try:
            self.channel = self.bot.get_channel(self.channel_id)
            print("[Shell] Shell channel found!")
            print("[Shell] Starting logging...")
            await asyncio.sleep(1)
            await self.log(
                f"Bot has successfully started.",
                title="Bot Started",
                msg_type="success",
                cog="Shell",
            )
        except:
            print("[Shell] Shell channel not found!")
            return

    async def create_embed(
        self,
        message: str,
        title: str = None,
        msg_type: str = "info",
        cog: str = None,
    ):

        if msg_type == "error" or msg_type == "fatal_error":
            color = discord.Color.red()
        elif msg_type == "success":
            color = discord.Color.green()
        elif msg_type == "warning":
            color = discord.Color.orange()
        else:
            color = discord.Color.blurple()
        embed = discord.Embed(
            title=f"[{msg_type.upper()}] {title}",
            description=message,
            color=color,
        )
        embed.set_author(name=cog)
        embed.set_footer(text="Powered by Splat Bot")
        return embed

    # Send a log message
    async def log(
        self,
        message: str,
        title: str = None,
        msg_type: str = "info",
        cog: str = None,
        plain_text: str = None,
    ):
        embed = await self.create_embed(message, title, msg_type, cog)
        await self.channel.send(
            (
                plain_text
                if plain_text
                else ("@everyone" if msg_type == "fatal_error" else "")
            ),
            embed=embed,
        )

    class ShellCommand:
        def __init__(
            self,
            name: str,
            cog: str,
            shell: "Shell",
            channel: discord.TextChannel = None,
        ):
            self.name = name
            self.cog = cog
            self.shell = shell
            if channel:
                self.channel = channel
            else:
                self.channel = self.shell.channel

        async def info(
            self,
            description: str,
            title: str,
            fields: list = None,
            footer: str = None,
        ):
            embed = await self.shell.create_embed(description, title, "info", self.cog)
            if fields:
                for field in fields:
                    embed.add_field(
                        name=field["name"],
                        value=field["value"],
                        inline=field.get("inline", False),
                    )
            if footer:
                embed.set_footer(text=footer)
            await self.channel.send(embed=embed)

        async def success(
            self,
            description: str,
            title: str,
            fields: list = None,
            footer: str = None,
        ):
            embed = await self.shell.create_embed(
                description, title, "success", self.cog
            )
            if fields:
                for field in fields:
                    embed.add_field(
                        name=field["name"],
                        value=field["value"],
                        inline=field.get("inline", False),
                    )
            if footer:
                embed.set_footer(text=footer)
            await self.channel.send(embed=embed)

        async def error(
            self,
            description: str,
            title: str,
            fields: list = None,
            footer: str = None,
        ):
            embed = await self.shell.create_embed(description, title, "error", self.cog)
            if fields:
                for field in fields:
                    embed.add_field(
                        name=field["name"],
                        value=field["value"],
                        inline=field.get("inline", False),
                    )
            if footer:
                embed.set_footer(text=footer)
            await self.channel.send(embed=embed)

        async def warning(
            self,
            description: str,
            title: str,
            fields: list = None,
            footer: str = None,
        ):
            embed = await self.shell.create_embed(
                description, title, "warning", self.cog
            )
            if fields:
                for field in fields:
                    embed.add_field(
                        name=field["name"],
                        value=field["value"],
                        inline=field.get("inline", False),
                    )
            if footer:
                embed.set_footer(text=footer)

            await self.channel.send(embed=embed)

        async def raw(self, *args, **kwargs):
            await self.channel.send(*args, **kwargs)
