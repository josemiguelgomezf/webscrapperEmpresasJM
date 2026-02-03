import requests
from bs4 import BeautifulSoup
import time
import random
import re
import json

URL = "https://www.paginasamarillas.es/search/asesorias-y-gestorias/all-ma/madrid/all-is/coslada/all-ba/all-pu/all-nc/1?what=asesorias+y+gestorias&where=coslada&qc=true"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "es-ES,es;q=0.9"
}

response = requests.get(URL, headers=HEADERS, timeout=15)
response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")

empresas_html = soup.find_all("div", class_="box")
print(f"Empresas encontradas: {len(empresas_html)}")

empresas = []

# Regex para teléfono español: +34 seguido de 9 dígitos o 9 dígitos local
telefono_regex = re.compile(r"(\+34\d{9}|\b\d{9}\b)")

for empresa in empresas_html:
    time.sleep(random.uniform(0.3, 0.8))

    # Inicializamos valores
    nombre_empresa = "No disponible"
    telefono = "No disponible"
    sitio_web = "No disponible"

    # 1️⃣ Nombre de la empresa: buscar <span itemprop="name">
    nombre_tag = empresa.select_one("span[itemprop='name']")
    if nombre_tag:
        nombre_empresa = nombre_tag.get_text(strip=True)

    # 2️⃣ Teléfono: primero buscar tel:, si no buscar patrón de números
    tel_tag = empresa.find("a", href=re.compile(r"^tel:"))
    if tel_tag:
        telefono = tel_tag['href'].replace("tel:", "").strip()
    else:
        texto_empresa = empresa.get_text(" ", strip=True)
        match = telefono_regex.search(texto_empresa)
        if match:
            telefono = match.group()

    # 3️⃣ Sitio web
    for a_tag in empresa.find_all("a", href=True):
        href = a_tag['href'].strip()
        if href.startswith("http") and "paginasamarillas" not in href and not href.startswith("tel:") and not href.startswith("mailto:"):
            sitio_web = href
            break

    empresas.append({
        "Nombre empresa": nombre_empresa,
        "Telefono": telefono,
        "Sitio web": sitio_web
    })

# Guardar resultados en JSON
with open("empresas.json", "w", encoding="utf-8") as f:
    json.dump(empresas, f, ensure_ascii=False, indent=4)

print("Archivo empresas.json generado correctamente con la información extraída.")


