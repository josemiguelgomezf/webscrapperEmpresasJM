import mysql.connector
import tkinter as tk
from tkinter import ttk, messagebox
import smtplib
from email.message import EmailMessage
import os
from pathlib import Path
from dotenv import load_dotenv

# ---------------- CONFIG ----------------
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def env_int(key, default):
    try:
        return int(os.getenv(key, default))
    except (TypeError, ValueError):
        return default


DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": env_int("DB_PORT", 3306),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME"),
    "charset": os.getenv("DB_CHARSET", "utf8mb4"),
}

SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = env_int("SMTP_PORT", 587)
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")

ESTADOS_DESCRIPCION = {
    "EN": "Enviado",
    "ER": "Error",
    "PE": "Pendiente",
}

PLANTILLA_EMAIL = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>JMOrdenadores</title>
</head>
<body style="margin:0; padding:0; background-color:#f4f6f8; font-family: Arial, Helvetica, sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f6f8; padding:20px;">
  <tr>
    <td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="background-color:#ffffff; border-radius:8px; overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,0.05);">
        
        <tr>
          <td style="background-color:#0b3c5d; padding:20px; text-align:center;">
            <img src="https://jmordenadores.com/assets/logoblue-DnLYxD6_.png"
                 alt="JMOrdenadores"
                 style="max-width:220px;">
          </td>
        </tr>

        <tr>
          <td style="padding:30px; color:#333333; font-size:15px; line-height:1.6;">

            <p>{saludo}</p>

            <p>
              Nos ponemos en contacto tras revisar vuestra actividad como 
              {tipo_empresa} en {localidad}.
            </p>

            <p>
              En <strong>JMOrdenadores</strong> ofrecemos soluciones informáticas
              específicas para empresas en su zona,
              ayudando a mejorar el rendimiento, la seguridad y la estabilidad
              de sus sistemas.
            </p>

            <p style="margin:20px 0;">
              <strong>Queremos que nos conozcáis sin compromiso:</strong>
            </p>

            <ul style="padding-left:20px;">
              <li><strong>Primera visita totalmente gratuita</strong></li>
              <li><strong>Resolución de la primera incidencia sin coste</strong></li>
            </ul>

            <p>Además, ofrecemos:</p>

            <ul style="padding-left:20px;">
              <li>Soporte informático cercano y profesional</li>
              <li>Venta y configuración de equipos y dispositivos</li>
              <li>Servidores de almacenamiento y copias de seguridad</li>
              <li>Consultoría en ciberseguridad</li>
              <li>Planes de mantenimiento con cuotas mensuales</li>
              <li>Precios muy competitivos</li>
            </ul>

            <p>
              Nuestro objetivo es que negocios como <strong>{empresa}</strong>
              puedan centrarse en su actividad mientras nosotros nos ocupamos
              de que la infraestructura informática funcione sin problemas.
            </p>

            <p style="text-align:center; margin:30px 0;">
              <a href="https://jmordenadores.com"
                 style="background-color:#0b3c5d; color:#ffffff; text-decoration:none; padding:12px 25px; border-radius:5px; display:inline-block;">
                Visitar nuestra web
              </a>
            </p>

            <p>
              No duden en contactarnos, estaremos encantados de valorar vuestra situación sin ningún compromiso.
            </p>

            <p style="margin-top:30px;">
              Un saludo,<br>
              <strong>José Miguel</strong><br>
              JMOrdenadores
            </p>

          </td>
        </tr>

        <tr>
          <td style="background-color:#f0f0f0; padding:15px; text-align:center; font-size:12px; color:#777;">
            © JMOrdenadores · Soporte informático profesional<br>
            <a href="https://jmordenadores.com" style="color:#0b3c5d; text-decoration:none;">
              jmordenadores.com
            </a>
          </td>
        </tr>

      </table>
    </td>
  </tr>
</table>
</body>
</html>
"""


# ---------------- DB ----------------
def conectar_db():
    return mysql.connector.connect(**DB_CONFIG)


def obtener_empresas():
    conn = conectar_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id_empresa, nombre FROM empresa ORDER BY nombre")
    empresas = cursor.fetchall()
    cursor.close()
    conn.close()
    return empresas


def _obtener_columnas_tabla(cursor, nombre_tabla):
    cursor.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s
        """,
        (DB_CONFIG["database"], nombre_tabla),
    )
    columnas = set()
    for fila in cursor.fetchall():
        if isinstance(fila, dict):
            nombre_columna = (
                fila.get("column_name")
                or fila.get("COLUMN_NAME")
                or fila.get("Column_name")
            )
            if nombre_columna:
                columnas.add(nombre_columna)
        elif fila:
            columnas.add(fila[0])
    return columnas


