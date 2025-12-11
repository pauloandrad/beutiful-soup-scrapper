from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
from datetime import datetime
from bs4 import BeautifulSoup

import pandas as pd
import sqlite3
import pytz
import os

load_dotenv()

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

def get_value_by_dusk(soup, dusk, element=None, class_name=None):
    row = soup.find('div', attrs={'dusk': dusk})

    if row:
        class_to_find = class_name or 'md:w-3/4'
        element_to_find = element or 'div'

        container = row.find(element_to_find, class_=lambda c: c and class_to_find in c)

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

def format_date_time(date_str):
    date_str = date_str.replace('Creación: ', '').replace('noviembre', 'November')
    date_format = "%d %B %Y %H:%M:%S"

    return datetime.strptime(date_str, date_format)

def get_order(soup):
    return {
        'id': get_value_by_dusk(soup, 'id'),
        'estado': get_value_by_dusk(soup, 'ComputedField'),
        'numero_guia': get_value_by_dusk(soup, 'number'),
        'fecha_creacion': format_date_time(get_value_by_dusk(soup, 'fechas', 'span', 'font-semibold')),
        'bodega': get_value_by_dusk(soup, 'throughCellar'),
        'transportadora': get_value_by_dusk(soup, 'transportadora'),
        'tienda': get_value_by_dusk(soup, 'throughStore'),
        'productos': get_value_by_dusk(soup, 'productos'),
        'orden_id': get_value_by_dusk(soup, 'order'),
    }

def insert_status_history(history, guide_id):
    conn = sqlite3.connect(os.getenv("GUIDE_DB"))
    cursor = conn.cursor()

    for status in history:
        update_date = datetime.strptime(status['fecha_y_hora'], '%m/%d/%Y, %I:%M %p GMT-5')

        cursor.execute('''
               INSERT INTO historial_estados (guia_id, estado, comentarios, fecha_y_hora, creado_por)
               VALUES (?, ?, ?, ?, ?)
               ''', (
            guide_id,
            status['estado'],
            status['comentarios'],
            update_date,
            status['creado_por']
        ))

    conn.commit()
    conn.close()

def insert_order_into_db(order_data):
    conn = sqlite3.connect(os.getenv("GUIDE_DB"))
    cursor = conn.cursor()

    cursor.execute('''
    INSERT INTO guias (id, estado, numero_guia, fecha_creacion, bodega, transportadora, tienda, productos, orden_id)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        order_data['id'],
        order_data['estado'],
        order_data['numero_guia'],
        order_data['fecha_creacion'],
        order_data['bodega'],
        order_data['transportadora'],
        order_data['tienda'],
        order_data['productos'],
        order_data['orden_id']
    ))

    conn.commit()
    conn.close()

def create_sqlite_db():
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS guias (
        id INTEGER PRIMARY KEY,
        estado TEXT,
        numero_guia TEXT,
        fecha_creacion DATETIME,
        bodega TEXT,
        transportadora TEXT,
        tienda TEXT,
        productos TEXT,
        orden_id TEXT
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS historial_estados (
        id INTEGER PRIMARY KEY,
        guia_id INTEGER,
        estado TEXT,
        comentarios TEXT,
        fecha_y_hora DATETIME,
        creado_por TEXT,
        FOREIGN KEY (guia_id) REFERENCES guias (id)
    )
    ''')

    conn.commit()


def get_last_inserted_guide_id():
    sql = "SELECT MAX(id) FROM guias"

    cursor.execute(sql)

    max_guide_id= cursor.fetchone()

    return max_guide_id[0] if max_guide_id else 0

def extract_guide_data(guide_ids):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)

        context = browser.new_context()
        context.add_cookies(COOKIES)

        page = context.new_page()

        get_last_inserted_guide_id()

        for guide_id in guide_ids:
            page.goto(os.getenv('GUIDE_BASE_URL') + str(guide_id))

            try:
                page.wait_for_selector('[dusk="id"]', timeout=5000)
                page.wait_for_selector('[dusk="resource-table"]', timeout=5000)
            except Exception as e:
                print(f"Seletor '[dusk=\"id\"]' não encontrado para o guia {guide_id}. Continuando...")
                continue

            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')
            order = get_order(soup)

            status_list = get_status_list(soup)

            insert_order_into_db(order)
            insert_status_history(status_list, order['id'])

        browser.close()

if __name__ == "__main__":
    conn = sqlite3.connect(os.getenv("GUIDE_DB"))
    cursor = conn.cursor()

    create_sqlite_db()

    max_id = get_last_inserted_guide_id()

    df_col_guides = pd.read_csv('./colombia/1765406867-guides.csv')
    ids = [id for id in df_col_guides['ID'] if id > max_id]

    extract_guide_data(ids)

    conn.close()