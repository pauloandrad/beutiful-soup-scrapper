from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

import os

load_dotenv()

GUIDE_BASE_URL = "https://hoko.com.co/admin/resources/guides/"
OUTPUT_FILE = "/hoko_guias_links.csv"
COOKIES = [
    {
        "name": "hoko_colombia_session",
        "value": os.getenv('HOKO_SESSION'),
        "domain": ".hoko.com.co",
        "path": "/",
        "httpOnly": True,
        "secure": True,
    },
    {
        "name": "XSRF-TOKEN",
        "value": os.getenv('XSRF_TOKEN'),
        "domain": ".hoko.com.co",
        "path": "/",
        "httpOnly": True,
        "secure": True,
    }
]

def get_value_by_dusk(soup, dusk, class_name):
    row = soup.find('div', attrs={'dusk': dusk})

    if row:
        container = row.find('div', class_=lambda c: c and 'md:w-3/4' in c)

        if container:
            return container.get_text(strip=True)

    return None

def extract_guide_data():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)

        context = browser.new_context()
        context.add_cookies(COOKIES)

        page = context.new_page()
        page.goto(GUIDE_BASE_URL + "1774435")

        page.wait_for_selector('[dusk="id"]')

        html = page.content()

        soup = BeautifulSoup(html, 'html.parser')

        order = {
            'id': get_value_by_dusk(soup, 'id'),
            'status': get_value_by_dusk(soup, 'ComputedField'),
            'guide_number': get_value_by_dusk(soup, 'number'),
            'creationDate': get_value_by_dusk(soup, 'fechas'),
            'supplier': get_value_by_dusk(soup, 'throughCellar'),
            'carrier': get_value_by_dusk(soup, 'transportadora'),
            'store': get_value_by_dusk(soup, 'throughStore'),
            'product_info': get_value_by_dusk(soup, 'productos'),
            'branch': get_value_by_dusk(soup, 'ComputedField'),
            'order_id': get_value_by_dusk(soup, 'order'),
        }

        print(order)

        with open("./output/teste.html", 'w', encoding='utf-8') as file:
            file.write(html)

        browser.close()

if __name__ == "__main__":
    ids = [1774435]

    extract_guide_data()





