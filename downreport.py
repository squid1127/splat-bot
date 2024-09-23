import discord
from discord import app_commands
from discord.ext import commands, tasks
import asyncio

import dotenv
import os

class DownReport(commands.Bot):
    def __init__(self, token: str, report_channel: int):
        super().__init__(command_prefix='dd:', intents=discord.Intents.all())
        self.report_channel = report_channel
        self.token = token
        
    def down_report(self):
        print("[Down Report] Starting up warning report")
        self.run(self.token)
        print("[Down Report] Done")
        
    async def on_ready(self):
        report_channel = self.get_channel(self.report_channel)
        await self.report(report_channel)
        await self.close()

    async def report(self, channel: discord.TextChannel):
        embed = discord.Embed(title="[WARN] BOT GOING OFFLINE", description="Bot will now shut down", color=discord.Color.red())
        embed.set_author(name="Bot Down Report")
        embed.set_footer(text="Powered by Splat-Bot")
        print("[Down Report] Sending report")
        await channel.send(embed=embed)
        