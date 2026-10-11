/**
 * legal-terms — es. Текст затвердженого пакета Legal Pack
 * (ТОВ «Акурлі», 5 вересня 2026), перенесений дослівно.
 *
 * Плейсхолдери `[[…]]` лишаються видимими: розділ 2 пакета прямо
 * забороняє вигадувати їхні значення, і сторінка не має права
 * вдавати, що дата чинності чи перелік cookie вже визначені.
 */

import { LegalPage, type LegalBlock } from "../../components/LegalPage";
import type { LocalizedPage } from "../../lib/page-types";

const BLOCKS: LegalBlock[] = [
  { kind: "para", text: "Estos términos regulan Crawldy, la vista previa gratuita, los informes de pago, las cuentas, Pack, Monthly y Actual AI Presence." },
  { kind: "heading", text: "Partes" },
  { kind: "para", text: "Crawldy está operado por LLC “Accurly”, código de identificación ucraniano 46295102, con domicilio social en 59 Stepana Bandery Street, Kamianets-Podilskyi, Kamianets-Podilskyi District, Khmelnytskyi Region, 32300, Ukraine." },
  { kind: "heading", text: "Aceptación de los términos" },
  { kind: "para", text: "«Tú» designa a la persona usuaria o a la organización en cuyo nombre se usa Crawldy. Si actúas para una organización, confirmas que puedes aceptar estos términos en su nombre. Al utilizar Crawldy, crear una cuenta o comprar un servicio, aceptas estos Términos, la Política de privacidad, la Política de reembolsos y la Política de uso aceptable. Antes del pago, el usuario debe poder abrir y guardar las versiones vigentes de estos documentos. Pueden crear una cuenta y comprar servicios los usuarios con capacidad legal para celebrar por sí mismos contratos vinculantes." },
  { kind: "heading", text: "Servicio" },
  { kind: "para", text: "Crawldy analiza páginas accesibles y genera un informe sobre visibilidad en buscadores e IA, estado técnico, rendimiento, accesibilidad y señales básicas de protección observables. El informe muestra cobertura, hallazgos, pruebas, impacto y prioridades. Refleja el estado disponible en el momento del análisis." },
  { kind: "heading", text: "Vista previa gratuita" },
  { kind: "para", text: "La vista previa gratuita funciona sin cuenta y sin límite comercial de cantidad. Muestra una puntuación general, la cobertura y algunos problemas principales. No desbloquea el informe completo, no concede un análisis completo de pago y no ejecuta Actual AI Presence. Los límites técnicos de seguridad y frecuencia no son una cuota comercial." },
  { kind: "heading", text: "Single" },
  { kind: "para", text: "Single es una compra única del informe completo para una auditoría concreta. No exige registro. Tras confirmar el pago, el comprador recibe un enlace protegido disponible durante 12 meses. Crear una cuenta después es opcional. El informe solo se vincula a una cuenta tras verificar la titularidad." },
  { kind: "para", text: "Single incluye la cantidad de Actual AI Presence mostrada antes del pago. La configuración inicial incluye una comprobación." },
  { kind: "heading", text: "Pack" },
  { kind: "para", text: "Pack exige una cuenta y concede la cantidad de análisis completos y Actual AI Presence mostrada antes del pago. Los análisis Pack no utilizados no caducan ni desaparecen al adquirir, renovar o cancelar Monthly. Pack no es una suscripción y no se renueva automáticamente." },
  { kind: "heading", text: "Monthly" },
  { kind: "para", text: "Monthly exige una cuenta y se renueva cada mes al precio mostrado. Incluye análisis completos ilimitados y una cantidad configurada por separado de Actual AI Presence para cada periodo mensual pagado." },
  { kind: "para", text: "«Ilimitados» significa que no existe un límite comercial de cantidad. Crawldy puede usar controles técnicos razonables de frecuencia, cola y concurrencia para la seguridad y estabilidad, pero no una cuota de pago oculta. Actual AI Presence sí está limitado; su cantidad se reinicia al comenzar cada periodo y no se acumula salvo indicación expresa." },
  { kind: "para", text: "Monthly puede cancelarse en el área de cliente o mediante la herramienta disponible. La cancelación detiene la siguiente renovación y el acceso continúa hasta finalizar el periodo pagado. Una organización no puede mantener dos suscripciones Monthly no terminadas a la vez." },
  { kind: "heading", text: "Sitios permitidos" },
  { kind: "para", text: "Puedes analizar un sitio que te pertenezca, que pertenezca a tu organización o a un cliente que haya autorizado debidamente el análisis. Se permite analizar páginas públicas con una finalidad legítima. No proporciones contraseñas, tokens, enlaces privados, áreas de cuenta, documentos confidenciales ni una dirección cuya comprobación infrinja la ley, un contrato o los derechos de otra persona." },
  { kind: "heading", text: "Actual AI Presence" },
  { kind: "para", text: "Actual AI Presence formula preguntas a proveedores externos de AI y registra las respuestas obtenidas en un momento concreto. La composición de los modelos, su disponibilidad, las reglas y las respuestas de los proveedores pueden cambiar. El resultado no garantiza que la marca sea o no sea mencionada a otro usuario, en otro momento, en otro país o con una consulta formulada de otra manera." },
  { kind: "heading", text: "Pagos mediante Paddle" },
  { kind: "para", text: "Los pagos se realizan mediante Paddle. En su modelo estándar, Paddle actúa como revendedor autorizado y Merchant of Record y gestiona el pago, los impuestos aplicables y el recibo. LLC “Accurly” opera Crawldy y proporciona acceso al servicio." },
  { kind: "para", text: "El checkout muestra producto, precio, moneda, impuestos y renovación. El acceso de pago solo se concede tras confirmarse el pago. Cerrar el checkout no demuestra que se haya pagado. Si el estado no está resuelto, Crawldy concilia primero la transacción y no ofrece un segundo pago." },
  { kind: "heading", text: "Análisis fallidos" },
  { kind: "para", text: "Si un análisis completo falla por un error técnico de Crawldy, podemos repetirlo, restaurar el derecho Pack o Monthly utilizado o reembolsar Single conforme a la Política de reembolsos. Si el sitio no está disponible o bloquea el acceso, Crawldy muestra la cobertura real y no inventa datos." },
  { kind: "heading", text: "Cuenta y seguridad" },
  { kind: "para", text: "Eres responsable de la información de la cuenta, la seguridad del acceso y los usuarios de tu organización. No compartas un enlace de invitado con personas no autorizadas." },
  { kind: "heading", text: "Uso del informe y propiedad" },
  { kind: "para", text: "Puedes utilizar, descargar y compartir el informe adquirido dentro de tu organización. Una agencia o consultor puede analizar el sitio de un cliente y entregar el informe a ese cliente si cuenta con su autorización. Esto no otorga el derecho a revender cuentas, créditos, acceso automatizado ni el propio servicio Crawldy sin un acuerdo separado. El software, el diseño, la metodología, el catálogo de comprobaciones y las marcas de Crawldy siguen siendo propiedad de LLC “Accurly” o de los respectivos titulares de derechos." },
  { kind: "heading", text: "Límites" },
  { kind: "para", text: "Crawldy es una herramienta informativa automatizada. El informe no garantiza posicionamiento, indexación o mención por IA; no es una prueba de penetración, evaluación de vulnerabilidades, certificación de seguridad o WCAG, asesoramiento jurídico o financiero ni una modificación automática del sitio." },
  { kind: "heading", text: "Disponibilidad del servicio" },
  { kind: "para", text: "No garantizamos funcionamiento ininterrumpido o sin errores." },
  { kind: "heading", text: "Suspensión del acceso" },
  { kind: "para", text: "Podemos limitar el acceso por seguridad, ley, abuso, fraude o impago. Un límite técnico o la cancelación de Monthly no elimina derechos Pack adquiridos por separado, salvo reembolso, fraude confirmado, contracargo u obligación legal." },
  { kind: "heading", text: "Responsabilidad" },
  { kind: "para", text: "No se limitan responsabilidades ni derechos del consumidor que la ley prohíba limitar. En la medida permitida, LLC “Accurly” no responde de daños indirectos, lucro cesante, pérdida de posiciones, menciones esperadas por IA ni decisiones tomadas solo a partir del informe. La responsabilidad total se limita al importe pagado por el Single o Pack afectado o, para Monthly, a lo pagado en los 12 meses anteriores. No se aplica a dolo, fraude, negligencia grave ni responsabilidad que no pueda limitarse." },
  { kind: "heading", text: "Finalización del uso" },
  { kind: "para", text: "Puedes cancelar Monthly, dejar de usar el servicio y eliminar tu cuenta. Los registros exigidos por ley se conservan." },
  { kind: "heading", text: "Ley aplicable" },
  { kind: "para", text: "Estos términos se rigen por la legislación de Ucrania. Las controversias serán resueltas por los tribunales competentes de Ucrania, salvo que las normas imperativas de protección del consumidor otorguen al usuario el derecho a acudir a otro tribunal o a aplicar otra legislación obligatoria. Las partes intentarán primero resolver la cuestión mediante el formulario de contacto protegido." },
  { kind: "heading", text: "Cambios en los términos" },
  { kind: "para", text: "Las modificaciones sustanciales no cambian retroactivamente una compra única completada y se comunicarán a los usuarios registrados." },
  { kind: "heading", text: "Contacto" },
  { kind: "para", text: "LLC “Accurly”, código de identificación ucraniano 46295102." },
  { kind: "para", text: "Utiliza el formulario protegido de Crawldy." },
];

function Body() {
  return (
    <LegalPage
      doc={{
        title: "Términos del servicio",
        meta: ["**Fecha de entrada en vigor:** `1 de enero de 2026`", "**Versión:** 1.0"],
        blocks: BLOCKS,
        contentsLabel: "Contenido",
        relatedLabel: "Documentos relacionados",
        related: [
    { label: "Privacidad y cookies", href: "/es/privacidad" },
    { label: "Reembolsos y cancelación", href: "/es/reembolsos" },
    { label: "Uso aceptable", href: "/es/uso-aceptable" },
    { label: "Contacto", href: "/es/contacto" },
        ],
      }}
    />
  );
}

export const es: LocalizedPage = {
  slug: "terminos",
  title: "Términos del servicio — Crawldy",
  h1: "Términos del servicio",
  description: "Estos términos regulan Crawldy, la vista previa gratuita, los informes de pago, las cuentas, Pack, Monthly y Actual AI Presence.",
  navLabel: "Términos del servicio",
  Body,
};
