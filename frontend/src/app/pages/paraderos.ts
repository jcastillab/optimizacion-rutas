import { Component, inject } from '@angular/core';
import { AuthService } from '../core/auth.service';
import { Campo, Columna, CrudTable } from '../shared/crud-table';

@Component({
  selector: 'app-paraderos',
  imports: [CrudTable],
  template: `<app-crud-table titulo="Paraderos" ruta="/paraderos" singular="paradero" [columnas]="columnas" [campos]="campos"
    [puedeEscribir]="auth.esAdmin()" />`,
})
export class Paraderos {
  auth = inject(AuthService);
  columnas: Columna[] = [
    { clave: 'nombre', titulo: 'Nombre' }, { clave: 'lat', titulo: 'Latitud' },
    { clave: 'lon', titulo: 'Longitud' }, { clave: 'activo', titulo: 'Activo' },
  ];
  campos: Campo[] = [
    { clave: 'nombre', etiqueta: 'Nombre', tipo: 'text', requerido: true },
    { clave: 'lat', etiqueta: 'Latitud (-90 a 90)', tipo: 'number', step: 'any', requerido: true },
    { clave: 'lon', etiqueta: 'Longitud (-180 a 180)', tipo: 'number', step: 'any', requerido: true },
    { clave: 'activo', etiqueta: 'Activo', tipo: 'checkbox' },
  ];
}
