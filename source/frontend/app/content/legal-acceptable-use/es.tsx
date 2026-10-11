/**
 * legal-acceptable-use — es. Текст затвердженого пакета Legal Pack
 * (ТОВ «Акурлі», 5 вересня 2026), перенесений дослівно.
 *
 * Плейсхолдери `[[…]]` лишаються видимими: розділ 2 пакета прямо
 * забороняє вигадувати їхні значення, і сторінка не має права
 * вдавати, що дата чинності чи перелік cookie вже визначені.
 */

import { LegalPage, type LegalBlock } from "../../components/LegalPage";
import type { LocalizedPage } from "../../lib/page-types";

const BLOCKS: LegalBlock[] = [
  { kind: "para", text: "Estas reglas protegen a los usuarios, a Crawldy y a los sitios analizados." },
  { kind: "heading", text: "Uso permitido" },
  { kind: "para", text: "Puedes analizar páginas públicas propias, de tu organización o de clientes que hayan autorizado el análisis y compartir el informe con esos clientes." },
  { kind: "heading", text: "Uso prohibido" },
  { kind: "para", text: "No puedes utilizar Crawldy para:" },
  {
    kind: "list",
    items: [
      "analizar un sitio con fines ilegales, fraudulentos, dañinos o de acoso;",
      "acceder a páginas, archivos o sistemas que no sean públicos;",
      "enviar a Crawldy contraseñas, tokens, enlaces privados, claves secretas u otras credenciales;",
      "eludir el acceso, CAPTCHA, Turnstile, límites de frecuencia, bloqueos técnicos u otras protecciones;",
      "explotar vulnerabilidades, realizar pruebas de penetración, distribuir código malicioso, provocar una denegación de servicio o efectuar pruebas destructivas;",
      "generar carga excesiva de forma intencionada o eludir límites técnicos mediante varias sesiones, cuentas u organizaciones;",
      "vulnerar la privacidad, los derechos de autor, las marcas, restricciones contractuales u otros derechos de terceros;",
      "revender cuentas, créditos o acceso automatizado, ni copiar Crawldy sin un acuerdo aparte;",
      "presentar el informe como certificación oficial de seguridad, accesibilidad, cumplimiento legal, posición en buscadores o recomendación de IA.",
    ],
  },
  { kind: "heading", text: "Cómo funciona el análisis" },
  { kind: "para", text: "Crawldy lee señales observables de páginas públicas. Sin una función independiente expresamente acordada y una base jurídica válida, el servicio no debe iniciar sesión en áreas privadas, introducir credenciales, enviar formularios, eludir protecciones ni realizar pruebas intrusivas." },
  { kind: "heading", text: "Protección del servicio" },
  { kind: "para", text: "Podemos detener o ralentizar un análisis si crea un riesgo para el sitio analizado, para Crawldy o para otros usuarios, o si infringe la ley. La protección técnica frente al abuso es independiente de los derechos de la tarifa." },
  { kind: "para", text: "Las medidas deben limitarse, cuando sea posible, al análisis o usuario problemático. La cancelación de Monthly o un bloqueo técnico no elimina los análisis Pack adquiridos legalmente, salvo reembolso, fraude confirmado u obligación legal." },
  { kind: "heading", text: "Comunicar un problema" },
  { kind: "para", text: "Para comunicar un uso indebido, utiliza el formulario protegido e indica dominio, hora e información técnica disponible. No envíes secretos." },
  { kind: "heading", text: "Consecuencias de una infracción" },
  { kind: "para", text: "Según la gravedad, podemos advertir al usuario, detener un análisis, limitar temporalmente el acceso o cerrar una cuenta. Podemos conservar las pruebas necesarias y dirigirnos a las autoridades competentes cuando lo exija la ley o la defensa frente a una amenaza real." },
  { kind: "heading", text: "Contacto" },
  { kind: "para", text: "LLC “Accurly”, código de identificación ucraniano 46295102." },
  { kind: "para", text: "Utiliza el formulario protegido de Crawldy." },
];

function Body() {
  return (
    <LegalPage
      doc={{
        title: "Uso aceptable",
        meta: ["**Fecha de entrada en vigor:** `1 de enero de 2026`", "**Versión:** 1.0"],
        blocks: BLOCKS,
        contentsLabel: "Contenido",
        relatedLabel: "Documentos relacionados",
        related: [
    { label: "Privacidad y cookies", href: "/es/privacidad" },
    { label: "Términos del servicio", href: "/es/terminos" },
    { label: "Reembolsos y cancelación", href: "/es/reembolsos" },
    { label: "Contacto", href: "/es/contacto" },
        ],
      }}
    />
  );
}

export const es: LocalizedPage = {
  slug: "uso-aceptable",
  title: "Uso aceptable — Crawldy",
  h1: "Uso aceptable",
  description: "Puedes analizar páginas públicas propias, de tu organización o de clientes que hayan autorizado el análisis y compartir el informe con esos clientes.",
  navLabel: "Uso aceptable",
  Body,
};
