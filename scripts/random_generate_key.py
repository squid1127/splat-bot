from cryptography.fernet import Fernet
import os
from dotenv import load_dotenv

# Open the .env file
load_dotenv()
# Check if the key already exists
print("Checking if key exists")
print("~"*15)
try:
    key = os.getenv("MYSQL_KEY")
    if key == None:
        raise Exception("Key not found")
except:
    print("Key not found")
    has_key = False
else:
    print(f"Key found: {key}")
    has_key = True

if has_key:
    print("1. Generate new key")
    print("2. Use a different key")
else:
    print("1. Generate key")
    print("2. Enter existing key")
print("3. Exit")

choice = input("Enter your choice: ")
if choice == "1":
    print("Generating new key")
    key = Fernet.generate_key()
    key = key.decode("utf-8")
    print(f"Key generated: {key}")
    if has_key:
        print("Are you sure you want to overwrite the existing key?")
        choice = input("Enter your choice (y/n): ")
        if choice.lower() == "y":
            print("Removing existing key")
            with open(".env", "r") as f:
                lines = f.readlines()
            with open(".env", "w") as f:
                for line in lines:
                    if "MYSQL_KEY" not in line:
                        f.write(line)
                        
    print("Writing key to .env")
    with open(".env", "a") as f:
        f.write(f"\nMYSQL_KEY={key}")

if choice == "2":
    print("Enter the key")
    key = input("Key: ")
    if has_key:
        print("Are you sure you want to overwrite the existing key?")
        choice = input("Enter your choice (y/n): ")
        if choice.lower() == "y":
            print("Removing existing key")
            with open(".env", "r") as f:
                lines = f.readlines()
            with open(".env", "w") as f:
                for line in lines:
                    if "MYSQL_KEY" not in line:
                        f.write(line)
        print("Writing key to .env")
        with open(".env", "a") as f:
            f.write(f"\nMYSQL_KEY={key}")

if choice == "3":
    print("Exiting")
    exit()