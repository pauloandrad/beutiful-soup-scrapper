from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

import os
import re

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

def get_value_by_dusk(soup, dusk, class_name=None):
    row = soup.find('div', attrs={'dusk': dusk})

    if row:
        container = row.find('div', class_=lambda c: c and 'md:w-3/4' in c)

        if container:
            return container.get_text(strip=True)

    return None


def normalize_to_snake_case(text):
    if not text: return ""

    text = text.replace(' ', '_')

    text = text.lower()

    return text

def get_status_list(soup):
    status_list = []

    table = soup.find('table', attrs={'dusk': 'resource-table'})

    if not table:
        print("Table 'resource-table' not found.")
        return status_list

    header_row = table.find('thead').find('tr')

    headers = [th.get_text(strip=True) for th in header_row.find_all('th')[:-1]]
    headers = [normalize_to_snake_case(h) for h in headers]

    body = table.find('tbody')

    data_rows = body.find_all('tr') if body else []

    for row in data_rows:
        cells = row.find_all('td')

        data_cells = cells[:len(headers)]

        row_data = {}
        for i, cell in enumerate(data_cells):
            column_name = headers[i]

            value = cell.get_text(strip=True)

            if value == '—':
                value = ''

            row_data[column_name] = value

        status_list.append(row_data)

    return status_list

def extract_guide_data():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)

        context = browser.new_context()
        context.add_cookies(COOKIES)

        page = context.new_page()
        page.goto(GUIDE_BASE_URL + "1774435")

        page.wait_for_selector('[dusk="id"]')
        page.wait_for_selector('[dusk="resource-table"]')

        html = page.content()

        soup = BeautifulSoup(html, 'html.parser')

        order = {
            'id': get_value_by_dusk(soup, 'id'),
            'estado': get_value_by_dusk(soup, 'ComputedField'),
            'numero_guia': get_value_by_dusk(soup, 'number'),
            'fecha_creacion': get_value_by_dusk(soup, 'fechas'),
            'bodega': get_value_by_dusk(soup, 'throughCellar'),
            'transportadora': get_value_by_dusk(soup, 'transportadora'),
            'tienda': get_value_by_dusk(soup, 'throughStore'),
            'productis': get_value_by_dusk(soup, 'productos'),
            'orden_id': get_value_by_dusk(soup, 'order'),
        }

        status_list = get_status_list(soup)

        print(status_list)

        with open("./output/teste.html", 'w', encoding='utf-8') as file:
            file.write(html)

        browser.close()

if __name__ == "__main__":
    ids = [1774435]

    extract_guide_data()





