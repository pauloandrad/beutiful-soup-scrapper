from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
from datetime import datetime
from bs4 import BeautifulSoup

import pandas as pd
import sqlite3
import os

load_dotenv()

COOKIES = [
    {
        "name": "hoko_colombia_session",
        "value": os.getenv('HOKO_COL_SESSION'),
        "domain": ".hoko.com.co",
        "path": "/",
        "httpOnly": True,
        "secure": True,
    },
    {
        "name": "hoko_ecuador_session",
        "value": os.getenv('HOKO_ECU_SESSION'),
        "domain": ".hoko.com.ec",
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
    },
    {
        "name": "XSRF-TOKEN",
        "value": os.getenv('XSRF_TOKEN'),
        "domain": ".hoko.com.ec",
        "path": "/",
        "httpOnly": True,
        "secure": True,
    }
]

def insert_status_history(history, guide_id):
    for status in history:
        update_date = None

        try:
            update_date  = datetime.strptime(status['fecha_y_hora'], '%m/%d/%Y, %I:%M %p GMT-5')
        except ValueError:
            pass

        try:
            update_date =  datetime.strptime(status['fecha_y_hora'], "%Y-%m-%d %I:%M:%S %p")
        except ValueError:
            pass

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

def insert_order_into_db(order_data):
    cursor.execute('''
    INSERT INTO guias (id, estado, numero_guia, fecha_creacion, bodega, transportadora, tienda, productos, pais, orden_id)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        order_data['id'],
        order_data['estado'],
        order_data['numero_guia'],
        order_data['fecha_creacion'],
        order_data['bodega'],
        order_data['transportadora'],
        order_data['tienda'],
        order_data['productos'],
        order_data['pais'],
        order_data['orden_id']
    ))

    conn.commit()

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
        pais TEXT,
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

def get_status_list(soup, attrs):
    status_list = []

    table = soup.find('table', attrs={attrs: 'resource-table'})

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

def format_date_time_ecu(date_str):
    date_format = "%Y-%m-%d %I:%M:%S %p"
    print(date_str)
    date_str = date_str.strip()

    return datetime.strptime(date_str, date_format)

def get_col_order(soup):
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
        'pais': 'COL'
    }


def get_ecu_order(soup):
    field_map = {
        'id': 'ID',
        'estado': 'Estado',
        'numero_guia': 'Numero de guia',
        'fecha_creacion': 'Fecha de creación',
        'transportadora': 'Transportadora',
        'bodega': 'Centro de costos',
        'tienda': 'Tienda',
        'productos': 'Produtos',
        'orden_id': 'Orden',
    }

    results = {}

    for key, title in field_map.items():
        value = get_value_by_title(soup, title)

        if key == 'fecha_creacion' and value:
            results[key] = format_date_time_ecu(value)
        else:
            results[key] = value

    results['pais'] = 'ECU'

    return results

def get_value_by_title(soup, title_text):
    title_tag = soup.find('h4', string=title_text)

    if not title_tag: return None

    row_div = title_tag.find_parent(class_=lambda c: c and 'flex border-b border-40' in c)

    if row_div:
        value_div = row_div.find('div', class_=lambda c: c and 'w-3/4 py-4 break-words' in c)

        if value_div:
            anchor_tag = value_div.find('a')

            if anchor_tag and title_text == 'Orden': return anchor_tag.get_text(strip=True)

            return value_div.get_text(strip=True)

    return None

def get_last_inserted_guide_id():
    sql = "SELECT MAX(id) FROM guias"

    cursor.execute(sql)

    max_guide_id = cursor.fetchone()

    return max_guide_id[0] if max_guide_id else 0

def extract_col_guide_data(guide_ids):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)

        context = browser.new_context()
        context.add_cookies(COOKIES)

        page = context.new_page()

        for guide_id in guide_ids:
            page.goto(os.getenv('HOKO_COL_GUIDE_BASE_URL') + str(guide_id))

            try:
                page.wait_for_selector('[dusk="id"]', timeout=5000)
                page.wait_for_selector('[dusk="resource-table"]', timeout=5000)

            except Exception as e:
                print(f"Seletor '[dusk=\"id\"]' não encontrado para o guia {guide_id}. Continuando...")
                continue

            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')
            order = get_col_order(soup)

            status_list = get_status_list(soup, 'dusk')

            insert_order_into_db(order)
            insert_status_history(status_list, order['id'])

        browser.close()

def extract_ecu_guide_data(guide_ids):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)

        context = browser.new_context()
        context.add_cookies(COOKIES)

        page = context.new_page()

        for guide_id in guide_ids:
            page.goto(os.getenv('HOKO_ECU_GUIDE_BASE_URL') + str(guide_id))

            try:
                page.wait_for_selector('[dusk="guides-detail-component"]', timeout=10000)
                page.wait_for_selector('[data-testid="resource-table"]', timeout=10000)

            except Exception as e:
                print(f"Seletor '[dusk=\"id\"]' não encontrado para o guia {guide_id}. Continuando...")
                continue

            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')
            order = get_ecu_order(soup)

            status_list = get_status_list(soup, 'data-testid')

            insert_order_into_db(order)
            insert_status_history(status_list, order['id'])

        browser.close()

def execute_hoko_col_scrapper():
    max_id = get_last_inserted_guide_id()

    df_col_guides = pd.read_csv('./colombia/1765406867-guides.csv')
    ids = [id for id in df_col_guides['ID'] if id > max_id]

    extract_col_guide_data(ids)

def execute_hoko_ecu_scrapper():
    df_ecu_guides = pd.read_csv('./ecuador/1765499388-guides.csv')
    ids = df_ecu_guides['ID'].tolist()

    extract_ecu_guide_data(ids)

if __name__ == "__main__":
    conn = sqlite3.connect(os.getenv("GUIDE_DB"))
    cursor = conn.cursor()

    create_sqlite_db()

    execute_hoko_ecu_scrapper()

    cursor.close()
    conn.close()