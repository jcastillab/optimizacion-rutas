import { Component, computed, inject } from '@angular/core';
import { AuthService } from '../core/auth.service';
import { CatalogosService, Ref } from '../core/catalogos.service';
import { Campo, Columna, CrudTable, Opcion } from '../shared/crud-table';

@Component({
  selector: 'app-personas',
  imports: [CrudTable],
  template: `<app-crud-table titulo="Personas" ruta="/personas" singular="persona" [columnas]="columnas()" [campos]="campos()"
    [puedeEscribir]="auth.esAdmin()" />`,
})
export class Personas {
  auth = inject(AuthService);
  private cat = inject(CatalogosService);

  constructor() {
    this.cat.asegurar();
  }

  columnas = computed<Columna[]>(() => [
    { clave: 'identificacion', titulo: 'Identificación' },
    { clave: 'nombre', titulo: 'Nombre' },
    { clave: 'finca_id', titulo: 'Finca', fmt: (f) => this.cat.nombre(this.cat.fincas(), f.finca_id) },
    { clave: 'paradero_id', titulo: 'Paradero', fmt: (f) => this.cat.nombre(this.cat.paraderos(), f.paradero_id) },
    { clave: 'activo', titulo: 'Activa' },
  ]);

  campos = computed<Campo[]>(() => {
    const op = (l: Ref[]): Opcion[] => l.map((x) => ({ valor: x.id, texto: x.nombre }));
    return [
      { clave: 'identificacion', etiqueta: 'Identificación', tipo: 'text', requerido: true },
      { clave: 'nombre', etiqueta: 'Nombre', tipo: 'text', requerido: true },
      { clave: 'finca_id', etiqueta: 'Finca', tipo: 'select', requerido: true, opciones: op(this.cat.fincas()) },
      { clave: 'paradero_id', etiqueta: 'Paradero', tipo: 'select', opciones: op(this.cat.paraderos()) },
      { clave: 'activo', etiqueta: 'Activa', tipo: 'checkbox' },
    ];
  });
}
