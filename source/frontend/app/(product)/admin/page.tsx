"use client";

/**
 * Адміністрування → Ціни.
 *
 * Перший і поки єдиний розділ службової сторінки: суми, кількості й те,
 * чи показувати формат на сторінці цін. Аналітика зʼявиться тут окремим
 * розділом пізніше — тому сторінка побудована як перелік розділів, а не
 * як одна форма.
 *
 * ## Що форма питає, а що знає сама
 *
 * Питає рівно комерційні значення: ціну, валюту, посилання на прайс
 * провайдера, кількість перевірок у пакеті, кількість Actual AI Presence
 * на місяць. Не питає складу пропозицій — він фіксований продуктом:
 * разова це завжди 1 перевірка + 1 Presence, пакет на N перевірок дає
 * N Presence, місячний план необмежений і місячний за означенням. Ціна
 * однієї перевірки в пакеті не вводиться, а обчислюється.
 *
 * ## Порожня ціна — легальний стан
 *
 * Поле можна лишити порожнім: формат тоді стоїть на сторінці цін і
 * чесно каже «ціна за запитом», а рядки складу лишаються на місці.
 * Вигаданих чисел не буває в жодному стані — ані тут, ані там.
 *
 * ## Текст сторінки українською
 *
 * Це інструмент команди, а не клієнтський екран: він не входить у
 * шість мов сайту й не додає ключів до клієнтського каталогу.
 */

import { useCallback, useEffect, useState } from "react";

import {
  Alert,
  Button,
  Field,
  Input,
  Panel,
  Spinner,
} from "../../components/primitives";
import {
  ApiError,
  listAdminOffers,
  listAdminPlans,
  saveAdminOffer,
  saveAdminPlan,
} from "../../lib/api";
import { readCheckoutConfig } from "../../lib/guest-payment";
import {
  MONTHLY_CODE,
  PACK_CODE,
  SINGLE_CODE,
  blankOffer,
  blankPlan,
  fromAmountField,
  monthlyPayload,
  monthlyPresence,
  monthlyPrice,
  packPayload,
  packProblem,
  packUnitPreview,
  singlePayload,
  toAmountField,
} from "../../lib/admin-pricing";
import type { AdminOffer, AdminPlan } from "../../lib/contracts";

const AMOUNT_ERROR: Record<string, string> = {
  not_a_number: "Ціна має бути числом, наприклад 19 або 19.90.",
  negative: "Ціна не буває відʼємною.",
  too_precise: "Забагато знаків після коми для цієї валюти.",
};

