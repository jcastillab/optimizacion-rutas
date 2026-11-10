import { Component } from '@angular/core';
import { Campo, Columna, CrudTable } from '../shared/crud-table';

@Component({
  selector: 'app-usuarios',
  imports: [CrudTable],
  template: `<app-crud-table titulo="Usuarios" ruta="/usuarios" singular="usuario" [columnas]="columnas" [campos]="campos"
    [filtroActivo]="false" [puedeEscribir]="true" [sinBorrar]="true" />`,
})
export class Usuarios {
  columnas: Columna[] = [
    { clave: 'usuario', titulo: 'Usuario' }, { clave: 'nombre', titulo: 'Nombre' },
    { clave: 'rol', titulo: 'Rol' }, { clave: 'activo', titulo: 'Activo' },
  ];
  campos: Campo[] = [
    { clave: 'usuario', etiqueta: 'Usuario', tipo: 'text', requerido: true },
    { clave: 'nombre', etiqueta: 'Nombre', tipo: 'text', requerido: true },
    {
      clave: 'rol', etiqueta: 'Rol', tipo: 'select', requerido: true, porDefecto: 'lector',
      opciones: [{ valor: 'lector', texto: 'Lector' }, { valor: 'admin', texto: 'Administrador' }],
    },
    { clave: 'clave', etiqueta: 'Contraseña', tipo: 'password', requerido: true, ayuda: 'Al editar, déjala vacía para no cambiarla.' },
    { clave: 'activo', etiqueta: 'Activo', tipo: 'checkbox' },
  ];
}
