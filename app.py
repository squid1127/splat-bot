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

channel = int(os.getenv("BOT_SHELL"))

splat = SplatBot(token=token, shell_channel=channel, postgres_connection=os.getenv("POSTGRES_CONNECTION"), postgres_password=os.getenv("POSTGRES_PASSWORD"))

print(f'[Runner] Splat Bot has been initialized with the following settings:\nToken: {token}\nShell Channel: {channel}\nPostgres Connection: {os.getenv("POSTGRES_CONNECTION")}')

# Start the Splat bot
try:
    print("[Runner] Running Splat Bot")
    splat.run()
except KeyboardInterrupt:
    print("[Runner] Bye bye 👋")
except Exception as e:
    print(f"[Runner] Bot crashed {e}")
    DownReport(token=token, report_channel=channel).report(f"Splat Bot has crashed due to: {e}; Attempting a restart.", title="Splat Bot Crashed", msg_type="error", cog="DownReport")

# # Start the Splat bot
# while True:
#     print("[Runner] Running Splat Bot")
#     try:
#         splat.run()
#     except KeyboardInterrupt:
#         print("[Runner] Bot stopped by host")
#         DownReport(token=token, report_channel=channel).report("Splat Bot stopped by keyboard interrupt, proceeding with shutdown", title="Splat Bot Stop", msg_type="warn", cog="DownReport")
#         break
#     except ConnectionError as e:
#         print(f"[Runner] Bot stopped by connection error {e}")
#         if e.args[0] == "Database failed after multiple attempts":
#             DownReport(token=token, report_channel=channel).report(f"Splat Bot has failed to connect to the database after multiple attempts; Attempting a restart.", title="Splat Bot Database Connection Error", msg_type="error", cog="DownReport")
#         else:
#             DownReport(token=token, report_channel=channel).report(f"Splat Bot has crashed due to: {e}; Attempting a restart.", title="Splat Bot Crashed", msg_type="error", cog="DownReport")
#     except Exception as e:
#         print(f"[Runner] Bot crashed {e}")
#         DownReport(token=token, report_channel=channel).report(f"Splat Bot has crashed due to: {e}; Attempting a restart.", title="Splat Bot Crashed", msg_type="error", cog="DownReport")