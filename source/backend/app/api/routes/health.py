from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text

from app.api.deps import SessionDep
from app.core.config import settings
from app.mail import transport as mail

router = APIRouter(tags=["system"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def ready(session: SessionDep) -> dict[str, str]:
    await session.execute(text("SELECT 1"))
    _assert_mail_ready()
    return {"status": "ready"}


def _assert_mail_ready() -> None:
    """Пошта поза `local` мусить бути справжньою.

    Прод без `MAIL_SMTP_HOST` чи `MAIL_SENDER` тепер не стартує взагалі
    (`Settings._production_mail_is_configured`), тож перша лінія — це
    падіння на старті. Ця перевірка потрібна для другої: staging такого
    гейта не має, а тиха відмова відновлення пароля — саме той дефект,
    що знаходиться найпізніше, бо ніхто не скаржиться на лист, якого не
    чекав.

    Готовність, а не `/health`: процес живий і решту роботи виконує, тож
    перезапускати його немає сенсу — балансувальник має лише не слати
    сюди новий трафік, поки конфігурацію не виправлено.
    """
    if settings.app_env == "local":
        return
    if mail.build_mailer().available():
        return
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={"reason": "mail.unconfigured"},
    )