def _tabla_tiene_columna(cursor, nombre_tabla, nombre_columna):
    return nombre_columna in _obtener_columnas_tabla(cursor, nombre_tabla)


def _tabla_existe(cursor, nombre_tabla):
    cursor.execute(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = %s AND table_name = %s
        """,
        (DB_CONFIG["database"], nombre_tabla),
    )
    return cursor.fetchone() is not None


def _primera_columna_existente(columnas, candidatas):
    for candidata in candidatas:
        if candidata in columnas:
            return candidata
    return None


def _asegurar_tabla_email_estado(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS email_estado (
            id_email INT NOT NULL,
            id_estado VARCHAR(2) NOT NULL,
            fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (id_email)
        )
        """
    )


def actualizar_estado_email(registro, id_estado):
    conn = conectar_db()
    cursor = conn.cursor(dictionary=True)

    try:
        columnas_email = _obtener_columnas_tabla(cursor, "email")
        columna_estado_en_email = _primera_columna_existente(
            columnas_email, ["id_estado", "id_estado_email", "estado_email", "estado"]
        )
        columna_pk_email = _primera_columna_existente(columnas_email, ["id_email"])
        columna_email_texto = _primera_columna_existente(columnas_email, ["email"])

        if columna_estado_en_email and columna_pk_email and registro.get("id_email"):
            cursor.execute(
                f"UPDATE email SET {columna_estado_en_email} = %s WHERE {columna_pk_email} = %s",
                (id_estado, registro["id_email"]),
            )
            conn.commit()
            return

        if columna_estado_en_email and columna_email_texto and registro.get("email"):
            cursor.execute(
                f"UPDATE email SET {columna_estado_en_email} = %s WHERE {columna_email_texto} = %s",
                (id_estado, registro["email"]),
            )
            conn.commit()
            return

        columnas_estado = _obtener_columnas_tabla(cursor, "estado_email")
        columna_estado = _primera_columna_existente(
            columnas_estado, ["id_estado", "id_estado_email", "estado_email", "estado"]
        )
        columna_ref_id_email = _primera_columna_existente(columnas_estado, ["id_email"])
        columna_ref_email = _primera_columna_existente(columnas_estado, ["email"])
        columna_ref_empresa = _primera_columna_existente(columnas_estado, ["id_empresa"])

        if columna_ref_id_email and columna_estado and registro.get("id_email"):
            cursor.execute(
                f"SELECT 1 FROM estado_email WHERE {columna_ref_id_email} = %s",
                (registro["id_email"],),
            )
            existe = cursor.fetchone() is not None
            if existe:
                cursor.execute(
                    f"UPDATE estado_email SET {columna_estado} = %s WHERE {columna_ref_id_email} = %s",
                    (id_estado, registro["id_email"]),
                )
            else:
                cursor.execute(
                    f"INSERT INTO estado_email ({columna_ref_id_email}, {columna_estado}) VALUES (%s, %s)",
                    (registro["id_email"], id_estado),
                )
            conn.commit()
            return

        if columna_ref_email and columna_estado and registro.get("email"):
            cursor.execute(
                f"SELECT 1 FROM estado_email WHERE {columna_ref_email} = %s",
                (registro["email"],),
            )
            existe = cursor.fetchone() is not None
            if existe:
                cursor.execute(
                    f"UPDATE estado_email SET {columna_estado} = %s WHERE {columna_ref_email} = %s",
                    (id_estado, registro["email"]),
                )
            else:
                if columna_ref_empresa and registro.get("id_empresa"):
                    cursor.execute(
                        f"INSERT INTO estado_email ({columna_ref_email}, {columna_ref_empresa}, {columna_estado}) VALUES (%s, %s, %s)",
                        (registro["email"], registro["id_empresa"], id_estado),
                    )
                else:
                    cursor.execute(
                        f"INSERT INTO estado_email ({columna_ref_email}, {columna_estado}) VALUES (%s, %s)",
                        (registro["email"], id_estado),
                    )
            conn.commit()
            return

        if columna_estado and "descripcion" in columnas_estado:
            _asegurar_tabla_email_estado(cursor)
            id_email = registro.get("id_email")
            if not id_email and registro.get("email"):
                cursor.execute(
                    "SELECT id_email FROM email WHERE email = %s LIMIT 1",
                    (registro["email"],),
                )
                fila_id = cursor.fetchone()
                id_email = fila_id.get("id_email") if fila_id else None

            if not id_email:
                raise RuntimeError("No se encontró id_email para actualizar estado.")

            cursor.execute(
                """
                INSERT INTO email_estado (id_email, id_estado)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE id_estado = VALUES(id_estado)
                """,
                (id_email, id_estado),
            )
            conn.commit()
            return

        raise RuntimeError(
            "No se pudo mapear el esquema para guardar el estado de email. "
            f"Columnas email={sorted(columnas_email)} | estado_email={sorted(columnas_estado)}"
        )
    finally:
        cursor.close()
        conn.close()