export default function AdminPage() {
  const [offers, setOffers] = useState<AdminOffer[] | null>(null);
  const [plans, setPlans] = useState<AdminPlan[] | null>(null);
  // Провайдер один на всі ціни й приходить із конфігурації. Тут він
  // потрібен рівно для нової пропозиції: наявна лишає свій.
  const [provider, setProvider] = useState("");
  const [failed, setFailed] = useState("");

  const load = useCallback(async () => {
    try {
      const [loadedOffers, loadedPlans, config] = await Promise.all([
        listAdminOffers(),
        listAdminPlans(),
        readCheckoutConfig().catch(() => null),
      ]);
      setOffers(loadedOffers);
      setPlans(loadedPlans);
      setProvider(config?.provider ?? "");
      setFailed("");
    } catch (problem) {
      setFailed(
        problem instanceof ApiError && problem.status === 403
          ? "Немає прав команди Crawldy."
          : "Не вдалося прочитати каталог.",
      );
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (failed && offers === null) {
    return <Alert tone="danger">{failed}</Alert>;
  }
  if (offers === null || plans === null) {
    return (
      <div className="flex justify-center py-16 text-muted">
        <Spinner className="size-5" />
      </div>
    );
  }

  const single = offers.find((offer) => offer.code === SINGLE_CODE) ?? blankOffer("single", provider);
  const pack = offers.find((offer) => offer.code === PACK_CODE) ?? blankOffer("pack", provider);
  const monthly = plans.find((plan) => plan.code === MONTHLY_CODE) ?? blankPlan(provider);

  return (
    <div className="flex flex-col gap-8">
      <h1 className="text-xl font-semibold tracking-tight text-primary">Ціни</h1>

      <SingleCard offer={single} onSaved={load} />
      <PackCard offer={pack} onSaved={load} />
      <MonthlyCard plan={monthly} onSaved={load} />
    </div>
  );
}

/** Спільна обгортка розділу: заголовок, пояснення, повідомлення, кнопка. */
function CardShell({
  title,
  error,
  saved,
  busy,
  onSave,
  children,
}: {
  title: string;
  error: string;
  saved: boolean;
  busy: boolean;
  onSave: () => void;
  children: React.ReactNode;
}) {
  return (
    <Panel>
      <h2 className="text-base font-semibold text-foreground">{title}</h2>
      <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{children}</div>
      {error ? (
        <div className="mt-4">
          <Alert tone="danger">{error}</Alert>
        </div>
      ) : null}
      <div className="mt-5 flex items-center gap-3">
        <Button loading={busy} onClick={onSave}>
          Зберегти
        </Button>
        {saved && !error ? <span className="text-sm text-muted">Збережено</span> : null}
      </div>
    </Panel>
  );
}

function useSaver(onSaved: () => Promise<void>) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  const run = async (action: () => Promise<unknown>) => {
    setBusy(true);
    setError("");
    setSaved(false);
    try {
      await action();
      await onSaved();
      setSaved(true);
    } catch (problem) {
      // Причина з сервера показується як є: тут її читає той, хто вміє
      // її прочитати, і загальне «щось пішло не так» лише сховало б,
      // яке саме правило каталогу не виконано.
      setError(
        problem instanceof ApiError
          ? `Сервер відмовив (${problem.status}): ${problem.message}`
          : "Не вдалося зберегти.",
      );
    } finally {
      setBusy(false);
    }
  };

  return { busy, error, saved, setError, run };
}

function SingleCard({ offer, onSaved }: { offer: AdminOffer; onSaved: () => Promise<void> }) {
  const [currency, setCurrency] = useState(offer.currency);
  const [amount, setAmount] = useState(toAmountField(offer.display_amount_minor, offer.currency));
  const { busy, error, saved, setError, run } = useSaver(onSaved);

  const save = () => {
    const parsed = fromAmountField(amount, currency);
    if ("error" in parsed) {
      setError(AMOUNT_ERROR[parsed.error]!);
      return;
    }
    void run(() =>
      saveAdminOffer(
        singlePayload(offer, {
          amountMinor: parsed.minor,
          currency,
        }),
      ),
    );
  };

  return (
    <CardShell
      title="Разова перевірка"
      error={error}
      saved={saved}
      busy={busy}
      onSave={save}
    >
      <Field label="Ціна">
        <Input value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="19.00" />
      </Field>
      <Field label="Валюта">
        <Input value={currency} onChange={(e) => setCurrency(e.target.value)} />
      </Field>
    </CardShell>
  );
}

function PackCard({ offer, onSaved }: { offer: AdminOffer; onSaved: () => Promise<void> }) {
  const [currency, setCurrency] = useState(offer.currency);
  const [amount, setAmount] = useState(toAmountField(offer.display_amount_minor, offer.currency));
  const [count, setCount] = useState(String(offer.audit_credits));
  const [presence, setPresence] = useState(String(offer.presence_credits));
  const { busy, error, saved, setError, run } = useSaver(onSaved);

  const parsedCount = Number.parseInt(count, 10);
  const validCount = Number.isFinite(parsedCount) ? parsedCount : 0;
  const parsedPresence = Number.parseInt(presence, 10);
  const validPresence = Number.isFinite(parsedPresence) ? parsedPresence : -1;
  const parsedAmount = fromAmountField(amount, currency);
  const unit =
    "minor" in parsedAmount ? packUnitPreview(parsedAmount.minor, validCount, currency) : "";

  const save = () => {
    if ("error" in parsedAmount) {
      setError(AMOUNT_ERROR[parsedAmount.error]!);
      return;
    }
    const problem = packProblem(validCount, validPresence);
    if (problem === "too_few") {
      setError("Пакет має містити щонайменше дві перевірки.");
      return;
    }
    if (problem === "presence_negative") {
      setError("Кількість AI presence — ціле число, не менше нуля.");
      return;
    }
    void run(() =>
      saveAdminOffer(
        packPayload(offer, {
          amountMinor: parsedAmount.minor,
          count: validCount,
          presence: validPresence,
          currency,
        }),
      ),
    );
  };

  return (
    <CardShell
      title="Пакет перевірок"
      error={error}
      saved={saved}
      busy={busy}
      onSave={save}
    >
      {/* Ціна за одну перевірку стоїть просто під ціною пакета: саме
          поруч із сумою її й читають, а окремою кліткою сітки вона
          відривалася від числа, до якого належить. */}
      <Field label="Ціна пакета" hint={unit ? `${unit} за одну перевірку` : undefined}>
        <Input value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="149.00" />
      </Field>
      <Field label="Перевірок у пакеті">
        <Input
          value={count}
          inputMode="numeric"
          onChange={(e) => setCount(e.target.value)}
        />
      </Field>
      {/* Окреме число: клієнт витрачає перевірки й присутність окремо,
          тож і продаються вони окремими кількостями. */}
      <Field label="AI presence у пакеті">
        <Input
          value={presence}
          inputMode="numeric"
          onChange={(e) => setPresence(e.target.value)}
        />
      </Field>
      <Field label="Валюта">
        <Input value={currency} onChange={(e) => setCurrency(e.target.value)} />
      </Field>
    </CardShell>
  );
}

function MonthlyCard({ plan, onSaved }: { plan: AdminPlan; onSaved: () => Promise<void> }) {
  const price = monthlyPrice(plan);
  const [currency, setCurrency] = useState(price?.currency ?? "USD");
  const [amount, setAmount] = useState(
    toAmountField(price?.display_amount_minor ?? null, price?.currency ?? "USD"),
  );
  const [presence, setPresence] = useState(String(monthlyPresence(plan)));
  const { busy, error, saved, setError, run } = useSaver(onSaved);

  const save = () => {
    const parsed = fromAmountField(amount, currency);
    if ("error" in parsed) {
      setError(AMOUNT_ERROR[parsed.error]!);
      return;
    }
    const checks = Number.parseInt(presence, 10);
    if (!Number.isFinite(checks) || checks < 0) {
      setError("Кількість перевірок Actual AI Presence має бути числом.");
      return;
    }
    void run(() =>
      saveAdminPlan(
        monthlyPayload(plan, {
          amountMinor: parsed.minor,
          presence: checks,
          currency,
        }),
      ),
    );
  };

  return (
    <CardShell
      title="Місячний план"
      error={error}
      saved={saved}
      busy={busy}
      onSave={save}
    >
      <Field label="Ціна за місяць">
        <Input value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="49.00" />
      </Field>
      <Field label="Actual AI Presence на місяць">
        <Input
          value={presence}
          inputMode="numeric"
          onChange={(e) => setPresence(e.target.value)}
        />
      </Field>
      <Field label="Валюта">
        <Input value={currency} onChange={(e) => setCurrency(e.target.value)} />
      </Field>
    </CardShell>
  );
}
