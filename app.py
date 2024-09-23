from splatbot import SplatBot # Splat bot
from downreport import DownReport # DownReport bot

# environment variables
from dotenv import load_dotenv
import os

print("[Runner] Running Splat Bot")

# Load the environment variables
print("[Runner] Loading environment variables")
load_dotenv()
token = os.getenv("BOT_TOKEN")
db_creds = [
    {
        "name": "Dev Database (Docker)",
        "host": "mysql",
        "user": os.getenv("MYSQL_USER"),
        "password": os.getenv("MYSQL_PASSWORD"),
        "db": os.getenv("MYSQL_DATABASE"),
    },
    {
        "name": "Dev Database (localhost)",
        "host": "localhost",
        "user": os.getenv("MYSQL_USER"),
        "password": os.getenv("MYSQL_PASSWORD"),
        "db": os.getenv("MYSQL_DATABASE"),
    },
]
channel = int(os.getenv("BOT_SHELL"))

splat = SplatBot(token=token, db_creds=db_creds, shell=channel)
# Start the Splat bot
print("[Runner] Running Splat Bot")
try:
    splat.run()
except KeyboardInterrupt:
    print("[Runner] Bot stopped by host")

print("[Runner] Running DownReport Bot")
# Start the DownReport bot (for reporting downtime)
dd_bot = DownReport(token=token, report_channel=channel)
dd_bot.down_report()