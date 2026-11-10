import { DatePipe, DecimalPipe } from '@angular/common';
import { Component, OnInit, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { ApiError, ApiService } from '../core/api.service';
import { AuthService } from '../core/auth.service';
import { Corrida } from '../core/models';
import { ListaPaginada } from '../core/lista';
import { NotificacionesService } from '../core/notificaciones.service';
import { Paginador } from '../shared/paginador';

@Component({
  selector: 'app-corridas',
  imports: [DatePipe, DecimalPipe, RouterLink, Paginador],
  template: `
    <h1>Corridas</h1>
    <div aria-live="polite">
      @if (lista.cargando()) { <p class="estado">Cargando…</p> }
      @else if (lista.error()) { <p class="estado error" role="alert">{{ lista.error() }}</p> }
      @else if (!lista.items().length) { <p class="estado">Aún no hay corridas. Ejecuta una desde el simulador.</p> }
    </div>
    @if (lista.items().length) {
      <div class="tabla-wrap">
        <table>
          <caption class="solo-lector">Historial de corridas</caption>
          <thead><tr>
            <th scope="col">#</th><th scope="col">Fecha</th><th scope="col">Usuario</th><th scope="col">Rutas</th>
            <th scope="col">Buses</th><th scope="col">Costo</th><th scope="col">Dif. vs. actual</th><th scope="col">Acciones</th>
          </tr></thead>
          <tbody>
            @for (c of lista.items(); track c.id) {
              <tr>
                <td>{{ c.id }}</td><td>{{ c.creada | date: 'dd/MM/yyyy HH:mm' }}</td><td>{{ c.usuario }}</td>
                <td>{{ c.resumen.rutas }}</td><td>{{ c.resumen.buses }}</td>
                <td>{{ c.resumen.costo_total | number: '1.0-0' }}</td>
                <td>{{ c.resumen.diferencia_pct == null ? '—' : (c.resumen.diferencia_pct | number: '1.1-1') + ' %' }}</td>
                <td class="acciones"><div>
                  <a class="btn" [routerLink]="['/corridas', c.id]" [attr.aria-label]="'Ver corrida ' + c.id">Ver</a>
                  @if (auth.esAdmin()) {
                    <button type="button" class="btn peligro" [attr.aria-label]="'Borrar corrida ' + c.id" (click)="borrar(c)">Borrar</button>
                  }
                </div></td>
              </tr>
            }
          </tbody>
        </table>
      </div>
    }
    <app-paginador [pagina]="lista.pagina()" [porPagina]="lista.porPagina" [total]="lista.total()" (cambiar)="lista.irA($event)" />
  `,
})
export class Corridas implements OnInit {
  auth = inject(AuthService);
  private api = inject(ApiService);
  private avisos = inject(NotificacionesService);
  lista = new ListaPaginada<Corrida>('/corridas', 25);

  ngOnInit() { this.lista.buscar(); }

  borrar(c: Corrida) {
    if (!confirm(`¿Borrar la corrida #${c.id}?`)) return;
    this.api.delete(`/corridas/${c.id}`).subscribe({
      next: () => { this.avisos.ok('Corrida borrada.'); this.lista.cargar(); }, // retrocede sola si la página quedó vacía
      error: (e: ApiError) => this.avisos.error(e.message),
    });
  }
}
