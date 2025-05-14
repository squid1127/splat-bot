# Simple python script to scrape a website and check if an item is in stock

import requests
from bs4 import BeautifulSoup


url = "https://www.microcenter.com/product/689241/intel-arc-b580-limited-edition-dual-fan-12gb-gddr6-pcie-40-graphics-card?storeid=101"

# Get the page
page = requests.get(url)

if page.status_code != 200:
    print("Failed to get page")
    exit(1)
    
# Parse the page
soup = BeautifulSoup(page.content, "html.parser")

# Search for the item status
item_div = soup.find("div", class_="inventory")
item_status = item_div.find("span").text

# Interpret the status
if "sold out" in item_status.lower():
    print("Item is out of stock")
else:
    if "in stock" in item_status.lower():
        stock_count = item_status.split()[0]
        print(f"Item is in stock with {stock_count} available")
    else:
        print("Item is in stock")
        
# Determine the price
price_div = soup.find("div", class_="pricing")
price_p = price_div.find("p", class_="big-price")
price = price_p.find("span").text.strip()
print(f"Price: {price}")