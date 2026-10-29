import { DecimalPipe } from '@angular/common';
import { Component, computed, input } from '@angular/core';
import { Corrida } from '../core/models';
import { MapaRuta } from './mapa-ruta';

@Component({
  selector: 'app-corrida-resultado',
  imports: [DecimalPipe, MapaRuta],
  template: `
    @let c = corrida();
    @let dif = c.resumen.diferencia_pct;
    <section aria-labelledby="res-t">
      <h2 id="res-t">Resumen</h2>
      @if ((c.resumen.advertencias ?? []).length) {
        <div class="estado aviso" role="note" aria-label="Advertencias sobre este resultado">
          <strong>Antes de leer las cifras</strong>
          <ul>@for (a of c.resumen.advertencias; track $index) { <li>{{ a }}</li> }</ul>
        </div>
      }
      <dl class="kpis">
        <div><dt>Rutas</dt><dd>{{ c.resumen.rutas }}</dd></div>
        <div><dt>Buses</dt><dd>{{ c.resumen.buses }}</dd></div>
        <div><dt>Personas</dt><dd>{{ c.resumen.personas }}</dd></div>
        <div><dt>Costo propuesto</dt><dd>{{ c.resumen.costo_total | number: '1.0-0' }}</dd></div>
        <div><dt>Costo red actual</dt><dd>{{ c.resumen.costo_red_actual | number: '1.0-0' }}</dd></div>
        <div>
          <dt>Comparación orientativa con la red actual</dt>
          <dd [class.mejor]="dif != null && dif < 0" [class.peor]="dif != null && dif > 0">
            @if (dif == null) { No comparable } @else {
              {{ dif > 0 ? '+' : '' }}{{ dif | number: '1.1-1' }} %
              <span class="solo-lector">{{ dif > 0 ? '(más caro)' : dif < 0 ? '(más barato)' : '(igual)' }}</span>
            }
          </dd>
        </div>
        <div><dt>Sin servicio</dt><dd>{{ c.resumen.personas_sin_servicio }}</dd></div>
      </dl>
      @if ((c.resumen.personas_sin_paradero ?? 0) > 0) {
        <p class="estado aviso" role="status">
          {{ c.resumen.personas_sin_paradero }} persona(s) no tienen paradero asignado y no entraron en la simulación.
        </p>
      }
      <p class="nota">Parámetros: {{ c.parametros.velocidad_kmh }} km/h, máximo {{ c.parametros.tiempo_max_min }} min.</p>
    </section>

    <section aria-labelledby="rutas-t">
      <h2 id="rutas-t">Rutas propuestas</h2>
      <div class="tabla-wrap">
        <table>
          <caption class="solo-lector">Rutas propuestas por la simulación</caption>
          <thead><tr>
            <th scope="col">Ruta</th><th scope="col">Finca</th><th scope="col">Paraderos</th><th scope="col">Personas</th>
            <th scope="col">Km</th><th scope="col">Min. máx.</th><th scope="col">Bus</th><th scope="col">Cant.</th><th scope="col">Costo</th>
          </tr></thead>
          <tbody>
            @for (r of c.rutas ?? []; track r.ruta_simulada) {
              <tr>
                <td>{{ r.ruta_simulada }}</td><td>{{ r.finca_nombre ?? '#' + r.finca_id }}</td>
                <td>{{ nombres(r.paraderos) }} ({{ r.paraderos.length }})</td><td>{{ r.personas }}</td>
                <td>{{ r.km | number: '1.1-1' }}</td><td>{{ r.minutos_max | number: '1.0-1' }}</td>
                <td>{{ r.tipo_bus }} ({{ r.capacidad }})</td><td>{{ r.buses }}</td>
                <td>{{ r.costo_total | number: '1.0-0' }}</td>
              </tr>
            } @empty {
              <tr><td colspan="9">Sin rutas.</td></tr>
            }
          </tbody>
        </table>
      </div>
    </section>

    <section aria-labelledby="mapa-t">
      <h2 id="mapa-t">Mapa de la ruta</h2>
      <app-mapa-ruta [rutas]="c.rutas ?? []" />
    </section>

    <section aria-labelledby="sin-t">
      <h2 id="sin-t">Sin servicio</h2>
      @if ((c.sin_servicio ?? []).length === 0) {
        <p>Todas las personas tienen servicio.</p>
      } @else {
        <ul>
          @for (s of c.sin_servicio; track $index) {
            <li>{{ s.personas }} persona(s) en el paradero #{{ s.paradero_id }}, finca {{ fincas().get(s.finca_id) ?? '#' + s.finca_id }}</li>
          }
        </ul>
      }
    </section>
  `,
})
export class CorridaResultado {
  corrida = input.required<Corrida>();
  // la corrida es un snapshot: los nombres salen de ella, no de los catálogos vivos
  fincas = computed(() => new Map((this.corrida().rutas ?? []).filter((r) => r.finca_nombre).map((r) => [r.finca_id, r.finca_nombre as string])));
  nombres = (p: { nombre: string }[]) => p.map((x) => x.nombre).join(', ');
}
