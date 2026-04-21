import time
import threading
import random
import os
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import requests
import asyncio

# ==================== KONFIGURACIJA ====================
TELEGRAM_TOKEN = "7164805897:AAF0tZhF5GagG5LL-Mzv_y52KfQP-hN8nTQ"
CHAT_ID = "5545672150"

# Žaidimo URL
MAIN_URL = "https://mafija.draugas.lt/"
GAME_URL = "https://mafija.draugas.lt/map/-8~7?z=Lxg"

# Prisijungimo duomenys
USERNAME = "PrinceOfEurope"
PASSWORD = "200203"

# ==================== GLOBALS ====================
class BotState:
    def __init__(self):
        self.clicking = False
        self.click_count = 0
        self.jail_count = 0
        self.hospital_count = 0
        self.start_time = None
        self.driver = None
        self.bot_thread = None
        self.stop_event = threading.Event()
        self.atm_hack_allowed = True
        self.paused = False
        self.stop_time = None  # Kada sustoti

state = BotState()

# ==================== PAGALBINĖS FUNKCIJOS ====================
def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)

def send_telegram_message(message, reply_markup=None):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
        if reply_markup:
            data["reply_markup"] = reply_markup
        requests.post(url, data=data, timeout=5)
    except Exception as e:
        log(f"Klaida siunčiant Telegram: {e}")

def pause_short():
    time.sleep(random.uniform(0.005, 0.010))

def pause_long():
    time.sleep(random.uniform(0.005, 0.010))

def wait_present(driver, by, selector, wait=0.2):
    try:
        return WebDriverWait(driver, wait).until(
            EC.presence_of_element_located((by, selector))
        )
    except TimeoutException:
        return None

def action_click(driver, by, selector):
    try:
        el = wait_present(driver, by, selector)
        if not el:
            return False
        ac = ActionChains(driver)
        ac.move_to_element(el).pause(0.01).click().perform()
        pause_long()
        return True
    except (StaleElementReferenceException, Exception):
        return False

# ==================== PRISIJUNGIMAS ====================
def is_logged_in(driver):
    try:
        game_elements = driver.find_elements(By.CSS_SELECTOR, ".map, #map, a.east, a.beat")
        if game_elements:
            return True
        login_form = driver.find_elements(By.NAME, "login[usr]")
        if not login_form:
            return True
        return False
    except:
        return False

def auto_login(driver):
    log("🔐 Pradedamas automatinis prisijungimas...")
    
    try:
        driver.get(MAIN_URL)
        log(f"🌐 Atidarytas: {MAIN_URL}")
        time.sleep(3)
        
        if is_logged_in(driver):
            log("✅ Jau prisijungęs!")
            send_telegram_message(f"✅ <b>Jau prisijungęs!</b>\n👤 {USERNAME}")
            return True
        
        wait = WebDriverWait(driver, 10)
        
        log("📝 Įvedamas vartotojo vardas...")
        username_field = wait.until(EC.presence_of_element_located((By.NAME, "login[usr]")))
        username_field.clear()
        username_field.send_keys(USERNAME)
        
        login_button = driver.find_element(By.CSS_SELECTOR, "input[value='Prisijungti']")
        login_button.click()
        log("✓ Paspausdintas 'Prisijungti' (1)")
        time.sleep(2)
        
        log("📝 Įvedamas slaptažodis...")
        password_field = wait.until(EC.presence_of_element_located((By.NAME, "login[pwd]")))
        password_field.clear()
        password_field.send_keys(PASSWORD)
        
        login_button2 = driver.find_element(By.CSS_SELECTOR, "input[value='Prisijungti']")
        login_button2.click()
        log("✓ Paspausdintas 'Prisijungti' (2)")
        time.sleep(4)
        
        if is_logged_in(driver):
            log("✅ Sėkmingai prisijungta!")
            send_telegram_message(f"✅ <b>Sėkmingai prisijungta!</b>\n👤 {USERNAME}")
            return True
        else:
            log("❌ Nepavyko prisijungti!")
            send_telegram_message("❌ <b>Nepavyko prisijungti!</b>")
            return False
            
    except Exception as e:
        log(f"❌ Klaida: {e}")
        send_telegram_message(f"❌ <b>Klaida!</b>\n{str(e)[:200]}")
        return False

# ==================== KALĖJIMAS / LIGONINĖ ====================
def is_arrested(driver):
    return len(driver.find_elements(By.CSS_SELECTOR, "a.ustat-arrested")) > 0

