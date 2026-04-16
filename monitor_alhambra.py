import os
import json
import requests
from datetime import datetime
from playwright.sync_api import sync_playwright

# ─── CONFIGURACIÓN ────────────────────────────────────────────
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
TARGET_DATES = ["1 mayo", "2 mayo", "3 mayo",
                "01/05", "02/05", "03/05",
                "2025-05-01", "2025-05-02", "2025-05-03",
                "May 1", "May 2", "May 3"]
URL = "https://tickets.alhambra-patronato.es/producto/alhambra-general/"
PRICE = "22,27"
# ──────────────────────────────────────────────────────────────


def check_availability():
    """Carga la página con un navegador real y busca disponibilidad."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        try:
            page.goto(URL, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(3000)  # espera JS dinámico
            content = page.content().lower()

            found_dates = []
            for date in TARGET_DATES:
                if date.lower() in content:
                    found_dates.append(date)

            # Busca señales positivas de disponibilidad
            availability_signals = [
                "añadir al carrito", "add to cart", "comprar",
                "seleccionar fecha", "disponible", "available",
                "buy now", "book now"
            ]
            has_availability = any(s in content for s in availability_signals)

            # Busca señales negativas (agotado)
            sold_out_signals = [
                "agotado", "sold out", "no disponible",
                "out of stock", "no hay entradas"
            ]
            is_sold_out = any(s in content for s in sold_out_signals)

            browser.close()
            return found_dates, has_availability, is_sold_out, content[:500]

        except Exception as e:
            browser.close()
            raise e


def send_discord_alert(found_dates, has_availability, is_sold_out):
    """Envía notificación a Discord."""
    if not DISCORD_WEBHOOK_URL:
        print("⚠️  DISCORD_WEBHOOK_URL no configurado")
        return

    now = datetime.now().strftime("%d/%m/%Y %H:%M")

    if found_dates and has_availability and not is_sold_out:
        # 🚨 ALERTA POSITIVA — hay entradas
        color = 0x00FF7F  # verde
        title = "🎟️ ¡ENTRADAS DISPONIBLES EN LA ALHAMBRA!"
        description = (
            f"**¡Corre, puede haber entradas para mayo!**\n\n"
            f"📅 Fechas detectadas: `{', '.join(set(found_dates))}`\n"
            f"💶 Precio: {PRICE}€\n\n"
            f"👉 [**COMPRAR AHORA**]({URL})\n\n"
            f"⏱️ Detectado a las: {now}"
        )
    elif is_sold_out:
        # sin interés, no notifica
        print(f"[{now}] Agotado. Sin notificación.")
        return
    else:
        # Estado ambiguo — avisa igualmente por si acaso
        color = 0xFFAA00  # naranja
        title = "⚠️ Alhambra — Cambio detectado en la página"
        description = (
            f"Se detectó un cambio en la página que puede indicar disponibilidad.\n\n"
            f"📅 Referencias a fechas encontradas: `{', '.join(set(found_dates)) if found_dates else 'ninguna'}`\n"
            f"💶 Precio: {PRICE}€\n\n"
            f"👉 [**Ver página**]({URL})\n\n"
            f"⏱️ Detectado a las: {now}"
        )

    payload = {
        "username": "Monitor Alhambra 🏰",
        "avatar_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/30/Alhambra_Palacios_Nazaries.jpg/240px-Alhambra_Palacios_Nazaries.jpg",
        "embeds": [{
            "title": title,
            "description": description,
            "color": color,
            "footer": {"text": "Monitor automático · GitHub Actions"}
        }]
    }

    response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
    if response.status_code in (200, 204):
        print(f"[{now}] ✅ Notificación enviada a Discord.")
    else:
        print(f"[{now}] ❌ Error enviando a Discord: {response.status_code}")


def main():
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    print(f"[{now}] 🔍 Comprobando disponibilidad Alhambra...")

    try:
        found_dates, has_availability, is_sold_out, _ = check_availability()
        print(f"  Fechas encontradas: {found_dates}")
        print(f"  Señal disponibilidad: {has_availability}")
        print(f"  Agotado: {is_sold_out}")

        if found_dates or has_availability:
            send_discord_alert(found_dates, has_availability, is_sold_out)
        else:
            print(f"[{now}] 😴 Sin disponibilidad detectada. Siguiente comprobación en 5 min.")

    except Exception as e:
        print(f"[{now}] ❌ Error: {e}")
        # Notifica el error a Discord para saber que el monitor sigue vivo
        if DISCORD_WEBHOOK_URL:
            payload = {
                "username": "Monitor Alhambra 🏰",
                "embeds": [{
                    "title": "⚙️ Error en el monitor",
                    "description": f"```{str(e)[:300]}```\n⏱️ {now}",
                    "color": 0xFF4444
                }]
            }
            requests.post(DISCORD_WEBHOOK_URL, json=payload)


if __name__ == "__main__":
    # TEST — borrar después
    send_discord_alert(["1 mayo", "2 mayo"], True, False)
    # main()
