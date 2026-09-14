import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app.main import app as asgi_app
from app import telegram_bot
from a2wsgi import ASGIMiddleware

telegram_bot.start()  # oddiy thread, event loop kerak emas — shu yerda xavfsiz ishga tushadi

application = ASGIMiddleware(asgi_app)