def is_in_hospital(driver):
    return len(driver.find_elements(By.CSS_SELECTOR, "a.ustat-warn")) > 0

def handle_jail(driver):
    if action_click(driver, By.CSS_SELECTOR, "input[name='cop[paymax]']"):
        time.sleep(0.5)
        if action_click(driver, By.CSS_SELECTOR, "input.btn.cash"):
            state.jail_count += 1
            log("🚓 Išpirka iš kalėjimo!")
            send_telegram_message(f"🚓 <b>IŠPIRKA IŠ KALĖJIMO!</b> (#{state.jail_count})")
            return True
    return False

def handle_hospital(driver):
    if action_click(driver, By.CSS_SELECTOR, "a.pad_item.hospital_nurse"):
        state.hospital_count += 1
        log("🏥 Gydymas ligoninėje!")
        send_telegram_message(f"🏥 <b>GYDYMAS LIGONINĖJE!</b> (#{state.hospital_count})")
        return True
    return False

def force_leave_hospital(driver):
    log("🏥 Priverstinis išėjimas iš ligoninės...")
    if action_click(driver, By.CSS_SELECTOR, "a.pad_item.hospital_nurse"):
        send_telegram_message("✅ <b>Išėjimas iš ligoninės atliktas!</b>")
        return True
    send_telegram_message("⚠️ Nepavyko išeiti iš ligoninės")
    return False

def handle_jail_or_hospital(driver):
    if is_arrested(driver):
        if handle_jail(driver):
            return "RESTART"
    if is_in_hospital(driver):
        if handle_hospital(driver):
            return "RESTART"
    return None

# ==================== VEIKSMŲ FUNKCIJOS ====================
def click_east_once(driver):
    if action_click(driver, By.CSS_SELECTOR, "a.east"):
        log("➡️ EAST")
        pause_short()
        return True
    return False

def drink_coffee(driver):
    log("⚡ Kavos gėrimas...")
    if action_click(driver, By.CSS_SELECTOR, "a.spot.cofemachine"):
        pause_short()
        for sel in [
            "//a[contains(@onclick,'drink-cafe/10')]",
            "//a[contains(@onclick,'drink-cafe')]"
        ]:
            if action_click(driver, By.XPATH, sel):
                log("✓ Išgerta kavos!")
                return True
    return False

def refresh_page(driver):
    log("🔄 Atnaujinamas puslapis...")
    driver.refresh()
    time.sleep(2)
    send_telegram_message("🔄 <b>Puslapis atnaujintas!</b>")
    return True

def safe_spot_action(driver, spot, action, name):
    if handle_jail_or_hospital(driver):
        return "RESTART"
    
    if not wait_present(driver, By.CSS_SELECTOR, spot):
        click_east_once(driver)
        return False
    
    action_click(driver, By.CSS_SELECTOR, spot)
    pause_short()
    ok = action_click(driver, By.XPATH, action)
    pause_short()
    
    if handle_jail_or_hospital(driver):
        return "RESTART"
    
    return ok

def skip_current_action(driver):
    log("⏭️ Praleidžiamas veiksmas...")
    send_telegram_message("⏭️ <b>Dabartinis veiksmas praleistas!</b>")
    return True

# ==================== PAGRINDINIS CIKLAS ====================
def run_cycle(driver):
    if state.paused:
        time.sleep(1)
        return
    
    log("=" * 40)
    log("🔄 CIKLAS PRADEDAMAS")
    
    # ATM BREAK
    r = safe_spot_action(driver, "a.spot.atm",
                         "//a[contains(@onclick,'atm.crash')]", "ATM Break")
    if r == "RESTART": return
    
    # ATM HACK
    if state.atm_hack_allowed:
        r = safe_spot_action(driver, "a.spot.atm",
                             "//a[contains(@onclick,'atm.hack')]", "ATM Hack")
        if r == "RESTART": return
    
    # Kavos
    drink_coffee(driver)
    
    # Businessman veiksmai
    for spot, act in [
        ("a.spot.businessman", "//a[contains(@onclick,'businessman.advice')]"),
        ("a.spot.businessman", "//a[contains(@onclick,'businessman.rob')]"),
        ("a.spot.businessman", "//a[contains(@onclick,'businessman.change')]"),
    ]:
        r = safe_spot_action(driver, spot, act, "BM")
        if r == "RESTART": return
    
    # Kavos
    drink_coffee(driver)
    
    # Daugiau businessman veiksmų
    for spot, act in [
        ("a.spot.businessman", "//a[contains(@onclick,'businessman.beat')]"),
        ("a.spot.businessman", "//a[contains(@onclick,'businessman.blackmail')]"),
    ]:
        r = safe_spot_action(driver, spot, act, "BM")
        if r == "RESTART": return
    
    # East judėjimas
    click_east_once(driver)
    
    state.click_count += 1
    log(f"✅ CIKLAS BAIGTAS (Iš viso: {state.click_count})")

