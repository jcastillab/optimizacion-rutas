import { DatePipe } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ListaPaginada } from '../core/lista';
import { Evento } from '../core/models';
import { lineasDetalle } from '../shared/detalle';
import { Paginador } from '../shared/paginador';

@Component({
  selector: 'app-eventos',
  imports: [DatePipe, FormsModule, Paginador],
  template: `
    <h1>Eventos de auditoría</h1>
    <form class="filtros" role="search" (submit)="$event.preventDefault(); buscar()">
      <label>Acción
        <select name="accion" [(ngModel)]="f.accion">
          <option value="">Todas</option>
          @for (a of acciones; track a) { <option [value]="a">{{ a }}</option> }
        </select>
      </label>
      <label>Usuario <input name="usuario" [(ngModel)]="f.usuario" /></label>
      <label>Entidad <input name="entidad" [(ngModel)]="f.entidad" /></label>
      <label>Desde <input type="date" name="desde" [(ngModel)]="f.desde" /></label>
      <label>Hasta <input type="date" name="hasta" [(ngModel)]="f.hasta" /></label>
      <button type="submit" class="btn">Filtrar</button>
    </form>
    <div aria-live="polite">
      @if (lista.cargando()) { <p class="estado">Cargando…</p> }
      @else if (lista.error()) { <p class="estado error" role="alert">{{ lista.error() }}</p> }
      @else if (!lista.items().length) { <p class="estado">No hay eventos con esos filtros.</p> }
    </div>
    @if (lista.items().length) {
      <div class="tabla-wrap">
        <table>
          <caption class="solo-lector">Eventos de auditoría</caption>
          <thead><tr>
            <th scope="col">Fecha</th><th scope="col">Usuario</th><th scope="col">Acción</th>
            <th scope="col">Entidad</th><th scope="col">Id</th><th scope="col">Detalle</th>
          </tr></thead>
          <tbody>
            @for (e of lista.items(); track e.id) {
              <tr>
                <td>{{ e.fecha | date: 'dd/MM/yyyy HH:mm:ss' }}</td><td>{{ e.usuario }}</td><td>{{ e.accion }}</td>
                <td>{{ e.entidad }}</td><td>{{ e.entidad_id }}</td>
                <td>@for (l of lineas(e.detalle); track $index) { <div>{{ l }}</div> }</td>
              </tr>
            }
          </tbody>
        </table>
      </div>
    }
    <app-paginador [pagina]="lista.pagina()" [porPagina]="lista.porPagina" [total]="lista.total()" (cambiar)="lista.irA($event)" />
  `,
})
export class Eventos implements OnInit {
  acciones = ['login', 'login_fallido', 'logout', 'crear', 'editar', 'borrar', 'importar', 'simular'];
  f = { accion: '', usuario: '', entidad: '', desde: '', hasta: '' };
  lista = new ListaPaginada<Evento>('/eventos', 50);
  lineas = lineasDetalle;

  ngOnInit() { this.buscar(); }
  /** Congela los filtros escritos; paginar usa esos, no lo que se esté tecleando. */
  buscar() { this.lista.buscar({ ...this.f }); }
}
