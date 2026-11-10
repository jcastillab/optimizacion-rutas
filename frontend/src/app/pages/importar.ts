import { Component, inject, signal } from '@angular/core';
import { ApiError, ApiService } from '../core/api.service';

export interface ResultadoImportar {
  fincas: { creadas: number; actualizadas: number };
  paraderos: { creadas: number; actualizadas: number };
  personas: { creadas: number; actualizadas: number };
  tipos_bus: { creadas: number; actualizadas: number };
  avisos: string[];
}

@Component({
  selector: 'app-importar',
  template: `
    <h1>Importar datos</h1>
    <p>Lee los Excel y KML locales del servidor y crea las fincas, paraderos, personas y tipos de bus que falten.
      Por defecto no modifica lo que ya existe.</p>
    <div class="campo">
      <label class="inline">
        <input type="checkbox" name="sobrescribir" [checked]="sobrescribir()" (change)="sobrescribir.set($any($event.target).checked)" />
        Sobrescribir registros existentes
      </label>
      <small class="error">Pisa ediciones hechas en la aplicación.</small>
    </div>
    <button type="button" class="btn primario" [disabled]="cargando()" (click)="abrir(conf)">Importar datos del Excel local</button>

    <div aria-live="polite">
      @if (cargando()) { <p class="estado">Importando, puede tardar unos segundos…</p> }
      @if (error()) { <p class="estado error" role="alert">{{ error() }}</p> }
      @if (resultado(); as r) {
        <h2>Resultado</h2>
        @if (r.avisos.length) {
          <div class="estado aviso" role="status">
            <strong>Avisos</strong>
            <ul>@for (a of r.avisos; track $index) { <li>{{ a }}</li> }</ul>
          </div>
        }
        <div class="tabla-wrap">
          <table>
            <caption class="solo-lector">Resultado de la importación</caption>
            <thead><tr><th scope="col">Recurso</th><th scope="col">Creadas</th><th scope="col">Actualizadas</th></tr></thead>
            <tbody>
              @for (f of filas(r); track f[0]) {
                <tr><td>{{ f[0] }}</td><td>{{ f[1].creadas }}</td><td>{{ f[1].actualizadas }}</td></tr>
              }
            </tbody>
          </table>
        </div>
      }
    </div>

    <dialog #conf aria-labelledby="imp-t">
      <h2 id="imp-t">Confirmar importación</h2>
      @if (sobrescribir()) {
        <p><strong>Modo: sobrescribir existentes.</strong> Se pisarán los registros ya existentes con los datos del Excel, incluidas las ediciones hechas en la aplicación.</p>
      } @else {
        <p><strong>Modo: solo crear lo que falta.</strong> Los registros existentes no se modifican.</p>
      }
      <p>¿Continuar?</p>
      <div class="dialogo-acciones">
        <button type="button" class="btn" (click)="cerrar(conf)">Cancelar</button>
        <button type="button" class="btn primario" (click)="cerrar(conf); importar()">Importar</button>
      </div>
    </dialog>
  `,
})
export class Importar {
  private api = inject(ApiService);
  cargando = signal(false);
  error = signal('');
  resultado = signal<ResultadoImportar | null>(null);
  sobrescribir = signal(false);

  filas(r: ResultadoImportar): [string, { creadas: number; actualizadas: number }][] {
    return [['Fincas', r.fincas], ['Paraderos', r.paraderos], ['Personas', r.personas], ['Tipos de bus', r.tipos_bus]];
  }

  // showModal/close no existen en jsdom: respaldo con el atributo "open" (en navegador real se usa la API nativa)
  abrir(d: HTMLDialogElement) {
    if (typeof d.showModal === 'function') d.showModal(); else d.setAttribute('open', '');
  }
  cerrar(d: HTMLDialogElement) {
    if (typeof d.close === 'function') d.close(); else d.removeAttribute('open');
  }

  importar() {
    this.cargando.set(true);
    this.error.set('');
    this.resultado.set(null);
    this.api.post<ResultadoImportar>('/importar/datos-locales', {}, this.sobrescribir() ? { sobrescribir: true } : undefined).subscribe({
      next: (r) => { this.resultado.set(r); this.cargando.set(false); },
      error: (e: ApiError) => { this.error.set(e.message); this.cargando.set(false); },
    });
  }
}
