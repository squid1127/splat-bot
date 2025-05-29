# PriceTracker - Track prices of products on Amazon & other e-commerce websites and notify Discord users when the price drops and when items are back in stock. Uses beautifulsoup4 and requests to scrape the web.


# Discord
import asyncio
import discord
from discord.ui import Select, View, Button
from discord import app_commands
from discord.ext import commands, tasks
from typing import Optional, Literal  # For command params
from datetime import timedelta, datetime  # For timeouts & timestamps
from enum import Enum  # For enums (select menus)

# Bot core
import core as squidcore

# Parse
import json
from bs4 import BeautifulSoup

# HTTP
import aiohttp

# Regex
import re

# Logger
import logging

logger = logging.getLogger("splat.price_tracker")


# Sites / Providers
class Provider:
    """
    Base class for all providers. Each provider should inherit from this class and implement the required methods.
    Attributes:
        friendly_name (str): The friendly name of the provider (e.g. Amazon, eBay, Micro Center)
        internal_name (str): The internal name of the provider (e.g. amazon, ebay, microcenter)
        website_homepage (str): The homepage URL of the provider (e.g. https://www.amazon.com/)
        url_regex (str):  regex pattern to match product URLs to add products based on URL (e.g.
        icon_url (str): The URL of the provider's icon

    """

    def __init__(
        self,
        friendly_name: str,
        internal_name: str,
        website_homepage: str = None,
        url_regex: str = None,
        icon_url: str = None,
    ):
        self.friendly_name = friendly_name
        self.internal_name = internal_name
        self.website_homepage = website_homepage
        self.icon_url = icon_url
        self.url_regex = url_regex

    def get_methods(self):
        """Returns a mapping of actions and their respective methods"""
        return {}


class MicroCenter(Provider):
    """Micro Center Provider"""

    def __init__(self):
        super().__init__(
            friendly_name="Micro Center",
            internal_name="microcenter",
            website_homepage="https://www.microcenter.com/",
            icon_url="https://yt3.googleusercontent.com/DK_uVA19jFp7pf8jCpyzpTJPo1ImEroHlB8pbLbdGEM6llziJfBPcdCAxz-5w8KJobAS4ZR9tQ=s900-c-k-c0x00ffffff-no-rj",
            url_regex=r"https://www.microcenter.com/product/.*",
        )

        self.store_id = 101  # Default store ID for Micro Center

    def get_methods(self):
        return {
            "extract_product_id": self.extract_product_id,
            # "add_product_url": self.product_from_url,
            # "add_product": self.add_product,
            "get_product": self.get_product,
            "product_embed": self.product_embed,
        }

    async def extract_product_id(self, url: str) -> Optional[str]:
        """Extract the product ID from the URL"""
        product_info = await self.scrape_site(url=url)
        return product_info.get("id") if product_info else None

    async def scrape_site(self, id: int = None, url: str = None) -> Optional[dict]:
        """Scrape the product page for product information"""
        if url is None:
            if id is None:
                logger.error("No URL or ID provided")
                return None
            url = f"https://www.microcenter.com/product/{id}/fish"
        logger.info(f"Scraping {url}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, params={"storeid": self.store_id}
                ) as response:
                    if response.status != 200:
                        logger.error(f"Failed to fetch {url}: {response.status}")
                        return None
                    html = await response.text()
                    return await self.parse_html(html)
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    async def parse_html(self, html: str) -> Optional[dict]:
        """Parse the HTML and extract the product information"""
        soup = BeautifulSoup(html, "html.parser")

        # Search for the item status
        item_div = soup.find("div", class_="inventory")
        item_status = item_div.find("span").text

        # Interpret the status
        stock_count = 0
        if "sold out" in item_status.lower():
            in_stock = False
        else:
            if "in stock" in item_status.lower():
                stock_count = item_status.split()[0]
                in_stock = True
            else:
                in_stock = True

        # Find the product header
        header = soup.find("div", class_="product-header")
        if not header:
            logger.error("Product header not found")
            return None

        h1_span = header.find("h1").find("span") if header.find("h1") else None
        if not h1_span:
            logger.error("Product header span not found")
            return None

        # Location
        store_name = soup.find("span", class_="storeName").text.strip()

        # Extract image URL
        try:
            image = (
                soup.find("div", class_="photos")
                .find("div", class_="slides-container")
                .find("img", class_="productImageZoom")
            )
            image_url = image["src"] if image.has_attr("src") else None
        except AttributeError:
            image = None
            image_url = None

        product = {
            "name": h1_span.get("data-name"),
            "price": h1_span.get("data-price"),
            "brand": h1_span.get("data-brand"),
            "id": h1_span.get("data-id"),
            "category": h1_span.get("data-category"),
            "in_stock": in_stock,
            "stock_count": stock_count,
            "store_name": store_name,
            "image": image_url,
        }

        # Optionally, check if all fields are present
        if not all(product.values()):
            logger.warning(f"Some product fields are missing: {product}")

        return product

    async def get_product(self, id: int) -> Optional[dict]:
        """Get the product information for a given product ID"""
        product = await self.scrape_site(id)
        if not product:
            logger.error(f"Failed to get product {id}")
            return None
        return product

    def product_embed(self, product: dict, name: str = None) -> discord.Embed:
        """Create an embed for the product"""
        uri = name.replace(" ", "-").lower() if name else "fish"
        description = f"**${product['price']}**\n"
        description += (
            "In Stock" if product.get("in_stock") else "Out of Stock"
        ) + "\n"
        description += "[Open Product Page]({})\n".format(
            f"https://www.microcenter.com/product/{product['id']}/{uri}"
        )

        embed = discord.Embed(
            title=product["name"],
            description=description,
            color=0x201E1E,
        )
        if product.get("image"):
            embed.set_thumbnail(url=product["image"])
        embed.set_author(
            name=f"{self.friendly_name}{' | ' + product['brand'] if product.get('brand') else ''}",
            url=self.website_homepage,
            icon_url=self.icon_url,
        )
        name_string = ' | "' + name + '"' if name else ""
        embed.set_footer(
            text=f"Product ID: {product['id']}{' | ' + product['store_name'] if product.get('store_name') else ''}{name_string}",
        )
        return embed


