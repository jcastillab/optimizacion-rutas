import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ApiError, ApiService } from '../core/api.service';
import { Corrida } from '../core/models';
import { NotificacionesService } from '../core/notificaciones.service';
import { CorridaResultado } from '../shared/corrida-resultado';

@Component({
  selector: 'app-simulador',
  imports: [FormsModule, CorridaResultado],
  template: `
    <h1>Simulador de rutas</h1>
    <form class="filtros" (submit)="$event.preventDefault(); ejecutar()" novalidate>
      <label>Velocidad (km/h)
        <input type="number" name="velocidad_kmh" min="1" step="any" [(ngModel)]="velocidad"
          [attr.aria-invalid]="errores()['velocidad_kmh'] ? true : null" [attr.aria-describedby]="errores()['velocidad_kmh'] ? 'e-v' : null" />
        @if (errores()['velocidad_kmh']) { <small class="error" id="e-v">{{ errores()['velocidad_kmh'] }}</small> }
      </label>
      <label>Tiempo máximo de viaje (min)
        <input type="number" name="tiempo_max_min" min="1" step="any" [(ngModel)]="tiempo"
          [attr.aria-invalid]="errores()['tiempo_max_min'] ? true : null" [attr.aria-describedby]="errores()['tiempo_max_min'] ? 'e-t' : null" />
        @if (errores()['tiempo_max_min']) { <small class="error" id="e-t">{{ errores()['tiempo_max_min'] }}</small> }
      </label>
      <button type="submit" class="btn primario" [disabled]="cargando()">
        {{ cargando() ? 'Calculando…' : 'Ejecutar simulación' }}
      </button>
    </form>
    <div aria-live="polite">
      @if (cargando()) { <p class="estado">Calculando rutas, puede tardar unos segundos…</p> }
      @if (error()) { <p class="estado error" role="alert">{{ error() }}</p> }
    </div>
    @if (corrida(); as c) {
      <p class="nota">Corrida #{{ c.id }} guardada en el historial.</p>
      <app-corrida-resultado [corrida]="c" />
    }
  `,
})
export class Simulador {
  private api = inject(ApiService);
  private avisos = inject(NotificacionesService);
  velocidad: number | null = 25;
  tiempo: number | null = 60;
  corrida = signal<Corrida | null>(null);
  cargando = signal(false);
  error = signal('');
  errores = signal<Record<string, string>>({});

  ejecutar() {
    if (this.cargando()) return;
    // las claves vacias se omiten para que el servidor use sus valores por defecto
    const cuerpo: Record<string, number> = {};
    if (this.velocidad != null) cuerpo['velocidad_kmh'] = this.velocidad;
    if (this.tiempo != null) cuerpo['tiempo_max_min'] = this.tiempo;
    this.cargando.set(true);
    this.error.set('');
    this.errores.set({});
    this.api.post<Corrida>('/simulador/ejecutar', cuerpo).subscribe({
      next: (c) => { this.corrida.set(c); this.cargando.set(false); this.avisos.ok('Simulación terminada.'); },
      error: (e: ApiError) => {
        const porCampo = e.porCampo();
        const propios = ['velocidad_kmh', 'tiempo_max_min'];
        this.errores.set(Object.fromEntries(Object.entries(porCampo).filter(([k]) => propios.includes(k))));
        const sueltos = (e.detalle ?? []).filter((d) => !propios.includes(d.campo)).map((d) => `${d.campo}: ${d.mensaje}`);
        this.error.set([e.message, ...sueltos].join(' '));
        this.cargando.set(false);
      },
    });
  }
}