def obtener_estados_email():
    conn = conectar_db()
    cursor = conn.cursor(dictionary=True)
    resultados = []

    try:
        columnas_email = _obtener_columnas_tabla(cursor, "email")
        columna_estado_en_email = _primera_columna_existente(
            columnas_email, ["id_estado", "id_estado_email", "estado_email", "estado"]
        )
        columnas_estado = _obtener_columnas_tabla(cursor, "estado_email")
        columna_estado = _primera_columna_existente(
            columnas_estado, ["id_estado", "id_estado_email", "estado_email", "estado"]
        )
        columna_ref_id_email = _primera_columna_existente(columnas_estado, ["id_email"])
        columna_ref_email = _primera_columna_existente(columnas_estado, ["email"])

        if columna_estado_en_email:
            cursor.execute(
                f"""
                SELECT em.nombre, e.email, e.{columna_estado_en_email} AS id_estado,
                       COALESCE(ee.descripcion, '') AS descripcion
                FROM email e
                JOIN empresa em ON em.id_empresa = e.id_empresa
                LEFT JOIN estado_email ee ON ee.id_estado = e.{columna_estado_en_email}
                ORDER BY em.nombre, e.email
                """
            )
            for fila in cursor.fetchall():
                id_estado = fila.get("id_estado")
                resultados.append(
                    {
                        "nombre": fila.get("nombre", ""),
                        "email": fila.get("email", ""),
                        "id_estado": id_estado or "",
                        "descripcion": fila.get("descripcion", "")
                        or ESTADOS_DESCRIPCION.get(id_estado, ""),
                    }
                )
            return resultados

        if _tabla_existe(cursor, "email_estado"):
            cursor.execute(
                """
                SELECT em.nombre, e.email, ee.id_estado, COALESCE(es.descripcion, '') AS descripcion
                FROM email_estado ee
                JOIN email e ON e.id_email = ee.id_email
                JOIN empresa em ON em.id_empresa = e.id_empresa
                LEFT JOIN estado_email es ON es.id_estado = ee.id_estado
                ORDER BY em.nombre, e.email
                """
            )
            for fila in cursor.fetchall():
                id_estado = fila.get("id_estado")
                resultados.append(
                    {
                        "nombre": fila.get("nombre", ""),
                        "email": fila.get("email", ""),
                        "id_estado": id_estado or "",
                        "descripcion": fila.get("descripcion", "")
                        or ESTADOS_DESCRIPCION.get(id_estado, ""),
                    }
                )
            return resultados

        if columna_ref_id_email and columna_estado:
            cursor.execute(
                f"""
                SELECT em.nombre, e.email, ee.{columna_estado} AS id_estado
                FROM estado_email ee
                JOIN email e ON e.id_email = ee.{columna_ref_id_email}
                JOIN empresa em ON em.id_empresa = e.id_empresa
                ORDER BY em.nombre, e.email
                """
            )
            for fila in cursor.fetchall():
                id_estado = fila.get("id_estado")
                resultados.append(
                    {
                        "nombre": fila.get("nombre", ""),
                        "email": fila.get("email", ""),
                        "id_estado": id_estado or "",
                        "descripcion": ESTADOS_DESCRIPCION.get(id_estado, ""),
                    }
                )
            return resultados

        if columna_ref_email and columna_estado:
            cursor.execute(
                f"""
                SELECT COALESCE(em.nombre, '') AS nombre, ee.{columna_ref_email} AS email, ee.{columna_estado} AS id_estado
                FROM estado_email ee
                LEFT JOIN email e ON e.email = ee.{columna_ref_email}
                LEFT JOIN empresa em ON em.id_empresa = e.id_empresa
                ORDER BY ee.{columna_ref_email}
                """
            )
            for fila in cursor.fetchall():
                id_estado = fila.get("id_estado")
                resultados.append(
                    {
                        "nombre": fila.get("nombre", ""),
                        "email": fila.get("email", ""),
                        "id_estado": id_estado or "",
                        "descripcion": ESTADOS_DESCRIPCION.get(id_estado, ""),
                    }
                )
            return resultados

        raise RuntimeError(
            "No se pudo mapear el esquema para consultar estados de email. "
            f"Columnas email={sorted(columnas_email)} | estado_email={sorted(columnas_estado)}"
        )
    finally:
        cursor.close()
        conn.close()