# Providers
ALL = [MicroCenter()]


# Core cog
class PriceTracker(commands.Cog):
    def __init__(self, bot: squidcore.Bot):
        self.bot = bot

        # Commands
        self.bot.shell.add_command(
            "pt",
            cog="PriceTracker",
            description="Manage the Price Tracker",
        )

        self.providers = ALL

        self.user_cd = {}

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("Waiting for database to be ready")
        while not self.bot.db.working:
            await asyncio.sleep(1)
        logger.info("Initializing Price Tracker")

        await self.init()

    # Database constants
    SCHEMA = "splat"
    TABLE = "price_tracker"
    TABLE_PRICE_HISTORY = "price_history"
    ADVISORY_LOCK = "49378"  # Arbitrary number for advisory lock

    INIT_SQL = f"""
    SELECT pg_advisory_lock({ADVISORY_LOCK});  -- Arbitrary number, must match across all clients

    CREATE SCHEMA IF NOT EXISTS {SCHEMA};
    
    CREATE TABLE IF NOT EXISTS {SCHEMA}.{TABLE} ( /* Product info */
        id SERIAL PRIMARY KEY, /* Unique ID for the product */
        owner_id BIGINT NOT NULL, /* User ID of the owner */
        dm BOOLEAN DEFAULT FALSE, /* Whether to DM the user for notifications */
        channel_id BIGINT DEFAULT NULL, /* Channel ID to send notifications to */
        name VARCHAR(255) NOT NULL, /* Name of the product */
        provider VARCHAR(255) NOT NULL, /* Provider of the product e.g. Amazon, eBay */
        provider_id VARCHAR(255) NOT NULL, /* Provider's ID/slug for the product */
        mentions TEXT, /* List of user IDs to notify (Appended to each notification) */
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP /* Last time the product was checked for price updates */
    );
    
    CREATE TABLE IF NOT EXISTS {SCHEMA}.{TABLE_PRICE_HISTORY} ( /* Price history */
        id SERIAL PRIMARY KEY, /* Unique ID for the price history entry */
        product_id INT NOT NULL, /* ID of the product */
        price DECIMAL(10, 2) NOT NULL, /* Price of the product */
        in_stock BOOLEAN NOT NULL DEFAULT FALSE, /* Whether the product is in stock or not */
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP, /* Timestamp of when the price was recorded */
        FOREIGN KEY (product_id) REFERENCES {SCHEMA}.{TABLE}(id) ON DELETE CASCADE
    );
    
    SELECT pg_advisory_unlock({ADVISORY_LOCK});  -- Release the advisory lock
    """

    async def init(self):
        if self.refresh_all_products_task.is_running():
            logger.info("Price Tracker is already running")
            return

        logger.info("Initializing...")
        try:
            # Create the database schema
            await self.bot.db.execute(self.INIT_SQL)

            # Fetch data from the database
            self.schema_object = self.bot.db.data.get_schema(self.SCHEMA)
            self.products_table_object = self.schema_object.get_table(self.TABLE)
            self.price_history_table_object = self.schema_object.get_table(
                self.TABLE_PRICE_HISTORY
            )

            asyncio.sleep(5)
            # Start the refresh task
            self.refresh_all_products_task.start()

        except Exception as e:
            logger.error(f"Error initializing Price Tracker: {e}")
            await self.bot.shell.log(
                f"Error initializing Price Tracker: {e}",
                title="Price Tracker Error",
                msg_type="error",
            )
            return

    async def shell_callback(self, command: squidcore.ShellCommand):
        if command.name == "pt":
            # if command.query.startswith("reload"):
            #     # await self.init()
            #     await command.log(
            #         "Successfully reloaded the Price Tracker database",
            #         title="Price Tracker Reloaded",
            #         msg_type="success",
            #     )
            #     return

            if command.query.startswith("update"):
                message = await command.log(
                    "Updating all products...",
                    title="Price Tracker Update",
                    msg_type="info",
                )
                successful, failed, total = await self.refresh_all_products()
                await command.log(
                    f"Successfully updated all products\nS: {successful}\nF: {failed}\nT: {total}",
                    title="Price Tracker Updated",
                    msg_type="success",
                    edit=message,
                )
                return

    async def provider_from_url(self, url: str) -> Optional[Provider]:
        """Get the provider from the URL"""
        for provider in self.providers:
            if hasattr(provider, "url_regex") and provider.url_regex:
                if re.match(provider.url_regex, url):
                    return provider
        return None

    async def _generic_unsupported_error(
        interaction: discord.Interaction, error_type: str
    ):
        """Send a generic unsupported error message"""
        if error_type == "unsupported_provider":
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="Price Tracker: Internal Error",
                    description="This website is not fully supported yet. Please contact the developer.",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            embed=discord.Embed(
                title="Price Tracker: Unsupported Action",
                description="This action is not supported yet. Please contact the developer.",
                color=discord.Color.red(),
            ),
            ephemeral=True,
        )
        return

    async def get_product(
        self,
        product_db_id: Optional[int] = None,
        product_id: Optional[str] = None,
        provider: Optional[Provider] = None,
    ) -> Optional[dict]:
        """Get the product information from the provider"""
        # Call the provider's get_product method
        product = None
        if provider.get_methods().get("get_product"):
            product = await provider.get_methods()["get_product"](product_id)
        if not product:
            return None

        # Add price information to database
        if product_db_id:
            try:
                await self.price_history_table_object.insert(
                    {
                        "product_id": product_db_id,
                        "price": product.get("price"),
                        "in_stock": product.get("in_stock"),
                    }
                )
            except Exception as e:
                logger.error(f"Error adding product price to database: {e}")
                return None
        return product

    def is_user_in_cooldown(self, user_id: int) -> int:
        """Check if the user is in cooldown and return the remaining time"""
        now = datetime.now()
        past_time = self.user_cd.get(user_id, None)
        if past_time:
            if now - past_time < timedelta(seconds=5):
                remaining_time = 5 - (now - past_time).total_seconds()
                return int(remaining_time)
        self.user_cd[user_id] = now
        return 0

    # Track-price command
    @app_commands.command(
        name="track-price",
        description="Track the price of e-commerce products",
    )
    @app_commands.describe(
        name="Give the entry a name (should be easy to recall, i.e. 'intel arc')",
        url="The URL of the product to track",
    )
    async def add_url(
        self,
        interaction: discord.Interaction,
        name: str,
        url: str,
    ):
        """Add a product to the price tracker"""
        # Check if the user is in cooldown
        seconds = self.is_user_in_cooldown(interaction.user.id)
        if seconds > 0:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="Cooldown",
                    description=f"Please wait {seconds} second{'s' if seconds != 1 else ''}.",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return
        await interaction.response.defer(thinking=True)

        # Name must be use alphanumeric characters and underscores, dashes, and spaces
        if not re.match(r"^[\w\s-]+$", name):
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Price Tracker: Invalid Name",
                    description="The name provided is invalid. Please use only alphanumeric characters, underscores, dashes, and spaces.",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return

        # Check if the URL is valid
        provider = await self.provider_from_url(url)

        if not provider:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Price Tracker: Invalid URL",
                    description="The URL provided is invalid or unsupported.",
                    color=discord.Color.red(),
                ).add_field(
                    name="Supported Websites",
                    value="- " + "\n- ".join([p.friendly_name for p in self.providers]),
                ),
                ephemeral=True,
            )
            return

        logger.info(f"Adding product {name} from {provider.friendly_name}")

        # Extract the product id/slug
        if provider.get_methods().get("extract_product_id"):
            product_id = await provider.get_methods()["extract_product_id"](url)
            if not product_id:
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="Price Tracker: Invalid Product ID",
                        description="The product ID could not be extracted from the URL.",
                        color=discord.Color.red(),
                    ),
                    ephemeral=True,
                )
                return
        else:
            await self._generic_unsupported_error(interaction, "unsupported_provider")
            return

        # Get the product information
        if provider.get_methods().get("get_product"):
            product_info = await self.get_product(
                product_id=product_id,
                provider=provider,
            )
            if not product_info:
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="Price Tracker: Product Not Found",
                        description="The product could not be found on the website.",
                        color=discord.Color.red(),
                    ),
                    ephemeral=True,
                )
                return
        else:
            await self._generic_unsupported_error(interaction, "unsupported_provider")
            return
        logger.info(f"Product info: {product_info}")

        # Create the embed
        embed = discord.Embed(
            title="Price Tracker: Product Added",
            description=f"Your product has been successfully added to the price tracker.",
            color=discord.Color.green(),
        ).set_footer(
            text="Tip: Use /track-price-edit for additional settings such as notifications."
        )

        if provider.get_methods().get("product_embed"):
            product_embed = provider.get_methods()["product_embed"](product_info, name)
        else:
            product_embed = (
                discord.Embed(
                    title=product_info.get("name", "Unknown"),
                    description="Product information could not be retrieved.",
                    color=discord.Color.red(),
                )
                .set_footer(text=f"Product ID: {product_info.get('id','Unknown')}")
                .set_author(
                    name=provider.friendly_name,
                )
            )

        # Check if the product already exists
        existing_product = await self.products_table_object.fetch(
            {
                "name": name,
                "owner_id": interaction.user.id,
            }
        )
        if existing_product:
            await interaction.followup.send(
                embeds=[
                    discord.Embed(
                        title="Price Tracker: Product Already Exists",
                        description="The product you are trying to add already exists in the price tracker.",
                        color=discord.Color.red(),
                    ),
                    product_embed,
                ],
                ephemeral=True,
            )
            return

        # Add the product to the database
        try:
            await self.products_table_object.insert(
                {
                    "owner_id": interaction.user.id,
                    "name": name,
                    "provider": provider.internal_name,
                    "provider_id": product_id,
                    "mentions": "",
                }
            )
        except Exception as e:
            logger.error(f"Error adding product: {e}")
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Price Tracker: Error Adding Product",
                    description="There was an error adding the product to the price tracker.",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            embeds=[embed, product_embed],
            ephemeral=False,
        )
        return

    # Track-price-edit command - Test notifcation view
    class TestNotificationView(View):
        def __init__(self, price_tracker: "PriceTracker", product_id: int):
            super().__init__(timeout=60)
            self.bot = price_tracker.bot
            self.price_tracker = price_tracker
            self.product_id = product_id

        @discord.ui.button(label="Test Notification", style=discord.ButtonStyle.primary)
        async def test_notification(
            self, interaction: discord.Interaction, button: discord.ui.Button
        ):
            """Test the notification"""

            # Use the send_notification method to send a test notification
            await interaction.response.defer(thinking=True)
            # Check if the user is in cooldown
            seconds = self.price_tracker.is_user_in_cooldown(interaction.user.id)

            if seconds > 0:
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="Cooldown",
                        description=f"Please wait {seconds} second{'s' if seconds != 1 else ''}.",
                        color=discord.Color.red(),
                    ),
                    ephemeral=True,
                )
                return

            # Get the product from the database
            product = await self.price_tracker.products_table_object.fetch(
                {
                    "id": self.product_id,
                    "owner_id": interaction.user.id,
                }
            )
            if not product:
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="Price Tracker: Product Not Found",
                        description="This product does not exist anymore.",
                        color=discord.Color.red(),
                    ),
                    ephemeral=True,
                )
                return

            # Get the provider
            provider = next(
                (
                    p
                    for p in self.price_tracker.providers
                    if p.internal_name == product[0]["provider"]
                ),
                None,
            )
            if not provider:
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="Price Tracker: Provider Not Found",
                        description="The provider for this product is not supported anymore.",
                        color=discord.Color.red(),
                    ),
                    ephemeral=True,
                )
                return

            # Get the product information
            product_info = await self.price_tracker.get_product(
                product_db_id=product[0]["id"],
                product_id=product[0]["provider_id"],
                provider=provider,
            )
            if not product_info:
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="Price Tracker: Product Not Found",
                        description="The product could not be found on the website.",
                        color=discord.Color.red(),
                    ),
                    ephemeral=True,
                )
                return

            # Send the notification
            try:
                await self.price_tracker.send_notification(
                    product=product[0],
                    provider=provider,
                    product_info=product_info,
                    reason=f"Test notification triggered by {interaction.user.mention}",
                )
            except Exception as e:
                logger.error(f"Error sending test notification: {e}")
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="Price Tracker: Error Sending Test Notification",
                        description="There was an error sending the test notification.",
                        color=discord.Color.red(),
                    ),
                    ephemeral=True,
                )
                return
            await interaction.followup.send(
                content="✅",
            )

            # Disable the button after the test notification is sent
            button.disabled = True
            button.label = "Test Notification Sent"
            await interaction.message.edit(view=self)
            return

    # Track-price-edit command
    @app_commands.command(
        name="track-price-edit",
        description="Edit the settings of a tracked product",
    )
    @app_commands.describe(
        name="The name of the product to edit",
        dm="Use DMs for notifications",
        channel="Use a channel for notifications",
        rm_channel="Disable channel notifications",
        mentions="A string of mentions to use when the product is updated",
        delete="Whether to delete the product from the tracker",
    )
    async def edit_product(
        self,
        interaction: discord.Interaction,
        name: str,
        dm: Optional[bool] = None,
        channel: Optional[discord.TextChannel] = None,
        rm_channel: Optional[bool] = False,
        mentions: Optional[str] = None,
        delete: Optional[bool] = None,
    ):
        """Edit the settings of a tracked product"""
        # Check if the user is in cooldown
        seconds = self.is_user_in_cooldown(interaction.user.id)
        if seconds > 0:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="Cooldown",
                    description=f"Please wait {seconds} second{'s' if seconds != 1 else ''}.",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return
        await interaction.response.defer(thinking=True)

        # Verify parameters
        if not (mentions or delete or dm or channel or rm_channel):
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Price Tracker: Invalid Parameters",
                    description="You must provide at least one parameter to edit.",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return

        # Check if the product exists
        product = await self.products_table_object.fetch(
            {
                "name": name,
                "owner_id": interaction.user.id,
            }
        )
        if not product:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Price Tracker: Product Not Found",
                    description="The product you are trying to edit does not exist.",
                    color=discord.Color.red(),
                ).set_footer(
                    text="Hint: Use /track-price-list to see your tracked products."
                ),
                ephemeral=True,
            )
            return

        # Update the product settings
        data = {}
        embed = discord.Embed(
            title="Price Tracker: Product Updated",
            description="The product has been successfully updated in the price tracker.",
            color=discord.Color.green(),
        )
        if mentions is not None:
            data["mentions"] = mentions
            embed.add_field(
                name="Mentions",
                value=mentions,
                inline=False,
            )
        if dm is not None:
            data["dm"] = dm
            embed.add_field(
                name="DM Notifications",
                value="Enabled" if dm else "Disabled",
                inline=False,
            )
        if channel is not None:
            data["channel_id"] = channel.id
            embed.add_field(
                name="Channel Notifications",
                value=f"Enabled in {channel.mention}",
                inline=False,
            )
        if rm_channel is not None and rm_channel:
            data["channel_id"] = None
            embed.add_field(
                name="Channel Notifications",
                value="Disabled",
                inline=False,
            )
        if delete is not None and delete:
            await self.products_table_object.delete({"id": product[0]["id"]})
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Price Tracker: Product Deleted",
                    description="The product has been successfully deleted from the price tracker.",
                    color=discord.Color.green(),
                ),
                ephemeral=True,
            )
            return

        # Update the database
        try:
            await self.products_table_object.update(
                data=data,
                filters={"id": product[0]["id"]},
            )
        except Exception as e:
            logger.error(f"Error updating product: {e}")
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Price Tracker: Error Updating Product",
                    description="There was an error updating the product in the price tracker.",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            embed=embed,
            view=self.TestNotificationView(self, product[0].get("id")),
        )
        return

    @app_commands.command(
        name="track-price-list",
        description="List all tracked products",
    )
    async def list_products(self, interaction: discord.Interaction):
        """List all tracked products"""
        # Check if the user is in cooldown
        seconds = self.is_user_in_cooldown(interaction.user.id)
        if seconds > 0:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="Cooldown",
                    description=f"Please wait {seconds} second{'s' if seconds != 1 else ''}.",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return
        await interaction.response.defer(thinking=True)

        # Get the products from the database
        products = await self.products_table_object.fetch(
            {
                "owner_id": interaction.user.id,
            }
        )
        if not products:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Price Tracker: No Products Found",
                    description="You have no products tracked.",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return

        # Create the embed
        embed = discord.Embed(
            title="Price Tracker: Your Products",
            description="Here are your tracked products:",
            color=discord.Color.green(),
        )

        for product in products:
            embed.add_field(
                name=product["name"],
                value=f"Provider: {product['provider']}\nID: {product['provider_id']}",
                inline=False,
            )

        await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="track-price-list",
        description="List all tracked products",
    )
    async def list_products(self, interaction: discord.Interaction):
        """List all tracked products"""
        # Check if the user is in cooldown
        seconds = self.is_user_in_cooldown(interaction.user.id)
        if seconds > 0:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="Cooldown",
                    description=f"Please wait {seconds} second{'s' if seconds != 1 else ''}.",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return
        await interaction.response.defer(thinking=True)

        # Get the products from the database
        products = await self.products_table_object.fetch(
            {
                "owner_id": interaction.user.id,
            }
        )
        if (not products) or len(products) == 0:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Price Tracker: No Products Found",
                    description="You have no products tracked.",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return

        # Create the embed
        description = ""
        for product in products:
            # Fetch actual name
            provider = next(
                (p for p in self.providers if p.internal_name == product["provider"]),
                None,
            )
            if not provider:
                logger.error(f"Provider {product['provider']} not found")
                continue
            product_info = await self.get_product(
                product_db_id=product["id"],
                product_id=product["provider_id"],
                provider=provider,
            )
            if not product_info:
                logger.error(f"Product {product['name']} not found")
                continue

            description += f"""1. **"{product['name']}"** ({product_info.get('name','Unknown')})\n"""

        embed = discord.Embed(
            title="Price Tracker: Your Products",
            description=description,
            color=discord.Color.green(),
        )

        await interaction.followup.send(embed=embed)

    # Track-price command
    @app_commands.command(
        name="track-price-info",
        description="Get information about a tracked product or a untracked product url",
    )
    @app_commands.describe(
        name="Name of a tracked product",
        url="Url of an untracked product",
    )
    async def product_info(
        self,
        interaction: discord.Interaction,
        name: str = None,
        url: str = None,
    ):
        """Get information about a tracked product or a untracked product url"""
        # Check if the user is in cooldown
        seconds = self.is_user_in_cooldown(interaction.user.id)
        if seconds > 0:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="Cooldown",
                    description=f"Please wait {seconds} second{'s' if seconds != 1 else ''}.",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return
        await interaction.response.defer(thinking=True)

        if (name) and not url:
            # Name must be use alphanumeric characters and underscores, dashes, and spaces
            if not re.match(r"^[\w\s-]+$", name):
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="Price Tracker: Invalid Name",
                        description="The name provided is invalid. Please use only alphanumeric characters, underscores, dashes, and spaces.",
                        color=discord.Color.red(),
                    ),
                    ephemeral=True,
                )
                return

            # Search for the product in the database
            product = await self.products_table_object.fetch(
                {
                    "name": name,
                    "owner_id": interaction.user.id,
                }
            )
            if (not product) or len(product) == 0:
                await interaction.followup.send(
                    embeds=[
                        discord.Embed(
                            title="Price Tracker: Product Not Found",
                            description="The product you are trying to get information about does not exist. Use /track-price-list to see your tracked products, or use /track-price to add a new product.",
                            color=discord.Color.red(),
                        ),
                    ],
                    ephemeral=True,
                )
                return
            product_id = product[0]["provider_id"]

            provider = next(
                (
                    p
                    for p in self.providers
                    if p.internal_name == product[0]["provider"]
                ),
                None,
            )
            if not provider:
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="Price Tracker: Provider Not Found",
                        description="The provider for this product is not supported anymore. Please contact the developer.",
                        color=discord.Color.red(),
                    ),
                    ephemeral=True,
                )
                return

        # Extract information from the URL
        elif url:
            # Check if the URL is valid
            provider = await self.provider_from_url(url)

            if not provider:
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="Price Tracker: Invalid URL",
                        description="The URL provided is invalid or unsupported.",
                        color=discord.Color.red(),
                    ).add_field(
                        name="Supported Websites",
                        value="- "
                        + "\n- ".join([p.friendly_name for p in self.providers]),
                    ),
                    ephemeral=True,
                )
                return

            logger.info(f"Got {name} from {provider.friendly_name}")

            # Extract the product id/slug
            if provider.get_methods().get("extract_product_id"):
                product_id = await provider.get_methods()["extract_product_id"](url)
                if not product_id:
                    await interaction.followup.send(
                        embed=discord.Embed(
                            title="Price Tracker: Invalid Product ID",
                            description="The product ID could not be extracted from the URL.",
                            color=discord.Color.red(),
                        ),
                        ephemeral=True,
                    )
                    return
            else:
                await self._generic_unsupported_error(
                    interaction, "unsupported_provider"
                )
                return

        else:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Price Tracker: Invalid Parameters",
                    description="You must provide either the name of an already tracked product or the URL of an untracked product.",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return

        # Get the product information
        if provider.get_methods().get("get_product"):
            product_info = await self.get_product(
                product_id=product_id,
                provider=provider,
            )
            if not product_info:
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="Price Tracker: Product Not Found",
                        description="The product could not be found on the website.",
                        color=discord.Color.red(),
                    ),
                    ephemeral=True,
                )
                return
        else:
            await self._generic_unsupported_error(interaction, "unsupported_provider")
            return
        logger.info(f"Product info: {product_info}")

        # Create the embed
        embed = discord.Embed(
            title="Price Tracker: Product Added",
            description=f"Your product has been successfully added to the price tracker.",
            color=discord.Color.green(),
        ).set_footer(
            text="Tip: Use /track-price-edit for additional settings such as notifications."
        )

        if provider.get_methods().get("product_embed"):
            product_embed = provider.get_methods()["product_embed"](product_info, name)
        else:
            product_embed = (
                discord.Embed(
                    title=product_info.get("name", "Unknown"),
                    description="Product information could not be retrieved.",
                    color=discord.Color.red(),
                )
                .set_footer(text=f"Product ID: {product_info.get('id','Unknown')}")
                .set_author(
                    name=provider.friendly_name,
                )
            )

        await interaction.followup.send(
            embed=product_embed,
            ephemeral=False,
        )
        return

    @tasks.loop(minutes=15)
    async def refresh_all_products_task(self):
        """Task to refresh all products in the database"""
        logger.info("Refreshing all products")
        successful, failed, total = await self.refresh_all_products()
        logger.info(
            f"Refreshed {successful} products successfully, {failed} failed out of {total} total."
        )

    async def refresh_all_products(self):
        """Refresh all products in the database"""
        logger.info("Refreshing all products")
        successful, failed, total = 0, 0, 0
        products = await self.products_table_object.fetch()
        for product in products:
            total += 1
            provider = next(
                (p for p in self.providers if p.internal_name == product["provider"]),
                None,
            )
            if not provider:
                failed += 1
                logger.error(f"Provider {product['provider']} not found")
                continue

            # Fetch the price history
            price_history = await self.price_history_table_object.fetch(
                {"product_id": product["id"]},
                order="timestamp DESC",
                limit=1,
            )

            # Get the product information & add to the database
            logger.info(
                f"Getting product {product['name']} from {provider.friendly_name}"
            )
            product_info = await self.get_product(
                product_db_id=product["id"],
                product_id=product["provider_id"],
                provider=provider,
            )
            if not product_info:
                logger.error(f"Product {product['name']} not found")
                failed += 1
                continue

            # If no price history, skip
            if len(price_history) == 0:
                logger.error(
                    f"Price history for product {product['name']} not found, skipping"
                )
                successful += 1
                continue

            # Check if info has changed
            reason = ""

            if product_info.get("in_stock") != price_history[0]["in_stock"]:
                reason += (
                    "Product is now **IN STOCK**"
                    if product_info.get("in_stock")
                    else "Product is **OUT OF STOCK**"
                ) + "\n"

            if float(product_info.get("price")) != float(price_history[0]["price"]):
                reason += (
                    f"Price changed: **${price_history[0]['price']}** -> **${product_info['price']}**"
                ) + "\n"

            if reason == "":
                successful += 1
                # Don't update the user if nothing has changed
                continue

            # Send the notification
            try:
                if not await self.send_notification(
                    product,
                    provider,
                    product_info,
                    reason,
                ):
                    failed += 1
                    continue
            except Exception as e:
                logger.error(f"Error sending notification: {e}")
                failed += 1
                continue
            successful += 1

        return successful, failed, total

    async def send_notification(
        self,
        product: dict,
        provider: Provider,
        product_info: dict,
        reason: str,
    ):
        """
        Send the notification to the user
        Args:
            product (dict): Core product information from the database
            provider (Provider): The provider of the product
            product_info (dict): New product information from the provider
            reason (str): The reason/message for the notification
        """
        logger.info(f"Sending notification for product {product['name']}")
        # Create the embed
        embed = discord.Embed(
            description=reason.strip(),
            color=discord.Color.green(),
        )

        if provider.get_methods().get("product_embed"):
            product_embed = provider.get_methods()["product_embed"](
                product_info, product.get("name")
            )
        else:
            product_embed = (
                discord.Embed(
                    title=product_info.get("name", "Unknown"),
                    description="Product information could not be retrieved.",
                    color=discord.Color.red(),
                )
                .set_footer(text=f"Product ID: {product_info.get('id','Unknown')}")
                .set_author(
                    name=provider.friendly_name,
                )
            )

        # Send the embed to the user
        if product["dm"]:
            try:
                user = await self.bot.fetch_user(product["owner_id"])
                if not user:
                    logger.error(
                        f"User {product['owner_id']} not found, removing from database"
                    )
                    await self.products_table_object.delete({"id": product["id"]})
                    return False
                await user.send(content=user.mention, embeds=[embed, product_embed])
            except discord.Forbidden:
                logger.error(
                    f"User {product['owner_id']} has DMs disabled, removing from database"
                )
                await self.products_table_object.delete({"id": product["id"]})
                return False
            except discord.NotFound:
                logger.error(
                    f"User {product['owner_id']} not found, removing from database"
                )
                await self.products_table_object.delete({"id": product["id"]})
                return False
            except Exception as e:
                logger.error(f"Error fetching user {product['owner_id']}: {e}")
                return False
        if product["channel_id"]:
            channel = self.bot.get_channel(product["channel_id"])
            if not channel:
                logger.error(
                    f"Channel {product['channel_id']} not found, removing from database"
                )
                await self.products_table_object.delete({"id": product["id"]})
                return False
            try:
                await channel.send(
                    content=product["mentions"],
                    embeds=[embed, product_embed],
                )
            except Exception as e:
                logger.error(f"Error sending message to channel {channel.id}: {e}")
                return False
            except discord.Forbidden:
                logger.error(
                    f"Bot does not have permission to send messages in channel {channel.id}, removing from database"
                )
                await self.products_table_object.delete({"id": product["id"]})
                return False
        return True
