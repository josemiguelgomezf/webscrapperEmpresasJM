import requests
from bs4 import BeautifulSoup
import time
import random
import re
import json

# ----------- CONFIGURACIÓN -----------
BASE_URL = "https://www.paginasamarillas.es/search/asesorias-y-gestorias/all-ma/madrid/all-is/all-ci/all-ba/all-pu/all-nc/{}?co=Asesorias+y+gestorias&what=Asesorias+y+gestorias&ub=false&qc=true"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "es-ES,es;q=0.9"
}

telefono_regex = re.compile(r"(\+34\d{9}|\b\d{9}\b)")

empresas = []

# ----------- SCRAPING AUTOMÁTICO POR PÁGINA -----------
pagina = 1

while True:
    url = BASE_URL.format(pagina)
    print(f"Scrapeando página {pagina}: {url}")

    response = requests.get(url, headers=HEADERS, timeout=15)
    if response.status_code != 200:
        print(f"No se pudo acceder a la página {pagina}. Código: {response.status_code}")
        break

    soup = BeautifulSoup(response.text, "html.parser")
    empresas_html = soup.find_all("div", class_="box")

    # Si no hay empresas, finalizamos
    if not empresas_html:
        print("No hay más empresas, finalizando scraping.")
        break

    for empresa in empresas_html:
        time.sleep(random.uniform(0.3, 0.8))  # delay por empresa

        nombre_empresa = "No disponible"
        telefono = "No disponible"
        sitio_web = "No disponible"
        direccion = "No disponible"
        codigo_postal = "No disponible"
        localidad = "No disponible"

        # Nombre empresa
        nombre_tag = empresa.select_one("span[itemprop='name']")
        if nombre_tag:
            nombre_empresa = nombre_tag.get_text(strip=True)

        # Teléfono
        tel_tag = empresa.find("a", href=re.compile(r"^tel:"))
        if tel_tag:
            telefono = tel_tag['href'].replace("tel:", "").strip()
        else:
            texto_empresa = empresa.get_text(" ", strip=True)
            match = telefono_regex.search(texto_empresa)
            if match:
                telefono = match.group()

        # Sitio web
        for a_tag in empresa.find_all("a", href=True):
            href = a_tag['href'].strip()
            if href.startswith("http") and "paginasamarillas" not in href and not href.startswith("tel:") and not href.startswith("mailto:"):
                sitio_web = href
                break

        # Dirección
        direccion_tag = empresa.select_one("span[itemprop='streetAddress']")
        if direccion_tag:
            direccion = direccion_tag.get_text(strip=True)

        # Código postal
        cp_tag = empresa.select_one("span[itemprop='postalCode']")
        if cp_tag:
            codigo_postal = cp_tag.get_text(strip=True)

        # Localidad
        localidad_tag = empresa.select_one("span[itemprop='addressLocality']")
        if localidad_tag:
            localidad = localidad_tag.get_text(strip=True)

        empresas.append({
            "Nombre empresa": nombre_empresa,
            "Telefono": telefono,
            "Sitio web": sitio_web,
            "Direccion": direccion,
            "Codigo postal": codigo_postal,
            "Localidad": localidad
        })

    pagina += 1
    time.sleep(random.uniform(1.5, 3))  # delay entre páginas

# ----------- GUARDAR RESULTADOS EN JSON -----------
with open("empresas_madrid_todas.json", "w", encoding="utf-8") as f:
    json.dump(empresas, f, ensure_ascii=False, indent=4)

print(f"Scraping completado. {len(empresas)} empresas guardadas en empresas_madrid_todas.json")