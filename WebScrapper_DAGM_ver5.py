import requests
from bs4 import BeautifulSoup
import time
import random
import re
import json
from pathlib import Path
from urllib.parse import urlparse
import tkinter as tk
from tkinter import ttk, messagebox
import unicodedata

# ---------------- CONFIGURACIÓN ----------------

BASE_URL = (
    #"https://www.paginasamarillas.es/search/asesorias-y-gestorias/"
    #"all-ma/madrid/all-is/all-ci/all-ba/all-pu/all-nc/{}"
    #"?co=Asesorias+y+gestorias&what=Asesorias+y+gestorias&ub=false&qc=true"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "es-ES,es;q=0.9"
}

OUTPUT_DIR = Path("resultados")
OUTPUT_DIR.mkdir(exist_ok=True)

telefono_regex = re.compile(r"(\+34\d{9}|\b\d{9}\b)")
email_regex = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
EMAILS_COMUNES = ["info", "contacto", "administracion"]

# ---------------- FUNCIONES AUXILIARES ----------------

from urllib.parse import urlparse, parse_qs

def extraer_info_url(url):
# Extrae el tipo de negocio (what) y la localidad (where) de la URL para usarlos en el nombre del archivo de salida.
    try:
        query = urlparse(url).query
        params = parse_qs(query)
        tipo = params.get("what", ["No disponible"])[0].replace("+", " ")
        localidad = params.get("where", ["No disponible"])[0].replace("+", " ")
        return tipo, localidad
    except:
        return "No disponible", "No disponible"


def limpiar_email(email):
    return email.strip().rstrip(".,;:")

