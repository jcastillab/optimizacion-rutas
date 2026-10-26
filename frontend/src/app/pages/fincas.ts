import { Component, inject } from '@angular/core';
import { AuthService } from '../core/auth.service';
import { Campo, Columna, CrudTable } from '../shared/crud-table';

@Component({
  selector: 'app-fincas',
  imports: [CrudTable],
  template: `<app-crud-table titulo="Fincas" ruta="/fincas" singular="finca" [columnas]="columnas" [campos]="campos"
    [puedeEscribir]="auth.esAdmin()" />`,
})
export class Fincas {
  auth = inject(AuthService);
  columnas: Columna[] = [
    { clave: 'nombre', titulo: 'Nombre' }, { clave: 'cod_nivel2', titulo: 'Cód. nivel 2' },
    { clave: 'lat', titulo: 'Latitud' }, { clave: 'lon', titulo: 'Longitud' }, { clave: 'activo', titulo: 'Activa' },
  ];
  campos: Campo[] = [
    { clave: 'nombre', etiqueta: 'Nombre', tipo: 'text', requerido: true },
    { clave: 'cod_nivel2', etiqueta: 'Código nivel 2', tipo: 'text' },
    { clave: 'lat', etiqueta: 'Latitud (-90 a 90)', tipo: 'number', step: 'any', requerido: true },
    { clave: 'lon', etiqueta: 'Longitud (-180 a 180)', tipo: 'number', step: 'any', requerido: true },
    { clave: 'activo', etiqueta: 'Activa', tipo: 'checkbox' },
  ];
}
