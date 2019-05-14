# l10n_cl_fe
Se crea este repositorio, para dar un enfoque de firma electrónica directa con el SII.

 - Se tomaron los inicios de github.com/odoo-chile/l10n_cl_dte y otros módulos de odoo-chile y la continuación de estos en github.com/dansanti/l10n_cl_dte.
 - Este repositorio se crea con la finalidad de unificar módulos y facilitar la mantención de la facturación electrónica, que se estaba muy complejo
 - obtener módulo de exportación xlsx "Base report xlsx" desde https://github.com/OCA/reporting-engine
 - Se integra la consulta de datos de empresas al repositorio https://sre.cl, para permitir obtener datos digitando el rut
 - Al instalar este módulo acepta que por defecto estará activa la sincronización de datos de partners al repositorio https://sre.cl, sin embargo puede desactivarlo en todo momento desde el panel de configuración general.
 - Integración con https://apicaf.cl , Api que permite emitir folios vía api, sin pasar por la página del SII. El uso y condiciones de la api es según políticas expuestas en el sitio web mismo de la api.

 Estado:
 - - Factura Electrónica (FAC 33, FNA 34): Ok envío, Ok muestra impresa, Ok Certificación
 - - Nota de Crédito Electrónica: Ok envío, Ok muestra impresa, Ok Certificación
 - - Nota de Débito Electrónica: Ok envío, Ok muestra impresa, Ok Certificación
 - - Recepción XML Intercambio: Ok recepción, Ok respuesta mercaderías, Ok respuesta Validación Comercial, Ok Envío Recepción al SII, Ok Certificación
 - - Libro de Compra Venta: Ok envío al SII, Ok Certificación (Básico y Exentos)
 - - Consumo de Folios: Validación OK, Envío OK, Certificación OK
 - - Boleta Electrónica por BO ( 39, 41 ): Validación Ok, Muestra impresa No probado aún, Información Pública no adaptada aún
 - - Libro Boletas Electrónica: Validación Ok, Creación XML OK
 - - Boleta Electrónica por POS ( 39, 41): Validación Ok, Muestras Impresas Ticket OK, Generación XML Ok, Visaulización Pública Ok, Certificación OK vía https://gitlab.com/dansanti/l10n_cl_dte_point_of_sale
 - - Nota de Crédito Electrónica para Boletas ( Solo por BO POS): Validación Ok, Generación XML Ok, Muestras Impresas Ticket OK, Certificación OK vía https://gitlab.com/dansanti/l10n_cl_dte_point_of_sale
 - - Guía de Despacho Electrónica: Ok envío, Ok muestra impresa, Ok Certificación, vía https://gitlab.com/dansanti/l10n_cl_stock_picking
 - - Libro Guía Despacho: Ok envío, Ok Muestras impresas, Ok Certificación, vía https://gitlab.com/dansanti/l10n_cl_stock_picking
 - - Factoring (Cesión de Créditos): Ok Envío, Ok Certificación, vía https://gitlab.com/dansanti/l10n_cl_dte_factoring
 - - Factura de Exportación Electrónica ( 110 con sus NC 111 y ND 112): No Portado, No Probado vía https://gitlab.com/dansanti/l10n_cl_dte_exportacion
 - - Liquidación de Facturas: No desarrollada
 - - Factura de Compra Electrónica ( 46 ): No desarrollada (NO confundir con el concepto de ingresar facturas de proveedor, que la mayoría le dice de compras, este es un documento de retención de impuestos, la recepción de documentos proveedor, está soportada, con los4 tipos de respuesta que se deben generar según normativa del sii)


 Agradecimientos y colaboradores:

 - Daniel Blanco
 - Nelson Ramirez
 - Carlos Toledo
 - Carlos Lopez

<a href='https://www.flow.cl/btn.php?token=ju5ulkb' target='_blank'>
  <img src='https://www.flow.cl/img/botones/btn-donar-negro.png'>
</a>
