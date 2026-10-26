import { DatePipe } from '@angular/common';
import { Component, inject, input } from '@angular/core';
import { toObservable, toSignal } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { catchError, map, of, startWith, switchMap } from 'rxjs';
import { ApiError, ApiService } from '../core/api.service';
import { Corrida } from '../core/models';
import { CorridaResultado } from '../shared/corrida-resultado';

interface Estado { c: Corrida | null; e: string; }

@Component({
  selector: 'app-corrida-detalle',
  imports: [DatePipe, RouterLink, CorridaResultado],
  template: `
    <p><a [routerLink]="['/corridas']">← Volver a corridas</a></p>
    <div aria-live="polite">
      @if (estado().e) { <p class="estado error" role="alert">{{ estado().e }}</p> }
      @else if (!estado().c) { <p class="estado">Cargando…</p> }
    </div>
    @if (estado().c; as c) {
      <h1>Corrida #{{ c.id }}</h1>
      <p class="nota">{{ c.creada | date: 'dd/MM/yyyy HH:mm' }} · {{ c.usuario }}</p>
      <app-corrida-resultado [corrida]="c" />
    }
  `,
})
export class CorridaDetalle {
  id = input.required<string>(); // desde la ruta (withComponentInputBinding)
  private api = inject(ApiService);
  // switchMap: si cambia :id se cancela la carga anterior y se vuelve a pedir
  estado = toSignal(
    toObservable(this.id).pipe(
      switchMap((id) =>
        this.api.get<Corrida>(`/corridas/${encodeURIComponent(id)}`).pipe(
          map((c): Estado => ({ c, e: '' })),
          catchError((e: ApiError) => of<Estado>({ c: null, e: e.message })),
          startWith<Estado>({ c: null, e: '' }),
        ),
      ),
    ),
    { initialValue: { c: null, e: '' } as Estado },
  );
}