def obtener_email_web(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return None
        match = email_regex.search(r.text)
        return limpiar_email(match.group()) if match else None
    except:
        return None

from urllib.parse import parse_qs, urlparse

def generar_nombre_archivo(base_url):
# Genera un archivo de salida con los parámetros de búsqueda normalizados (what y where) para facilitar la identificación de los resultados.
    try:
        query = urlparse(base_url).query
        params = parse_qs(query)
        what = params.get("what", ["NoDisponible"])[0]
        where = params.get("where", ["NoDisponible"])[0]

        # Normalizar: quitar +, espacios, caracteres especiales y capitalizar
        def normalizar(texto):
            texto = texto.replace("+", " ").strip()
            texto = re.sub(r"[^a-zA-Z0-9]", "", texto)  # solo letras y números
            return texto.capitalize() if texto else "NoDisponible"

        what_norm = normalizar(what)
        where_norm = normalizar(where)

        return f"{what_norm}{where_norm}.json"
    except Exception:
        return "resultados.json"


def obtener_dominio(url):
    try:
        parsed = urlparse(url)
        dominio = parsed.netloc.lower()
        if dominio.startswith("www."):
            dominio = dominio[4:]
        return dominio if "." in dominio else None
    except:
        return None

def normalizar_nombre_empresa(nombre):
  # Normaliza el nombre de la empresa para facilitar comparaciones y evitar duplicados.
    if not nombre or nombre == "No disponible":
        return None

    # Quitar acentos
    nombre = unicodedata.normalize("NFKD", nombre)
    nombre = nombre.encode("ascii", "ignore").decode("ascii")

    nombre = nombre.lower()

    # Eliminar formas jurídicas comunes
    eliminar = [
        " s.l.", " sl", " s.l", " s.a.", " sa", " s.a",
        " sociedad limitada", " sociedad anonima",
        " slp", " s.l.p", " s.c", " sc"
    ]

    for sufijo in eliminar:
        nombre = nombre.replace(sufijo, "")

    # Eliminar todo lo que no sea letras o números
    nombre = re.sub(r"[^a-z0-9]", "", nombre)

    return nombre if len(nombre) >= 3 else None

def obtener_dominio_desde_nombre(nombre):
    base = normalizar_nombre_empresa(nombre)
    if not base:
        return None
    return f"{base}.com"

def obtener_dominio_fiable(data):
# Intenta obtener un dominio de correo electrónico confiable a partir de la información disponible, siguiendo un orden de preferencia.

    #  Desde la web
    if data.get("web") and data["web"] != "No disponible":
        dominio = obtener_dominio(data["web"])
        if dominio:
            return dominio

    #  Desde email real
    if data.get("email") and data["email"] != "No disponible":
        partes = data["email"].split("@")
        if len(partes) == 2:
            return partes[1].lower()

    #  Desde el nombre de la empresa
    if data.get("nombre") and data["nombre"] != "No disponible":
        return obtener_dominio_desde_nombre(data["nombre"])

    return None

def construir_url(base_url, pagina):
# Construye paginación para las urls en base a numero de página dinamico.
    return re.sub(r"/\d+/?$", f"/{pagina}", base_url)

def datosvalidos(data):
  # Verifica si al menos un campo tiene un valor distinto a "No disponible"
    return any(
        valor != "No disponible"
        for valor in data.values()
    )

def normalizar_telefono(telefono):
# Normaliza el número de teléfono para que tenga un formato consistente, preferiblemente con el prefijo internacional +34.
    telefono = telefono.strip().replace(" ", "").replace("-", "")
    
    if telefono.startswith("+"):
        return telefono  # Ya tiene prefijo
    elif len(telefono) == 9 and telefono.isdigit():
        return f"+34{telefono}"
    else:
        return telefono


# ---------------- SCRAPING ----------------
def iniciar_scraping(base_url, max_paginas, scrapear_email_web, log_func):

    for pagina in range(1, max_paginas + 1):
        url = construir_url(base_url, pagina)
        log_func(f"📄 Scrapeando página {pagina}")

        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code != 200:
            log_func(f"❌ Error HTTP {response.status_code}")
            break

        soup = BeautifulSoup(response.text, "html.parser")
        empresas_html = soup.find_all("div", class_="box")

        if not empresas_html:
            log_func("⚠️ No hay más empresas")
            break

        empresas = []

        for empresa in empresas_html:
            time.sleep(random.uniform(0.3, 0.8))

            data = {
                "nombre": "No disponible",
                "telefono": "No disponible",
                "email": "No disponible",
                "email_posible_info": "No disponible",
                "email_posible_contacto": "No disponible",
                "email_posible_administracion": "No disponible",
                "web": "No disponible",
                "direccion": "No disponible",
                "codigo_postal": "No disponible",
                "localidad": "No disponible"
            }

            # Nombre
            tag = empresa.select_one("span[itemprop='name']")
            if tag:
                data["nombre"] = tag.get_text(strip=True)

            # Teléfono
            tel_tag = empresa.find("a", href=re.compile(r"^tel:"))
            if tel_tag:
                data["telefono"] = normalizar_telefono(tel_tag["href"].replace("tel:", "").strip())
            else:
                texto = empresa.get_text(" ", strip=True)
                match = telefono_regex.search(texto)
                if match:
                    data["telefono"] = normalizar_telefono(match.group())

            # Email real
            email_tag = empresa.find("a", href=re.compile(r"^mailto:"))
            if email_tag:
                data["email"] = limpiar_email(
                    email_tag["href"].replace("mailto:", "")
                )
            else:
                texto = empresa.get_text(" ", strip=True)
                match = email_regex.search(texto)
                if match:
                    data["email"] = limpiar_email(match.group())

            # Web
            # Web desde la etiqueta <a class="web">
            web_tag = empresa.find("a", class_="web", href=True)
            if web_tag:
                data["web"] = web_tag["href"].split("?")[0].strip()

            # Email desde web externa
            if scrapear_email_web and data["email"] == "No disponible" and data["web"] != "No disponible":
                email_web = obtener_email_web(data["web"])
                if email_web:
                    data["email"] = email_web

            # Emails posibles
            if data["email"] == "No disponible":
                dominio = obtener_dominio_fiable(data)
            if dominio:
                 data["email_posible_info"] = f"info@{dominio}"
                 data["email_posible_contacto"] = f"contacto@{dominio}"
                 data["email_posible_administracion"] = f"administracion@{dominio}"
                
            # Dirección
            tag = empresa.select_one("span[itemprop='streetAddress']")
            if tag:
                data["direccion"] = tag.get_text(strip=True)

            tag = empresa.select_one("span[itemprop='postalCode']")
            if tag:
                data["codigo_postal"] = tag.get_text(strip=True)

            tag = empresa.select_one("span[itemprop='addressLocality']")
            if tag:
                data["localidad"] = tag.get_text(strip=True)
            
            if datosvalidos(data):
                empresas.append(data)
            else:
                log_func("⏭️ Empresa descartada (sin datos útiles)")


        tipo_empresa, localidad = extraer_info_url(base_url)

        resultado = {
            "localidad": localidad,
            "tipo_empresa": tipo_empresa,
            "resultados": empresas
        }

        nombre_archivo = generar_nombre_archivo(base_url)
        output_file = OUTPUT_DIR / f"{nombre_archivo.replace('.json', '')}_pagina_{pagina}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(resultado, f, ensure_ascii=False, indent=4)

        log_func(f"✅ Página {pagina} guardada ({len(empresas)} empresas)")

    log_func("🎉 Scraping finalizado")

# ---------------- INTERFAZ GRÁFICA ----------------

def lanzar_gui():

    # ---------------- MENÚ CONTEXTUAL ----------------
    def crear_menu_contextual(widget):
        menu = tk.Menu(widget, tearoff=0)
        menu.add_command(label="Cortar", command=lambda: widget.event_generate("<<Cut>>"))
        menu.add_command(label="Copiar", command=lambda: widget.event_generate("<<Copy>>"))
        menu.add_command(label="Pegar", command=lambda: widget.event_generate("<<Paste>>"))

        # Mostrar menú en clic derecho
        def mostrar_menu(event):
            menu.tk_popup(event.x_root, event.y_root)
        
        widget.bind("<Button-3>", mostrar_menu)  # Button-3 = clic derecho

    def log(msg):
        text_log.insert(tk.END, msg + "\n")
        text_log.see(tk.END)
        root.update()

    def ejecutar():
        try:
            paginas = int(entry_paginas.get())
            base_url = entry_url.get().strip()

            iniciar_scraping(
                base_url,
                paginas,
                var_email_web.get(),
                log
            )

            messagebox.showinfo("Finalizado", "Scraping completado")

        except ValueError:
            messagebox.showerror("Error", "Número de páginas inválido")


    root = tk.Tk()
    root.title("WebScraper Páginas Amarillas")
    root.geometry("600x450")

    frame = ttk.Frame(root, padding=10)
    frame.pack(fill="both", expand=True)

    ttk.Label(frame, text="URL:").pack(anchor="w")

    entry_url = ttk.Entry(frame)
    entry_url.insert(
    0,
    ""
    )
    entry_url.pack(fill="x", pady=5)
    crear_menu_contextual(entry_url)

    ttk.Label(frame, text="Número de páginas:").pack(anchor="w")
    entry_paginas = ttk.Entry(frame)
    entry_paginas.insert(0, "3")
    entry_paginas.pack(fill="x")
    crear_menu_contextual(entry_paginas)

    var_email_web = tk.BooleanVar(value=True)
    ttk.Checkbutton(
        frame,
        text="Buscar email en web externa",
        variable=var_email_web
    ).pack(anchor="w", pady=5)

    ttk.Button(
        frame,
        text="Iniciar scraping",
        command=ejecutar
    ).pack(pady=10)

    text_log = tk.Text(frame, height=15)
    text_log.pack(fill="both", expand=True)
    crear_menu_contextual(text_log)

    root.mainloop()

# ---------------- MAIN ----------------

if __name__ == "__main__":
    lanzar_gui()
