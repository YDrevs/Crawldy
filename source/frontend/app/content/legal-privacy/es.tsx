/**
 * legal-privacy — es. Текст затвердженого пакета Legal Pack
 * (ТОВ «Акурлі», 5 вересня 2026), перенесений дослівно.
 *
 * Плейсхолдери `[[…]]` лишаються видимими: розділ 2 пакета прямо
 * забороняє вигадувати їхні значення, і сторінка не має права
 * вдавати, що дата чинності чи перелік cookie вже визначені.
 */

import { LegalPage, type LegalBlock } from "../../components/LegalPage";
import type { LocalizedPage } from "../../lib/page-types";

const BLOCKS: LegalBlock[] = [
  { kind: "para", text: "Esta política explica qué datos trata Crawldy, por qué son necesarios, quién puede recibirlos y qué derechos tienen los usuarios." },
  { kind: "heading", text: "Responsable" },
  { kind: "para", text: "Crawldy está operado por LIMITED LIABILITY COMPANY “Accurly” (LLC “Accurly”), código de identificación ucraniano 46295102. Domicilio social: 59 Stepana Bandery Street, Kamianets-Podilskyi, Kamianets-Podilskyi District, Khmelnytskyi Region, 32300, Ukraine." },
  { kind: "para", text: "Para consultas de privacidad, utiliza el formulario protegido de Crawldy y selecciona «Privacidad y datos»." },
  { kind: "heading", text: "Ámbito" },
  { kind: "para", text: "Esta política se aplica a `crawldy.ai y crawldy.com`, la vista previa gratuita, los análisis de pago, Actual AI Presence, las cuentas, el área de cliente, los pagos y el formulario de contacto." },
  { kind: "heading", text: "Datos que tratamos" },
  { kind: "para", text: "**Sitio web y análisis.** Tratamos la URL y el dominio enviados, páginas públicas, respuestas del servidor, cabeceras, metadatos, enlaces, datos estructurados, métricas de rendimiento, hallazgos, pruebas, cobertura y puntuaciones." },
  { kind: "para", text: "**Cuenta.** Si creas una cuenta, tratamos el nombre, correo electrónico, datos de autenticación, pertenencia a una organización, historial de análisis, saldos adquiridos y uso del servicio." },
  { kind: "para", text: "**Pago.** Paddle trata los datos de pago en el checkout. Crawldy no recibe el número completo de la tarjeta. Recibimos y conservamos identificadores de cliente o transacción, producto, importe, moneda, estado del pago y de la suscripción, datos de reembolso y la información necesaria para prestar y contabilizar el servicio." },
  { kind: "para", text: "**Actual AI Presence.** Para un análisis de pago podemos crear consultas sobre la marca, el sitio, la empresa, el mercado o los servicios y enviarlas a OpenAI, Anthropic, Google y Perplexity. Conservamos la consulta, la respuesta, la fecha, el modelo, el estado y la observación registrada. La vista previa gratuita no ejecuta Actual AI Presence." },
  { kind: "para", text: "**Contacto y seguridad.** Tratamos el nombre, dirección de respuesta, asunto, mensaje, estado de entrega y resultado de Cloudflare Turnstile. También podemos tratar dirección IP, navegador, dispositivo, idioma, hora, registros de error, identificadores de sesión, límites de frecuencia y señales contra abusos." },
  { kind: "heading", text: "Finalidades del tratamiento" },
  { kind: "para", text: "Usamos los datos para analizar el sitio indicado y generar el resultado, proporcionar el informe adquirido, mantener el saldo de Pack o gestionar Monthly, ejecutar Actual AI Presence después del pago, crear y proteger una cuenta, confirmar pagos, reembolsos o cancelaciones, responder consultas, detectar errores, fraude, abusos automatizados y amenazas de seguridad, cumplir obligaciones contables, fiscales y otras obligaciones legales, y mejorar la fiabilidad y claridad de Crawldy a partir de datos agregados o anonimizados." },
  { kind: "heading", text: "Bases jurídicas" },
  { kind: "para", text: "Según corresponda, el tratamiento se basa en la ejecución de un contrato o medidas precontractuales, una obligación legal, intereses legítimos de seguridad y funcionamiento o tu consentimiento. El consentimiento se usa para cookies opcionales de analítica o marketing si se activan." },
  { kind: "heading", text: "Análisis automatizado" },
  { kind: "para", text: "Crawldy genera automáticamente hallazgos técnicos, puntuación, cobertura y prioridades. No adopta una decisión jurídica o de efecto similar sobre una persona. La puntuación general puede no mostrarse si faltan datos suficientes." },
  { kind: "heading", text: "Destinatarios" },
  { kind: "para", text: "Solo comunicamos los datos necesarios:" },
  {
    kind: "list",
    items: [
      "a Paddle para checkout, pagos, impuestos, recibos, suscripciones y reembolsos;",
      "a Cloudflare para Turnstile y las funciones de seguridad habilitadas;",
      "a OpenAI, Anthropic, Google y Perplexity para Actual AI Presence de pago;",
      "a proveedores de alojamiento, bases de datos, almacenamiento, autenticación, correo, supervisión y copias de seguridad;",
      "a asesores, tribunales o autoridades cuando lo exija la ley.",
    ],
  },
  { kind: "para", text: "No vendemos datos personales. No enviamos de forma intencionada contraseñas, credenciales de pago o contenido privado a los proveedores de IA. Los usuarios no deben proporcionar esos datos a Crawldy." },
  { kind: "heading", text: "Conservación" },
  {
    kind: "list",
    items: [
      "Vista previa gratuita: hasta 30 días.",
      "Informe Single anónimo y token seguro: 12 meses desde la compra.",
      "Cuenta, historial, Pack y Monthly: mientras la cuenta esté activa; tras una eliminación verificada, los datos no exigidos por ley se eliminan o anonimizan en 30 días y las copias de seguridad pueden conservarse hasta 90 días.",
      "Mensajes de contacto: hasta 24 meses tras cerrar la solicitud.",
      "Registros de seguridad y límites: hasta 90 días, salvo que un incidente requiera más tiempo.",
      "Datos contables, fiscales y de pago: durante el periodo exigido por la ley.",
      "Datos de proveedores externos: conforme a sus condiciones y a la configuración real de la API.",
    ],
  },
  { kind: "heading", text: "Cookies y almacenamiento local" },
  { kind: "para", text: "Crawldy puede usar cookies técnicamente necesarias para el funcionamiento del sitio, la autenticación y el almacenamiento de las preferencias del usuario." },
  { kind: "para", text: "Cloudflare Turnstile trata señales del navegador para distinguir a una persona de una solicitud automatizada. Cloudflare indica que Turnstile no accede ni transmite el texto introducido en un formulario. Paddle puede usar tecnologías necesarias propias en el checkout." },
  { kind: "heading", text: "Tus derechos" },
  { kind: "para", text: "Según la ley aplicable, puedes solicitar acceso, copia, rectificación, supresión, limitación, oposición, portabilidad o retirada del consentimiento. También puedes reclamar ante una autoridad de protección de datos competente." },
  { kind: "para", text: "Utiliza el formulario protegido y selecciona «Privacidad y datos». Podemos pedir una prueba de identidad o de representación de una organización." },
  { kind: "heading", text: "Datos de terceros y sitios de clientes" },
  { kind: "para", text: "Debes tener una base legal para enviar un sitio. No proporciones URL privadas, contraseñas, tokens, documentos privados ni secretos. Si actúas para un cliente, eres responsable de obtener la autorización y facilitar la información necesaria." },
  { kind: "heading", text: "Derecho a utilizar el servicio" },
  { kind: "para", text: "El servicio está destinado a usuarios con capacidad legal para celebrar por sí mismos contratos vinculantes." },
  { kind: "heading", text: "Seguridad" },
  { kind: "para", text: "Aplicamos medidas técnicas y organizativas para proteger los datos. Ningún sistema puede garantizar una seguridad absoluta. En caso de incidente, actuaremos de acuerdo con la legislación aplicable." },
  { kind: "heading", text: "Cambios en la política" },
  { kind: "para", text: "Las modificaciones se publicarán con fecha y versión y las modificaciones sustanciales se comunicarán a los usuarios registrados por un canal disponible." },
  { kind: "heading", text: "Contacto" },
  { kind: "para", text: "LLC “Accurly”, código de identificación ucraniano 46295102." },
  { kind: "para", text: "59 Stepana Bandery Street, Kamianets-Podilskyi, Kamianets-Podilskyi District, Khmelnytskyi Region, 32300, Ukraine." },
  { kind: "para", text: "Utiliza el formulario protegido de Crawldy." },
  { kind: "para", text: "---" },
];

function Body() {
  return (
    <LegalPage
      doc={{
        title: "Privacidad y cookies",
        meta: ["**Fecha de entrada en vigor:** `1 de enero de 2026`", "**Versión:** 1.0"],
        blocks: BLOCKS,
        contentsLabel: "Contenido",
        relatedLabel: "Documentos relacionados",
        related: [
    { label: "Términos del servicio", href: "/es/terminos" },
    { label: "Reembolsos y cancelación", href: "/es/reembolsos" },
    { label: "Uso aceptable", href: "/es/uso-aceptable" },
    { label: "Contacto", href: "/es/contacto" },
        ],
      }}
    />
  );
}

export const es: LocalizedPage = {
  slug: "privacidad",
  title: "Privacidad y cookies — Crawldy",
  h1: "Privacidad y cookies",
  description: "Esta política explica qué datos trata Crawldy, por qué son necesarios, quién puede recibirlos y qué derechos tienen los usuarios.",
  navLabel: "Privacidad y cookies",
  Body,
};
