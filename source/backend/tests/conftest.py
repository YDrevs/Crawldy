import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Консоль Windows у cp1251 перетворює українські повідомлення assert'ів
# на мотлох — читати провалений тест стає неможливо.
for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        _reconfigure(encoding="utf-8", errors="replace")


# Налаштування платежів фіксуються ДО імпорту застосунку: інакше тести
# читали б `.env` розробника, і зелений набір означав би «на цій машині
# так налаштовано», а не «код такий».
#
# Найгірший варіант тут — не червоний прогін, а тихий: тест, що взяв
# справжній ключ провайдера з `.env` і пішов у мережу за гроші.
_PAYMENT_TEST_ENV = {
    # Оточення теж фіксується. `prod` міняє cookie сесії на префікс
    # `__Host-`, який вимагає HTTPS, — тестовий клієнт ходить по HTTP і
    # такий cookie не збереже, тож автентифікація мовчки ламається, а
    # падають натомість тести сайтів, розкладів і квоти. Одного разу
    # цього вистачило, щоб 134 перевірки почервоніли через рядок у
    # `.env`, поставлений заради тунелю.
    "APP_ENV": "local",
    "BILLING_PROVIDER": "fake",
    "PADDLE_ENV": "sandbox",
    "PADDLE_API_KEY": "",
    "PADDLE_CLIENT_TOKEN": "",
    "PADDLE_WEBHOOK_SECRET": "",
    "PADDLE_FULL_AUDIT_PRICE_ID": "",
}
for _name, _value in _PAYMENT_TEST_ENV.items():
    import os as _os

    _os.environ[_name] = _value
