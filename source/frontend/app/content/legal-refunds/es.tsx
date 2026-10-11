/**
 * legal-refunds — es. Текст затвердженого пакета Legal Pack
 * (ТОВ «Акурлі», 5 вересня 2026), перенесений дослівно.
 *
 * Плейсхолдери `[[…]]` лишаються видимими: розділ 2 пакета прямо
 * забороняє вигадувати їхні значення, і сторінка не має права
 * вдавати, що дата чинності чи перелік cookie вже визначені.
 */

import { LegalPage, type LegalBlock } from "../../components/LegalPage";
import type { LocalizedPage } from "../../lib/page-types";

const BLOCKS: LegalBlock[] = [
  { kind: "para", text: "Estas reglas voluntarias no limitan derechos legales imperativos." },
  { kind: "heading", text: "Checkout cerrado" },
  { kind: "para", text: "Si cierras el checkout antes de completar el pago, la auditoría permanece guardada. Solo se realiza el cargo si Paddle confirma el pago. Una vez confirmado que el pago no se ha completado, puedes repetir el pago para la misma auditoría." },
  { kind: "para", text: "Si el estado no está resuelto, Crawldy comprueba primero la transacción y no ofrece un pago duplicado." },
  { kind: "heading", text: "Single" },
  { kind: "para", text: "El informe completo empieza a procesarse inmediatamente después del pago confirmado, a solicitud del comprador. Una vez generado y abierto correctamente, no hay reembolso voluntario por cambio de opinión, salvo obligación legal." },
  { kind: "para", text: "Reembolsaremos el importe o repetiremos el análisis sin coste adicional si:" },
  {
    kind: "list",
    items: [
      "el pago se ha duplicado;",
      "se ha realizado el cargo pero no se ha facilitado el acceso de pago;",
      "un error técnico de Crawldy impidió generar un informe completo utilizable y el problema no puede resolverse repitiendo el análisis en un plazo razonable.",
    ],
  },
  { kind: "para", text: "Una puntuación baja, los hallazgos o la ausencia de una mención esperada por IA no son por sí solos un error técnico." },
  { kind: "heading", text: "Pack" },
  { kind: "para", text: "Un Pack totalmente sin usar puede reembolsarse dentro de los 14 días naturales siguientes a la compra. Tras usar cualquier análisis completo o Actual AI Presence no se ofrece un reembolso voluntario total, salvo obligación legal." },
  { kind: "para", text: "Si un error técnico de Crawldy consume un derecho, se restaura. Los derechos Pack no utilizados no caducan." },
  { kind: "heading", text: "Monthly" },
  { kind: "para", text: "Monthly puede cancelarse en cualquier momento para detener futuras renovaciones. El acceso continúa hasta terminar el periodo pagado." },
  { kind: "para", text: "El primer pago puede reembolsarse dentro de 14 días naturales si no se ha ejecutado ningún análisis completo ni Actual AI Presence." },
  { kind: "para", text: "La renovación automática más reciente puede reembolsarse dentro de 7 días naturales si no se ha usado ninguno en el nuevo periodo. Tras el uso no hay reembolso voluntario proporcional, salvo obligación legal." },
  { kind: "para", text: "Cancelar Monthly no elimina las comprobaciones Pack adquiridas por separado." },
  { kind: "heading", text: "Problemas técnicos del sitio analizado" },
  { kind: "para", text: "Si el sitio no está disponible, bloquea el análisis, la dirección indicada es incorrecta o responde solo en parte, Crawldy muestra la cobertura real. Consideraremos repetir el análisis o realizar un reembolso si el resultado no puede considerarse utilizable y esta limitación no era evidente antes de la compra." },
  { kind: "heading", text: "Cómo enviar una solicitud" },
  { kind: "para", text: "Utiliza el formulario protegido y selecciona «Pago, reembolso o suscripción». Indica la dirección para la respuesta, el dominio, la fecha aproximada de compra y el identificador de la transacción o del recibo, si lo tienes." },
  { kind: "para", text: "No envíes el número de tarjeta, el código de seguridad ni credenciales bancarias." },
  { kind: "para", text: "Confirmaremos la recepción de la solicitud y comunicaremos la decisión o los datos que falten. Los reembolsos aprobados se tramitan mediante Paddle al método de pago original. El plazo de abono depende de Paddle, del banco y del método de pago." },
  { kind: "heading", text: "Contracargos y fraude" },
  { kind: "para", text: "Si un pago se impugna sin contacto previo, podemos suspender los derechos relacionados mientras se revisa el caso. Esto no priva al usuario de sus derechos imperativos. Un reembolso confirmado, un contracargo o un pago fraudulento puede dar lugar a la cancelación del acceso no utilizado correspondiente." },
  { kind: "heading", text: "Contacto" },
  { kind: "para", text: "LLC “Accurly”, código de identificación ucraniano 46295102." },
  { kind: "para", text: "Utiliza el formulario protegido de Crawldy." },
];

function Body() {
  return (
    <LegalPage
      doc={{
        title: "Reembolsos y cancelación",
        meta: ["**Fecha de entrada en vigor:** `1 de enero de 2026`", "**Versión:** 1.0"],
        blocks: BLOCKS,
        contentsLabel: "Contenido",
        relatedLabel: "Documentos relacionados",
        related: [
    { label: "Privacidad y cookies", href: "/es/privacidad" },
    { label: "Términos del servicio", href: "/es/terminos" },
    { label: "Uso aceptable", href: "/es/uso-aceptable" },
    { label: "Contacto", href: "/es/contacto" },
        ],
      }}
    />
  );
}

export const es: LocalizedPage = {
  slug: "reembolsos",
  title: "Reembolsos y cancelación — Crawldy",
  h1: "Reembolsos y cancelación",
  description: "Estas reglas voluntarias no limitan derechos legales imperativos.",
  navLabel: "Reembolsos y cancelación",
  Body,
};