# ---------------- EMAIL ----------------
def enviar_email(destinatario, asunto, cuerpo_html):
    msg = EmailMessage()
    msg["From"] = SMTP_USER
    msg["To"] = destinatario
    msg["Subject"] = asunto
    msg.set_content("Tu cliente de email no soporta HTML")
    msg.add_alternative(cuerpo_html, subtype="html")

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)


def limpiar_valor(valor, fallback):
    if not valor:
        return fallback
    valor_str = str(valor).strip().lower()
    if valor_str in ("none", "null", "no disponible", ""):
        return fallback
    return str(valor).strip()


def generar_saludo(nombre_empresa):
    nombre_limpio = limpiar_valor(nombre_empresa, "")
    if not nombre_limpio:
        return "Estimado equipo,"
    return f"Estimado equipo de {nombre_limpio},"


# ---------------- GUI ----------------
def lanzar_gui():
    root = tk.Tk()
    root.title("Consultor de Empresas")
    root.geometry("700x500")

    empresas = []
    emails_actuales = []
    emails_reales = []
    emails_posibles = []

    frame = ttk.Frame(root, padding=10)
    frame.pack(fill="both", expand=True)

    notebook = ttk.Notebook(frame)
    notebook.pack(fill="both", expand=True, pady=10)

    # --- Pestana Emails ---
    tab_emails = ttk.Frame(notebook)
    notebook.add(tab_emails, text="Empresas con Email")

    listbox_emails_tab = tk.Listbox(tab_emails, height=20)
    listbox_emails_tab.pack(fill="both", expand=True, padx=5, pady=5)

    # --- Pestana Telefonos ---
    tab_telefonos = ttk.Frame(notebook)
    notebook.add(tab_telefonos, text="Empresas con Telefono")

    listbox_telefonos_tab = tk.Listbox(tab_telefonos, height=20)
    listbox_telefonos_tab.pack(fill="both", expand=True, padx=5, pady=5)

    # --- Pestana Estado Emails ---
    tab_estado_emails = ttk.Frame(notebook)
    notebook.add(tab_estado_emails, text="Estado Emails")

    listbox_estado_emails_tab = tk.Listbox(tab_estado_emails, height=20)
    listbox_estado_emails_tab.pack(fill="both", expand=True, padx=5, pady=5)

    def cargar_empresas():
        nonlocal empresas, emails_actuales, emails_reales, emails_posibles
        empresas = obtener_empresas()
        emails_actuales = []
        emails_reales = []
        emails_posibles = []

        listbox_emails_tab.delete(0, tk.END)

        conn = conectar_db()
        cursor = conn.cursor(dictionary=True)

        ids = [e["id_empresa"] for e in empresas]
        if ids:
            formato = ",".join(["%s"] * len(ids))
            cursor.execute(
                f"""
                SELECT DISTINCT em.id_empresa, e.id_email, e.id_tipo_email, em.nombre, e.email,
                                b.tipo_empresa, b.localidad
                FROM empresa em
                JOIN email e ON em.id_empresa = e.id_empresa
                LEFT JOIN busqueda_empresa be ON em.id_empresa = be.id_empresa
                LEFT JOIN busqueda b ON be.id_busqueda = b.id_busqueda
                WHERE em.id_empresa IN ({formato})
                  AND LOWER(TRIM(e.email)) NOT IN ('no disponible', '', 'none', 'null')
                ORDER BY em.nombre, e.id_tipo_email, e.email
            """,
                ids,
            )
            emails_actuales = cursor.fetchall()

        cursor.close()
        conn.close()

        # Separar emails reales (RE) y posibles (IN/CO/AD).
        for e in emails_actuales:
            tipo = (e.get("id_tipo_email") or "").strip().upper()
            if tipo == "RE":
                emails_reales.append(e)
            elif tipo in ("IN", "CO", "AD"):
                emails_posibles.append(e)

        # En la pestaña principal solo mostramos los reales (RE).
        for e in emails_reales:
            listbox_emails_tab.insert(tk.END, f"{e['nombre']} | {e['email']}")

    def abrir_envio_email():
        if not emails_reales and not emails_posibles:
            messagebox.showwarning("Aviso", "Primero consulta los emails")
            return

        win = tk.Toplevel(root)
        win.title("Enviar Email")
        win.geometry("700x700")
        win.minsize(650, 650)

        ttk.Label(win, text="Destinatarios:").pack(anchor="w", padx=10)
        notebook_envio = ttk.Notebook(win)
        notebook_envio.pack(fill="x", padx=10)

        tab_reales = ttk.Frame(notebook_envio)
        notebook_envio.add(tab_reales, text="Reales (RE)")

        tab_posibles = ttk.Frame(notebook_envio)
        notebook_envio.add(tab_posibles, text="Posibles (IN/CO/AD)")

        listbox_emails_reales = tk.Listbox(tab_reales, selectmode=tk.MULTIPLE, height=8)
        listbox_emails_reales.pack(fill="x")
        for e in emails_reales:
            listbox_emails_reales.insert(tk.END, f"{e['nombre']} | {e['email']}")

        frame_sel_reales = ttk.Frame(tab_reales)
        frame_sel_reales.pack(anchor="w", pady=(6, 0))

        def seleccionar_todos_reales():
            if listbox_emails_reales.size() > 0:
                listbox_emails_reales.selection_set(0, tk.END)

        def deseleccionar_todos_reales():
            listbox_emails_reales.selection_clear(0, tk.END)

        ttk.Button(
            frame_sel_reales, text="Seleccionar todas", command=seleccionar_todos_reales
        ).pack(side="left")
        ttk.Button(
            frame_sel_reales,
            text="Deseleccionar todas",
            command=deseleccionar_todos_reales,
        ).pack(side="left", padx=(8, 0))

        listbox_emails_posibles = tk.Listbox(
            tab_posibles, selectmode=tk.MULTIPLE, height=8
        )
        listbox_emails_posibles.pack(fill="x")
        for e in emails_posibles:
            tipo = (e.get("id_tipo_email") or "").strip().upper()
            listbox_emails_posibles.insert(
                tk.END, f"{e['nombre']} | {e['email']} | {tipo}"
            )

        frame_sel_posibles = ttk.Frame(tab_posibles)
        frame_sel_posibles.pack(anchor="w", pady=(6, 0))

        def seleccionar_todos_posibles():
            if listbox_emails_posibles.size() > 0:
                listbox_emails_posibles.selection_set(0, tk.END)

        def deseleccionar_todos_posibles():
            listbox_emails_posibles.selection_clear(0, tk.END)

        ttk.Button(
            frame_sel_posibles,
            text="Seleccionar todas",
            command=seleccionar_todos_posibles,
        ).pack(side="left")
        ttk.Button(
            frame_sel_posibles,
            text="Deseleccionar todas",
            command=deseleccionar_todos_posibles,
        ).pack(side="left", padx=(8, 0))

        ttk.Label(win, text="Asunto:").pack(anchor="w", padx=10, pady=(10, 0))
        entry_asunto = ttk.Entry(win)
        entry_asunto.insert(0, "Contacto JMOrdenadores")
        entry_asunto.pack(fill="x", padx=10)

        ttk.Label(win, text="Mensaje HTML:").pack(anchor="w", padx=10, pady=(10, 0))
        text_cuerpo = tk.Text(win, height=15)
        text_cuerpo.insert("1.0", PLANTILLA_EMAIL)
        text_cuerpo.pack(fill="both", expand=True, padx=10, pady=5)

        def enviar_emails():
            seleccion_reales = listbox_emails_reales.curselection()
            seleccion_posibles = listbox_emails_posibles.curselection()
            if not seleccion_reales and not seleccion_posibles:
                messagebox.showwarning("Aviso", "Selecciona al menos un email")
                return

            asunto = entry_asunto.get().strip()
            cuerpo_base = text_cuerpo.get("1.0", tk.END)
            errores = []

            seleccionados = []
            for i in seleccion_reales:
                seleccionados.append(emails_reales[i])
            for i in seleccion_posibles:
                seleccionados.append(emails_posibles[i])

            # Evitar duplicados por id_email/email.
            unicos = []
            vistos = set()
            for r in seleccionados:
                clave = r.get("id_email") or r.get("email")
                if clave in vistos:
                    continue
                vistos.add(clave)
                unicos.append(r)

            for registro in unicos:
                email = registro["email"]
                nombre_empresa = limpiar_valor(registro.get("nombre"), "")
                tipo_empresa = limpiar_valor(registro.get("tipo_empresa"), "empresa")
                localidad = limpiar_valor(registro.get("localidad"), "su zona")
                saludo = generar_saludo(nombre_empresa)

                try:
                    try:
                        actualizar_estado_email(registro, "PE")
                    except Exception as exc_estado_pe:
                        errores.append(
                            f"{email}: no se pudo marcar estado PE ({exc_estado_pe})"
                        )

                    cuerpo_personalizado = cuerpo_base.format(
                        empresa=nombre_empresa,
                        tipo_empresa=tipo_empresa,
                        localidad=localidad,
                        saludo=saludo,
                    )
                    enviar_email(email, asunto, cuerpo_personalizado)
                    try:
                        actualizar_estado_email(registro, "EN")
                    except Exception as exc_estado_en:
                        errores.append(
                            f"{email}: email enviado, pero no se pudo marcar EN ({exc_estado_en})"
                        )
                except Exception as exc:
                    try:
                        actualizar_estado_email(registro, "ER")
                    except Exception as exc_estado_er:
                        errores.append(
                            f"{email}: error de envio y no se pudo marcar ER ({exc_estado_er})"
                        )
                    errores.append(f"{email}: {exc}")

            if errores:
                messagebox.showerror("Errores", "\n".join(errores))
            else:
                messagebox.showinfo("OK", "Emails enviados correctamente")
                win.destroy()

        ttk.Button(win, text="Enviar emails", command=enviar_emails).pack(pady=10)

    def cargar_telefonos():
        listbox_telefonos_tab.delete(0, tk.END)
        conn = conectar_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id_empresa, nombre, telefono
            FROM empresa
            WHERE telefono IS NOT NULL AND telefono != ''
            ORDER BY nombre
        """
        )
        telefonos = cursor.fetchall()
        cursor.close()
        conn.close()

        for t in telefonos:
            listbox_telefonos_tab.insert(tk.END, f"{t['nombre']} | {t['telefono']}")

    def cargar_estado_emails():
        listbox_estado_emails_tab.delete(0, tk.END)
        try:
            estados = obtener_estados_email()
        except Exception as exc:
            messagebox.showerror("Error", f"No se pudieron consultar los estados: {exc}")
            return

        if not estados:
            listbox_estado_emails_tab.insert(tk.END, "No hay estados registrados.")
            return

        for estado in estados:
            nombre = estado.get("nombre", "")
            email = estado.get("email", "")
            id_estado = estado.get("id_estado", "")
            descripcion = estado.get("descripcion", "")
            listbox_estado_emails_tab.insert(
                tk.END, f"{nombre} | {email} | {id_estado} - {descripcion}"
            )

    ttk.Button(frame, text="Cargar empresas con email", command=cargar_empresas).pack(pady=5)
    ttk.Button(tab_emails, text="Enviar email", command=abrir_envio_email).pack(pady=5)
    ttk.Button(tab_telefonos, text="Cargar telefonos", command=cargar_telefonos).pack(pady=5)
    ttk.Button(
        tab_estado_emails, text="Consultar estados de email", command=cargar_estado_emails
    ).pack(pady=5)

    root.mainloop()


if __name__ == "__main__":
    lanzar_gui()
