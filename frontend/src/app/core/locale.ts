import { registerLocaleData } from '@angular/common';
import localeEsCo from '@angular/common/locales/es-CO';
import { LOCALE_ID, Provider } from '@angular/core';

registerLocaleData(localeEsCo);
/** Locale único de la app (pipes number/date). Las pruebas que renderizan deben usar este mismo proveedor. */
export const proveedorLocale: Provider = { provide: LOCALE_ID, useValue: 'es-CO' };