def check_stop_time():
    """Tikrina ar atėjo laikas sustoti"""
    if state.stop_time and datetime.now() >= state.stop_time:
        log("⏰ Laikas baigėsi! Botas sustabdomas automatiškai.")
        send_telegram_message(f"⏰ <b>LAIKAS BAIGĖSI!</b>\nBotas veikė {state.click_count} ciklų.\n🚓 Kalėjimų: {state.jail_count}\n🏥 Ligoninių: {state.hospital_count}")
        state.clicking = False
        state.stop_event.set()
        if state.driver:
            try:
                state.driver.quit()
            except:
                pass
        return True
    return False

def run_mafija_bot():
    options = webdriver.ChromeOptions()
    
    # ============ VPS NUSTATYMAI (HEADLESS) ============
    options.add_argument("--headless=new")  # NEMATOMAS REŽIMAS - BŪTINA VPS
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-notifications")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    
    try:
        driver = webdriver.Chrome(options=options)
        state.driver = driver
        
        if not auto_login(driver):
            log("❌ Nepavyko prisijungti!")
            send_telegram_message("❌ <b>Botas sustabdytas!</b> Nepavyko prisijungti.")
            state.clicking = False
            return
        
        driver.get(GAME_URL)
        time.sleep(3)
        
        log("✅ Botas paruoštas VPS!")
        send_telegram_message(f"✅ <b>Botas paleistas VPS!</b>\n👤 {USERNAME}\n🔄 Pradedami veiksmai...")
        
        last_report = time.time()
        
        while not state.stop_event.is_set():
            try:
                # Tikriname ar laikas baigėsi
                if check_stop_time():
                    break
                
                if not state.paused:
                    run_cycle(driver)
                
                # Ataskaita kas 30 sek
                if time.time() - last_report > 30 and not state.paused:
                    duration = datetime.now() - state.start_time if state.start_time else 0
                    if state.stop_time:
                        time_left = state.stop_time - datetime.now()
                        time_left_str = str(time_left).split('.')[0] if time_left.total_seconds() > 0 else "Baigiasi"
                    else:
                        time_left_str = "Nenustatytas"
                    
                    send_telegram_message(
                        f"📊 <b>Ataskaita</b>\n"
                        f"🔄 Ciklų: {state.click_count}\n"
                        f"🚓 Kalėjimų: {state.jail_count}\n"
                        f"🏥 Ligoninių: {state.hospital_count}\n"
                        f"⏱️ Veikia: {str(duration).split('.')[0]}\n"
                        f"⏰ Liko: {time_left_str}"
                    )
                    last_report = time.time()
                
                time.sleep(0.25)
                
            except Exception as e:
                log(f"Klaida cikle: {e}")
                time.sleep(2)
                
    except Exception as e:
        log(f"Fatal error: {e}")
        send_telegram_message(f"❌ <b>BOTAS SUSTRADO!</b>\n{e}")
    finally:
        if state.driver:
            try:
                state.driver.quit()
            except:
                pass

