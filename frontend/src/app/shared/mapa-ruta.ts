import { Component, computed, inject, input, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { catchError, map, of } from 'rxjs';
import { ApiService } from '../core/api.service';
import { Finca, Pagina, RutaSimulada } from '../core/models';

const W = 800, H = 500;

/** Proyecta coordenadas a un lienzo (sin fondo de mapa): escala única y longitud corregida por la latitud media. */
export function proyectar(puntos: { lat: number; lon: number }[], ancho = W, alto = H, margen = 60): { x: number; y: number }[] {
  if (!puntos.length) return [];
  const k = Math.cos((puntos.reduce((s, p) => s + p.lat, 0) / puntos.length) * Math.PI / 180);
  const xs = puntos.map((p) => p.lon * k), ys = puntos.map((p) => p.lat);
  const minX = Math.min(...xs), minY = Math.min(...ys);
  const rangoX = Math.max(...xs) - minX, rangoY = Math.max(...ys) - minY;
  const escala = Math.min((ancho - 2 * margen) / (rangoX || 1), (alto - 2 * margen) / (rangoY || 1));
  const offX = (ancho - rangoX * escala) / 2, offY = (alto - rangoY * escala) / 2;
  return puntos.map((_, i) => ({ x: offX + (xs[i] - minX) * escala, y: alto - offY - (ys[i] - minY) * escala }));
}

@Component({
  selector: 'app-mapa-ruta',
  template: `
    @if (!rutas().length) {
      <p>Sin rutas para dibujar.</p>
    } @else {
      <p>
        <label>Ruta
          <select (change)="elegir($event)">
            @for (r of rutas(); track r.ruta_simulada) {
              <option [value]="r.ruta_simulada" [selected]="r.ruta_simulada === actual()?.ruta_simulada">
                Ruta {{ r.ruta_simulada }} · {{ r.finca_nombre ?? '#' + r.finca_id }} · {{ r.paraderos.length }} paraderos
              </option>
            }
          </select>
        </label>
      </p>
      @if (dibujo(); as d) {
        <svg class="mapa-ruta" [attr.viewBox]="'0 0 ' + W + ' ' + H" role="img" [attr.aria-label]="'Mapa de la ruta ' + actual()?.ruta_simulada">
          @if (d.linea) { <polyline [attr.points]="d.linea" fill="none" stroke="#047E77" stroke-width="4" /> }
          @if (d.tramoFinca) { <polyline [attr.points]="d.tramoFinca" fill="none" stroke="#E64393" stroke-width="3" stroke-dasharray="10 8" /> }
          @for (p of d.paradas; track p.n) {
            <g>
              <title>{{ p.n }}. {{ p.nombre }}</title>
              <circle [attr.cx]="p.x" [attr.cy]="p.y" r="18" fill="#00B2A9" stroke="#FFFFFF" stroke-width="3" />
              <text [attr.x]="p.x" [attr.y]="p.y + 6" text-anchor="middle" fill="#FFFFFF" font-size="18" font-weight="700">{{ p.n }}</text>
              <text [attr.x]="p.x + (p.x > W / 2 ? -28 : 28)" [attr.y]="p.y + 6" [attr.text-anchor]="p.x > W / 2 ? 'end' : 'start'" fill="#FFFFFF" font-size="16">{{ p.nombre }}</text>
            </g>
          }
          @if (d.finca) {
            <g>
              <title>Finca {{ d.finca.nombre }}</title>
              <rect [attr.x]="d.finca.x - 20" [attr.y]="d.finca.y - 20" width="40" height="40" fill="#E64393" stroke="#FFFFFF" stroke-width="3" />
              <text [attr.x]="d.finca.x" [attr.y]="d.finca.y + 40" text-anchor="middle" fill="#FFFFFF" font-size="18" font-weight="700">{{ d.finca.nombre }}</text>
            </g>
          }
        </svg>
        <p class="nota">Orden de recogida: números 1 a {{ d.paradas.length }}. Línea continua: recorrido entre paraderos; punteada: último tramo a la finca. Coordenadas en línea recta, sin calles.</p>
      } @else {
        <p class="nota">La finca de esta ruta no tiene coordenadas en el catálogo.</p>
      }
    }
  `,
})
export class MapaRuta {
  rutas = input.required<RutaSimulada[]>();
  W = W;
  H = H;
  private api = inject(ApiService);
  private fincas = toSignal(
    this.api.get<Pagina<Finca>>('/fincas', { por_pagina: 200 }).pipe(map((p) => p.items), catchError(() => of([] as Finca[]))),
    { initialValue: [] as Finca[] },
  );
  private elegida = signal<number | null>(null);
  actual = computed(() => this.rutas().find((r) => r.ruta_simulada === (this.elegida() ?? this.rutas()[0]?.ruta_simulada)) ?? this.rutas()[0]);

  dibujo = computed(() => {
    const r = this.actual();
    if (!r) return null;
    const finca = this.fincas().find((f) => f.id === r.finca_id) ?? null;
    const pts = [...r.paraderos, ...(finca ? [finca] : [])];
    const xy = proyectar(pts);
    const paradas = r.paraderos.map((p, i) => ({ n: i + 1, nombre: p.nombre, x: xy[i].x, y: xy[i].y }));
    const ultimo = paradas[paradas.length - 1];
    const f = finca ? { nombre: finca.nombre, x: xy[xy.length - 1].x, y: xy[xy.length - 1].y } : null;
    const linea = paradas.map((p) => `${p.x},${p.y}`).join(' ');
    const tramoFinca = f && ultimo ? `${ultimo.x},${ultimo.y} ${f.x},${f.y}` : '';
    return { paradas, finca: f, linea, tramoFinca };
  });

  elegir(e: Event) {
    this.elegida.set(Number((e.target as HTMLSelectElement).value));
  }
}
