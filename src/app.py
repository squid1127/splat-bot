"""Startup script and environment variable handling for the Splat Bot."""
import splat as splat #Splat Bot!!

# Environment variable handling
from dotenv import load_dotenv
import os

import logging
logger = logging.getLogger("splat.app")

# Environment variables 
load_dotenv()
# Core Bot
token = os.getenv("SPLAT_TOKEN")
shell = int(os.getenv("SPLAT_SHELL"))

splat = splat.Splat(token=token, shell=shell)
splat.add_db(from_env=True)  # Add database from environment variables

logger.info("Starting bot...")
splat.run()