# ==================== TELEGRAM MYGTUKAI ====================
def get_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("🟢 START", callback_data="start"),
         InlineKeyboardButton("🔴 STOP", callback_data="stop")],
        [InlineKeyboardButton("⏸️ PAUSE", callback_data="pause"),
         InlineKeyboardButton("▶️ RESUME", callback_data="resume")],
        [InlineKeyboardButton("⏰ 30 MIN", callback_data="time_30"),
         InlineKeyboardButton("⏰ 1 H", callback_data="time_1h"),
         InlineKeyboardButton("⏰ 2 H", callback_data="time_2h")],
        [InlineKeyboardButton("⏰ 4 H", callback_data="time_4h"),
         InlineKeyboardButton("⏰ 8 H", callback_data="time_8h"),
         InlineKeyboardButton("⏰ 12 H", callback_data="time_12h")],
        [InlineKeyboardButton("⏰ 24 H", callback_data="time_24h"),
         InlineKeyboardButton("❌ IŠJUNGTI LAIKĄ", callback_data="time_off")],
        [InlineKeyboardButton("📊 STATUS", callback_data="status"),
         InlineKeyboardButton("📈 STATS", callback_data="stats")],
        [InlineKeyboardButton("☕ ENERGY", callback_data="coffee"),
         InlineKeyboardButton("🏥 LEAVE HOSPITAL", callback_data="leave_hospital")],
        [InlineKeyboardButton("🔄 REFRESH", callback_data="refresh"),
         InlineKeyboardButton("⏭️ SKIP", callback_data="skip")],
        [InlineKeyboardButton("🗺️ GO TO ZONE", callback_data="goto_zone"),
         InlineKeyboardButton("🔐 RE-LOGIN", callback_data="relogin")],
        [InlineKeyboardButton("❓ HELP", callback_data="help")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ==================== TELEGRAM KOMANDOS ====================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if state.clicking:
        await update.message.reply_text("⚠️ Botas jau veikia!", reply_markup=get_main_keyboard())
        return
    
    await update.message.reply_text(
        f"🚀 <b>Paleidžiamas Mafija Botas VPS...</b>\n\n"
        f"👤 {USERNAME}\n"
        f"🔐 Prisijungiama...\n"
        f"⏳ ~15 sek.\n\n"
        f"💡 <b>Nustatykite veikimo laiką mygtukais!</b>",
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )
    
    state.clicking = True
    state.paused = False
    state.stop_event.clear()
    state.click_count = 0
    state.jail_count = 0
    state.hospital_count = 0
    state.start_time = datetime.now()
    state.atm_hack_allowed = True
    state.stop_time = None
    
    state.bot_thread = threading.Thread(target=run_mafija_bot, daemon=True)
    state.bot_thread.start()

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not state.clicking:
        await update.message.reply_text("⚠️ Botas neveikia!", reply_markup=get_main_keyboard())
        return
    
    state.clicking = False
    state.paused = False
    state.stop_event.set()
    
    if state.driver:
        try:
            state.driver.quit()
        except:
            pass
    
    duration = datetime.now() - state.start_time if state.start_time else 0
    await update.message.reply_text(
        f"⏹️ <b>Botas sustabdytas!</b>\n\n"
        f"📊 <b>Statistika:</b>\n"
        f"🔄 Ciklų: {state.click_count}\n"
        f"🚓 Kalėjimų: {state.jail_count}\n"
        f"🏥 Ligoninių: {state.hospital_count}\n"
        f"⏱️ Veikė: {str(duration).split('.')[0]}",
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )

async def pause_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not state.clicking:
        await update.message.reply_text("⚠️ Botas neveikia!")
        return
    if state.paused:
        await update.message.reply_text("⚠️ Botas jau pristabdytas!")
        return
    
    state.paused = True
    await update.message.reply_text("⏸️ <b>Botas pristabdytas!</b>\nNaudokite /resume tęsimui", parse_mode="HTML", reply_markup=get_main_keyboard())

async def resume_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not state.clicking:
        await update.message.reply_text("⚠️ Botas neveikia!")
        return
    if not state.paused:
        await update.message.reply_text("⚠️ Botas nėra pristabdytas!")
        return
    
    state.paused = False
    await update.message.reply_text("▶️ <b>Botas tęsia darbą!</b>", parse_mode="HTML", reply_markup=get_main_keyboard())

async def set_time_command(update: Update, context: ContextTypes.DEFAULT_TYPE, hours=0, minutes=0):
    if not state.clicking:
        await update.message.reply_text("⚠️ Botas neveikia! Pirmiausia paleiskite /start")
        return
    
    duration = timedelta(hours=hours, minutes=minutes)
    state.stop_time = datetime.now() + duration
    
    if hours > 0:
        time_str = f"{hours} valandų"
    else:
        time_str = f"{minutes} minučių"
    
    await update.message.reply_text(
        f"⏰ <b>Laikmatis nustatytas!</b>\n"
        f"Botas veiks {time_str}\n"
        f"Sustos: {state.stop_time.strftime('%H:%M:%S')}",
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )

async def time_30_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await set_time_command(update, context, minutes=30)

async def time_1h_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await set_time_command(update, context, hours=1)

async def time_2h_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await set_time_command(update, context, hours=2)

async def time_4h_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await set_time_command(update, context, hours=4)

async def time_8h_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await set_time_command(update, context, hours=8)

async def time_12h_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await set_time_command(update, context, hours=12)

async def time_24h_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await set_time_command(update, context, hours=24)

async def time_off_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state.stop_time = None
    await update.message.reply_text("❌ <b>Laikmatis išjungtas!</b>\nBotas veiks kol patys sustabdysite.", parse_mode="HTML", reply_markup=get_main_keyboard())

async def coffee_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not state.driver:
        await update.message.reply_text("⚠️ Botas neveikia!")
        return
    
    await update.message.reply_text("☕ <b>Geriama kava...</b>", parse_mode="HTML")
    drink_coffee(state.driver)

async def leave_hospital_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not state.driver:
        await update.message.reply_text("⚠️ Botas neveikia!")
        return
    
    await update.message.reply_text("🏥 <b>Bandoma išeiti iš ligoninės...</b>", parse_mode="HTML")
    force_leave_hospital(state.driver)

async def refresh_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not state.driver:
        await update.message.reply_text("⚠️ Botas neveikia!")
        return
    
    await update.message.reply_text("🔄 <b>Atnaujinamas puslapis...</b>", parse_mode="HTML")
    refresh_page(state.driver)

async def skip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not state.driver:
        await update.message.reply_text("⚠️ Botas neveikia!")
        return
    
    skip_current_action(state.driver)

async def goto_zone_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not state.driver:
        await update.message.reply_text("⚠️ Botas neveikia!")
        return
    
    await update.message.reply_text("🗺️ <b>Einama į žaidimo zoną...</b>", parse_mode="HTML")
    state.driver.get(GAME_URL)
    time.sleep(2)

async def relogin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not state.driver:
        await update.message.reply_text("⚠️ Botas neveikia!")
        return
    
    await update.message.reply_text("🔄 <b>Prisijungiama iš naujo...</b>", parse_mode="HTML")
    auto_login(state.driver)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = "🟢 VEIKIA" if state.clicking and not state.paused else "⏸️ PRISTABDYTA" if state.paused else "🔴 SUSTABDYTA"
    duration = datetime.now() - state.start_time if state.start_time and state.clicking else 0
    
    time_left = ""
    if state.stop_time:
        remaining = state.stop_time - datetime.now()
        if remaining.total_seconds() > 0:
            time_left = f"\n⏰ Liko: {str(remaining).split('.')[0]}"
        else:
            time_left = f"\n⏰ Liko: BAIGIASI"
    else:
        time_left = "\n⏰ Liko: Neribota"
    
    msg = (
        f"<b>🤖 BOTO BŪSENA</b>\n\n"
        f"📌 Statusas: {status}\n"
        f"🔄 Ciklų: {state.click_count}\n"
        f"🚓 Kalėjimų: {state.jail_count}\n"
        f"🏥 Ligoninių: {state.hospital_count}\n"
        f"⏱️ Veikia: {str(duration).split('.')[0] if duration else 'N/A'}{time_left}\n"
        f"👤 Vartotojas: {USERNAME}\n"
        f"🖥️ Platforma: VPS (Headless)"
    )
    
    await update.message.reply_text(msg, parse_mode="HTML", reply_markup=get_main_keyboard())

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    screenshot_path = None
    if state.driver and state.clicking:
        try:
            screenshot_path = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            state.driver.save_screenshot(screenshot_path)
        except:
            pass
    
    msg = (
        f"📊 <b>DETALI STATISTIKA</b>\n\n"
        f"🔄 Ciklų: <code>{state.click_count}</code>\n"
        f"🚓 Kalėjimų: <code>{state.jail_count}</code>\n"
        f"🏥 Ligoninių: <code>{state.hospital_count}</code>\n"
        f"👤 Vartotojas: <code>{USERNAME}</code>\n"
        f"📅 Paleista: <code>{state.start_time.strftime('%Y-%m-%d %H:%M:%S') if state.start_time else 'N/A'}</code>\n"
        f"🖥️ Platforma: <code>VPS (Headless)</code>"
    )
    
    await update.message.reply_text(msg, parse_mode="HTML")
    
    if screenshot_path and os.path.exists(screenshot_path):
        await update.message.reply_photo(photo=open(screenshot_path, 'rb'))
        os.remove(screenshot_path)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📖 <b>MAFIJA BOT VPS - PAGRALBA</b>\n\n"
        "<b>🤖 Pagrindinės komandos:</b>\n"
        "/start - Paleisti botą\n"
        "/stop - Sustabdyti botą\n"
        "/pause - Pristabdyti\n"
        "/resume - Tęsti\n\n"
        "<b>⏰ Laiko valdymas (mygtukais):</b>\n"
        "• 30 min, 1h, 2h, 4h, 8h, 12h, 24h\n"
        "• Išjungti laikmatį\n\n"
        "<b>⚡ Veiksmų komandos:</b>\n"
        "/coffee - Gerti kavą (energija)\n"
        "/leave_hospital - Išeiti iš ligoninės\n"
        "/refresh - Atnaujinti puslapį\n"
        "/skip - Praleisti veiksmą\n"
        "/goto_zone - Eiti į žaidimo zoną\n"
        "/relogin - Prisijungti iš naujo\n\n"
        "<b>📊 Informacijos komandos:</b>\n"
        "/status - Dabartinė būsena\n"
        "/stats - Išsami statistika + screenshot\n"
        "/help - Ši žinutė\n\n"
        "<b>🔄 Botas automatiškai atlieka:</b>\n"
        "• ATM Break / Hack\n"
        "• Businessman (advice, rob, change, beat, blackmail)\n"
        "• Kavos gėrimas energijai\n"
        "• East judėjimas\n"
        "• Išpirka iš kalėjimo\n"
        "• Gydymas ligoninėje\n\n"
        f"<b>🖥️ Veikia VPS (Headless) - 24/7</b>\n"
        f"👤 Vartotojas: {USERNAME}"
    )
    await update.message.reply_text(help_text, parse_mode="HTML", reply_markup=get_main_keyboard())

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    callback_map = {
        "start": start_command,
        "stop": stop_command,
        "pause": pause_command,
        "resume": resume_command,
        "time_30": time_30_command,
        "time_1h": time_1h_command,
        "time_2h": time_2h_command,
        "time_4h": time_4h_command,
        "time_8h": time_8h_command,
        "time_12h": time_12h_command,
        "time_24h": time_24h_command,
        "time_off": time_off_command,
        "status": status_command,
        "stats": stats_command,
        "coffee": coffee_command,
        "leave_hospital": leave_hospital_command,
        "refresh": refresh_command,
        "skip": skip_command,
        "goto_zone": goto_zone_command,
        "relogin": relogin_command,
        "help": help_command,
    }
    
    if query.data in callback_map:
        await callback_map[query.data](update, context)

