import { Component, inject } from '@angular/core';
import { AuthService } from '../core/auth.service';
import { Campo, Columna, CrudTable } from '../shared/crud-table';

@Component({
  selector: 'app-tipos-bus',
  imports: [CrudTable],
  template: `<app-crud-table titulo="Tipos de bus" ruta="/tipos-bus" singular="tipo de bus" [columnas]="columnas" [campos]="campos"
    [puedeEscribir]="auth.esAdmin()" />`,
})
export class TiposBus {
  auth = inject(AuthService);
  columnas: Columna[] = [
    { clave: 'tipo', titulo: 'Tipo' }, { clave: 'capacidad', titulo: 'Capacidad' },
    { clave: 'costo', titulo: 'Costo', fmt: (f) => Number(f.costo).toLocaleString('es-CO') },
    { clave: 'activo', titulo: 'Activo' },
  ];
  campos: Campo[] = [
    { clave: 'tipo', etiqueta: 'Tipo', tipo: 'text', requerido: true },
    { clave: 'capacidad', etiqueta: 'Capacidad (mayor a 0)', tipo: 'number', step: '1', requerido: true },
    { clave: 'costo', etiqueta: 'Costo (0 o más)', tipo: 'number', step: 'any', requerido: true },
    { clave: 'activo', etiqueta: 'Activo', tipo: 'checkbox' },
  ];
}
