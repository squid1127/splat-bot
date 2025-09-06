# Splat Bot

Splat Bot is a Discord bot built using the `discord.py` library. It provides a variety of features, including message impersonation, logging, and price tracking, among others. The bot is designed to be modular, with core functionality and additional features implemented as cogs.

## Warning‼️

This bot is currently in development by a one person who doesn't know what he's doing. Use at your own risk. The bot is not yet fully functional and may contain bugs or incomplete features.

## Features

- **Message Impersonation**: Generate embeds to mimic user messages, including replies and attachments.
- **Logging**: Tracks and logs messages and events in Discord servers.
- **Price Tracking**: Monitors and reports price changes for specified items. (Coming soon)
- **Word Filtering**: Automatically detects and filters inappropriate words.
- **Extensible Design**: Add new features easily using the cog system.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Installation

Don't. Please.

But if you really want to, create a docker container with this image: `ghcr.io/squid1127/splat-bot:latest`

### Required Environment Variables

- `SPLAT_TOKEN`: The bot token for your Discord bot.
- `SPLAT_SHELL`: A Discord channel ID where the bot will accept commands and send notifications.
- A PostgreSQL database connection using the following variables:
  - `POSTGRES_DSN`: The full DSN string for connecting to the PostgreSQL database.
  - `POSTGRES_HOST`: The hostname or IP address of the PostgreSQL server.
  - `POSTGRES_PORT`: The port number on which the PostgreSQL server is listening.
  - `POSTGRES_DB`: The name of the PostgreSQL database.
  - `POSTGRES_USER`: The username for the PostgreSQL database.
  - `POSTGRES_PASSWORD`: The password for the PostgreSQL database user.
