import traceback
from telegram.ext import Application
from bot import BOT_TOKEN

try:
    print("Testing builder...")
    app = Application.builder().token(BOT_TOKEN).build()
    print("Builder success")
except Exception as e:
    print(f"Exception Type: {type(e).__name__}")
    print(f"Exception Message: {e}")
    traceback.print_exc()