# ==================== MAIN ====================
def main():
    print("=" * 60)
    print("🤖 MAFIJA BOT - VPS VERSION SU LAIKO VALDYMU")
    print("=" * 60)
    print(f"👤 Vartotojas: {USERNAME}")
    print(f"🎮 Žaidimas: Mafija")
    print(f"🖥️ Režimas: Headless (VPS)")
    print("=" * 60)
    print("✅ Botas paleistas VPS!")
    print("📱 Telegram komandos:")
    print("   /start - paleisti")
    print("   /stop - sustabdyti")
    print("   /pause - pristabdyti")
    print("   /resume - tęsti")
    print("   /status - būsena")
    print("   /stats - statistika")
    print("   /help - pagalba")
    print("=" * 60)
    print("⏰ LAIKO VALDYMAS:")
    print("   Mygtukais galite nustatyti 30min, 1h, 2h, 4h, 8h, 12h, 24h")
    print("=" * 60)
    
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Komandos
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("pause", pause_command))
    app.add_handler(CommandHandler("resume", resume_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("coffee", coffee_command))
    app.add_handler(CommandHandler("leave_hospital", leave_hospital_command))
    app.add_handler(CommandHandler("refresh", refresh_command))
    app.add_handler(CommandHandler("skip", skip_command))
    app.add_handler(CommandHandler("goto_zone", goto_zone_command))
    app.add_handler(CommandHandler("relogin", relogin_command))
    app.add_handler(CommandHandler("help", help_command))
    
    # Laiko komandos
    app.add_handler(CommandHandler("time_30", time_30_command))
    app.add_handler(CommandHandler("time_1h", time_1h_command))
    app.add_handler(CommandHandler("time_2h", time_2h_command))
    app.add_handler(CommandHandler("time_4h", time_4h_command))
    app.add_handler(CommandHandler("time_8h", time_8h_command))
    app.add_handler(CommandHandler("time_12h", time_12h_command))
    app.add_handler(CommandHandler("time_24h", time_24h_command))
    app.add_handler(CommandHandler("time_off", time_off_command))
    
    # Mygtukų callback
    app.add_handler(CallbackQueryHandler(button_callback))
    
    app.run_polling(allowed_updates=["message", "callback_query"])

if __name__ == "__main__":
    main()