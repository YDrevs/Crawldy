"use client";

/**
 * Зміна пароля в кабінеті.
 *
 * Живе в меню акаунта, а не окремим розділом навігації: розділів пʼять,
 * вони вміщаються сіткою на вузькому екрані, і шостий зламав би саме те
 * компонування, яке робить смугу читабельною. Зміна пароля — дія
 * рідкісна, її місце поруч із мовою й виходом.
 *
 * **Поточний пароль обовʼязковий навіть тут.** Людина вже автентифікована,
 * і спокуса не питати велика — але вкрадена сесія тоді перетворюється на
 * вкрадений акаунт: той, хто дістався чужої відкритої вкладки, міняв би
 * пароль і забирав акаунт назовсім.
 *
 * **Після успіху сесій не лишається жодної — включно з цією.** Це не
 * побічний ефект, а зміст дії: пароль міняють саме тоді, коли підозрюють,
 * що ним користується хтось іще. Тому екран не вдає, ніби нічого не
 * сталося: він веде на форму входу й каже, що сталося.
 */

import { useState } from "react";

import { Alert, Button, Dialog, Input } from "./primitives";
import { ApiError, changePassword } from "../lib/api";
import { useLocale } from "../lib/locale";
import { MIN_PASSWORD_LENGTH } from "../lib/password-policy";
import { problemKey } from "../lib/problem";

export function ChangePasswordDialog({
  open,
  onClose,
  onChanged,
}: {
  open: boolean;
  onClose: () => void;
  /** Успіх. Викликач гасить сесію й веде на форму входу. */
  onChanged: () => void;
}) {
  const { t } = useLocale();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [repeat, setRepeat] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  function close() {
    // Поля не переживають закриття: введений пароль не має лежати в
    // памʼяті вкладки довше, ніж триває сама дія.
    setCurrent("");
    setNext("");
    setRepeat("");
    setError("");
    onClose();
  }

  /** Валідація застосунку — ключ каталогу або null, коли все гаразд. */
  function invalidKey(): string | null {
    if (!current) return "auth.passwordRequired";
    if (next.length < MIN_PASSWORD_LENGTH) return "auth.passwordHint";
    if (next !== repeat) return "recovery.mismatch";
    return null;
  }

  async function submit() {
    const invalid = invalidKey();
    if (invalid) {
      setError(invalid);
      return;
    }
    setBusy(true);
    setError("");
    try {
      await changePassword(current, next);
      onChanged();
    } catch (caught) {
      // 403 тут означає рівно одне — поточний пароль не збігся, і це
      // окреме речення, а не загальне «щось пішло не так»: людина
      // мусить знати, яке саме поле переписати.
      setError(
        caught instanceof ApiError && caught.status === 403
          ? "password.wrongCurrent"
          : problemKey(caught, { 422: "auth.passwordHint" }),
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog
      open={open}
      onClose={close}
      title={t("password.change")}
      footer={
        <>
          <Button variant="quiet" onClick={close}>
            {t("action.cancel")}
          </Button>
          <Button loading={busy} onClick={() => void submit()}>
            {t("password.change")}
          </Button>
        </>
      }
    >
      <form
        className="flex flex-col gap-4"
        noValidate
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
      >
        <Input
          label={t("password.current")}
          type="password"
          autoComplete="current-password"
          value={current}
          onChange={(event) => setCurrent(event.target.value)}
        />
        <Input
          label={t("recovery.newPassword")}
          type="password"
          autoComplete="new-password"
          hint={t("auth.passwordHint")}
          value={next}
          onChange={(event) => setNext(event.target.value)}
        />
        <Input
          label={t("recovery.repeatPassword")}
          type="password"
          autoComplete="new-password"
          value={repeat}
          onChange={(event) => setRepeat(event.target.value)}
        />
        {error ? <Alert tone="danger">{t(error)}</Alert> : null}
        <p className="text-xs text-muted">{t("password.signsYouOut")}</p>
        {/* Кнопка форми потрібна, щоб Enter у полі надсилав її так само,
            як натискання в підвалі діалогу. Візуально вона зайва, тож
            прихована від ока й від фокуса, а не видалена. */}
        <button type="submit" className="hidden" tabIndex={-1} aria-hidden />
      </form>
    </Dialog>
  );
}
