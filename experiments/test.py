# Simple python script to scrape a website and check if an item is in stock

import requests
from bs4 import BeautifulSoup

urls = [
    "https://www.microcenter.com/product/690491/msi-nvidia-geforce-rtx-5090-ventus-3x-overclocked-triple-fan-32gb-gddr7-pcie-50-graphics-card",
    "https://www.microcenter.com/product/689735/asus-nvidia-geforce-rtx-5080-rog-astral-overclocked-triple-fan-16gb-gddr7-pcie-50-graphics-card",
    "https://www.microcenter.com/product/689241/intel-arc-b580-limited-edition-dual-fan-12gb-gddr6-pcie-40-graphics-card",
        "https://www.microcenter.com/product/1234/fake-product-name-1",

]

for url in urls:
    print(f"Url: {url}")

    # Get the page
    page = requests.get(url, params={"storeid": "101"})

    if page.status_code == 404:
        print("Page not found")
        continue

    if page.status_code != 200:
        print("Failed to get page")
        continue

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

    # Determine the item name/info
    header = soup.find("div", class_="product-header").find("h1").find("span")

    item_name = header["data-name"] if header.has_attr("data-name") else None
    item_id = header["data-id"] if header.has_attr("data-id") else None
    item_price = header["data-price"] if header.has_attr("data-price") else None
    item_brand = header["data-brand"] if header.has_attr("data-brand") else None
    item_category = (
        header["data-category"] if header.has_attr("data-category") else None
    )
    
    # Extract image URL
    try:
        image = soup.find("div", class_="photos").find("div", class_="slides-container").find("img", class_="productImageZoom")
        image_url = image["src"] if image.has_attr("src") else None
    except AttributeError:
        image = None
        image_url = None

    print(f"Item name: {item_name}")
    print(f"Item ID: {item_id}")
    print(f"Item Price: ${item_price}")
    print(f"Item Brand: {item_brand}")
    print(f"Item Category: {item_category}")
    print(f"Image URL: {image_url}")

    print("-----------------------------------")