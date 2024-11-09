import splat #Splat Bot!!   

# Environment variable handling
from dotenv import load_dotenv
import os



# Environment variables 
load_dotenv()
# Core Bot
token = os.getenv("SPLAT_TOKEN")
shell = int(os.getenv("SPLAT_SHELL"))

# Database
postgres_connection = os.getenv("POSTGRES_CONNECTION")
postgres_password = os.getenv("POSTGRES_PASSWORD")
postgres_pool = os.getenv("POSTGRES_POOL")

try:
    postgres_pool = int(postgres_pool)
except ValueError:
    print("[Runner] Warning: POSTGRES_POOL is not an integer, defaulting to 20")
    postgres_pool = 20

if postgres_pool is None:
    print("[Runner] Warning: POSTGRES_POOL not set, defaulting to 20")
    postgres_pool = 20

splat = splat.Splat(token=token, shell=shell)
splat.add_db(postgres_connection=postgres_connection, postgres_password=postgres_password, postgres_pool=postgres_pool)

print("[Runner] Starting Splat bot")
splat.run()