import { Component, DestroyRef, ElementRef, Injector, OnInit, afterNextRender, inject, input, runInInjectionContext, signal, viewChild } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { ApiError, ApiService } from '../core/api.service';
import { ListaPaginada } from '../core/lista';
import { NotificacionesService } from '../core/notificaciones.service';
import { Paginador } from './paginador';

export interface Columna { clave: string; titulo: string; fmt?: (fila: any) => string; }
export interface Opcion { valor: unknown; texto: string; }
export interface Campo {
  clave: string;
  etiqueta: string;
  tipo: 'text' | 'number' | 'password' | 'select' | 'checkbox';
  requerido?: boolean;
  opciones?: Opcion[];
  step?: string;
  ayuda?: string;
  /** Solo se envia al crear (no editable despues). */
  soloCrear?: boolean;
  porDefecto?: unknown;
}

type Fila = Record<string, any>;

const nombreDe = (f: Fila) => String(f['nombre'] ?? f['tipo'] ?? f['usuario'] ?? f['identificacion'] ?? f['id']);

/** Tabla CRUD reutilizable: paginado servidor, busqueda, filtro activo, dialogo y confirmacion. */
@Component({
  selector: 'app-crud-table',
  imports: [FormsModule, Paginador],
  template: `
    <header class="barra">
      <h1>{{ titulo() }}</h1>
      @if (puedeEscribir()) {
        <button type="button" class="btn primario" (click)="abrir(null)">Nuevo</button>
      }
    </header>

    <form class="filtros" role="search" (submit)="$event.preventDefault(); buscar()">
      <label>Buscar
        <input type="search" name="q" [ngModel]="q()" (ngModelChange)="q.set($event)" />
      </label>
      @if (filtroActivo()) {
        <label>Estado
          <select name="activo" [ngModel]="activo()" (ngModelChange)="activo.set($event); buscar()">
            <option value="">Todos</option>
            <option value="true">Activos</option>
            <option value="false">Inactivos</option>
          </select>
        </label>
      }
      <button type="submit" class="btn">Buscar</button>
    </form>

    <div aria-live="polite">
      @if (lista.cargando()) {
        <p class="estado">Cargando…</p>
      } @else if (lista.error()) {
        <p class="estado error" role="alert">{{ lista.error() }}
          <button type="button" class="btn" (click)="lista.cargar()">Reintentar</button></p>
      } @else if (lista.items().length === 0) {
        <p class="estado">No hay registros.</p>
      }
    </div>

    @if (!lista.cargando() && !lista.error() && lista.items().length) {
      <div class="tabla-wrap">
        <table>
          <caption class="solo-lector">{{ titulo() }}</caption>
          <thead>
            <tr>
              @for (c of columnas(); track c.clave) { <th scope="col">{{ c.titulo }}</th> }
              @if (puedeEscribir()) { <th scope="col">Acciones</th> }
            </tr>
          </thead>
          <tbody>
            @for (f of lista.items(); track f['id']) {
              <tr>
                @for (c of columnas(); track c.clave) { <td>{{ celda(f, c) }}</td> }
                @if (puedeEscribir()) {
                  <td class="acciones"><div>
                    <button type="button" class="btn" [attr.aria-label]="'Editar ' + singular() + ' ' + nombreFila()(f)" (click)="abrir(f)">Editar</button>
                    @if (!sinBorrar()) {
                      <button type="button" class="btn peligro" [attr.aria-label]="'Borrar ' + singular() + ' ' + nombreFila()(f)" (click)="pedirBorrar(f)">Borrar</button>
                    }
                  </div></td>
                }
              </tr>
            }
          </tbody>
        </table>
      </div>
    }
    <app-paginador [pagina]="lista.pagina()" [porPagina]="lista.porPagina" [total]="lista.total()" (cambiar)="lista.irA($event)" />

    <dialog #dlg aria-labelledby="dlg-titulo" (close)="editando.set(undefined)">
      @if (editando() !== undefined) {
        <form (submit)="$event.preventDefault(); guardar()" novalidate>
          <h2 id="dlg-titulo">{{ editando() ? 'Editar' : 'Nuevo' }} · {{ titulo() }}</h2>
          @if (errorForm()) { <p class="error" role="alert">{{ errorForm() }}</p> }
          @for (c of campos(); track c.clave) {
            @if (!editando() || !c.soloCrear) {
              <div class="campo">
                @if (c.tipo === 'checkbox') {
                  <label class="inline">
                    <input type="checkbox" [id]="'f-' + c.clave" [name]="c.clave"
                      [ngModel]="valores()[c.clave]" (ngModelChange)="poner(c.clave, $event)" />
                    {{ c.etiqueta }}
                  </label>
                } @else {
                  <label [for]="'f-' + c.clave">{{ c.etiqueta }}@if (c.requerido) { <span aria-hidden="true"> *</span> }</label>
                  @if (c.tipo === 'select') {
                    <select [id]="'f-' + c.clave" [name]="c.clave" [ngModel]="valores()[c.clave]"
                      (ngModelChange)="poner(c.clave, $event)" [attr.aria-invalid]="errores()[c.clave] ? true : null"
                      [attr.aria-required]="c.requerido ? true : null"
                      [attr.aria-describedby]="errores()[c.clave] ? 'e-' + c.clave : null">
                      @if (!c.requerido) { <option [ngValue]="null">— Ninguno —</option> }
                      @for (o of opcionesDe(c); track o.valor) { <option [ngValue]="o.valor">{{ o.texto }}</option> }
                    </select>
                  } @else {
                    <input [id]="'f-' + c.clave" [name]="c.clave" [type]="c.tipo" [attr.step]="c.step"
                      [autocomplete]="c.tipo === 'password' ? 'new-password' : 'off'"
                      [ngModel]="valores()[c.clave]" (ngModelChange)="poner(c.clave, $event)"
                      [attr.aria-required]="c.requerido ? true : null"
                      [attr.aria-invalid]="errores()[c.clave] ? true : null"
                      [attr.aria-describedby]="errores()[c.clave] ? 'e-' + c.clave : null" />
                  }
                }
                @if (c.ayuda) { <small>{{ c.ayuda }}</small> }
                @if (errores()[c.clave]) { <small class="error" [id]="'e-' + c.clave">{{ errores()[c.clave] }}</small> }
              </div>
            }
          }
          <div class="dialogo-acciones">
            <button type="button" class="btn" (click)="cerrarForm()">Cancelar</button>
            <button type="submit" class="btn primario" [disabled]="guardando()">
              {{ guardando() ? 'Guardando…' : 'Guardar' }}
            </button>
          </div>
        </form>
      }
    </dialog>

    <dialog #conf aria-labelledby="conf-titulo" (close)="porBorrar.set(null)">
      <h2 id="conf-titulo">Confirmar borrado</h2>
      <p>¿Borrar este registro? Esta acción no se puede deshacer.</p>
      <div class="dialogo-acciones">
        <button type="button" class="btn" autofocus (click)="cerrar(confRef())">Cancelar</button>
        <button type="button" class="btn peligro" [disabled]="borrando()" (click)="borrar()">
          {{ borrando() ? 'Borrando…' : 'Borrar' }}
        </button>
      </div>
    </dialog>
  `,
})
export class CrudTable implements OnInit {
  titulo = input.required<string>();
  ruta = input.required<string>();
  columnas = input.required<Columna[]>();
  campos = input.required<Campo[]>();
  filtroActivo = input(true);
  puedeEscribir = input(false);
  sinBorrar = input(false);
  /** Para los aria-label de las acciones: "Editar finca YARUMO". */
  singular = input('registro');
  nombreFila = input<(f: Fila) => string>(nombreDe);

  private api = inject(ApiService);
  private avisos = inject(NotificacionesService);
  private injector = inject(Injector);
  private destroyRef = inject(DestroyRef);
  private host = inject<ElementRef<HTMLElement>>(ElementRef);
  private dlgRef = viewChild.required<ElementRef<HTMLDialogElement>>('dlg');
  private confRef = viewChild.required<ElementRef<HTMLDialogElement>>('conf');

  // Se crea en ngOnInit (la ruta es un input) pero dentro del contexto de inyeccion del componente.
  lista!: ListaPaginada<Fila>;

  q = signal('');
  activo = signal('');

  /** undefined = cerrado, null = nuevo, objeto = editando esa fila. */
  editando = signal<Fila | null | undefined>(undefined);
  valores = signal<Fila>({});
  errores = signal<Record<string, string>>({});
  errorForm = signal('');
  guardando = signal(false);
  porBorrar = signal<Fila | null>(null);
  borrando = signal(false);

  ngOnInit() {
    this.lista = runInInjectionContext(this.injector, () => new ListaPaginada<Fila>(this.ruta(), 25));
    this.buscar();
  }

  /** Copia lo escrito a filtros "aplicados"; paginar reutiliza esos filtros, no lo que haya en pantalla. */
  buscar() {
    this.lista.buscar({ q: this.q().trim(), activo: this.filtroActivo() ? this.activo() : '' });
  }

  celda(f: Fila, c: Columna): string {
    const v = c.fmt ? c.fmt(f) : f[c.clave];
    if (typeof v === 'boolean') return v ? 'Sí' : 'No';
    return v === null || v === undefined ? '' : String(v);
  }

  /** Opciones del select; si el valor actual no esta en la lista (p. ej. mas alla de lo cargado) se agrega. */
  opcionesDe(c: Campo): Opcion[] {
    const ops = c.opciones ?? [];
    const actual = this.valores()[c.clave];
    return actual == null || ops.some((o) => o.valor === actual) ? ops : [...ops, { valor: actual, texto: `#${actual}` }];
  }

  private mostrar(d: ElementRef<HTMLDialogElement>) {
    const el = d.nativeElement;
    // showModal real solo se probo en navegador; jsdom no lo implementa y usamos el atributo
    if (typeof el.showModal === 'function') el.showModal();
    else el.setAttribute('open', '');
  }
  cerrar(d: ElementRef<HTMLDialogElement>) {
    const el = d.nativeElement;
    if (typeof el.close === 'function') el.close();
    else el.removeAttribute('open');
    if (d === this.dlgRef()) this.editando.set(undefined);
    else this.porBorrar.set(null);
  }
  cerrarForm() { this.cerrar(this.dlgRef()); }

  private enfocarPrimero(selector: string) {
    afterNextRender(() => this.host.nativeElement.querySelector<HTMLElement>(selector)?.focus(), { injector: this.injector });
  }

  abrir(fila: Fila | null) {
    const v: Fila = {};
    for (const c of this.campos()) {
      v[c.clave] = fila ? (c.tipo === 'password' ? '' : (fila[c.clave] ?? null)) : (c.porDefecto ?? (c.tipo === 'checkbox' ? true : null));
    }
    this.valores.set(v);
    this.errores.set({});
    this.errorForm.set('');
    this.editando.set(fila);
    this.mostrar(this.dlgRef());
    this.enfocarPrimero('dialog[open] form input, dialog[open] form select');
  }
  poner(clave: string, valor: unknown) {
    this.valores.update((v) => ({ ...v, [clave]: valor }));
  }

  guardar() {
    if (this.guardando()) return;
    const fila = this.editando();
    const errs: Record<string, string> = {};
    const cuerpo: Fila = {};
    for (const c of this.campos()) {
      if (fila && c.soloCrear) continue;
      let v = this.valores()[c.clave];
      // las contrasenas no se recortan: los espacios cuentan
      if (typeof v === 'string' && c.tipo !== 'password') v = v.trim();
      // [type] dinamico no activa el accessor numerico de ngModel: llega texto, el API espera numero
      if (c.tipo === 'number' && typeof v === 'string') v = v === '' ? null : Number(v);
      const vacio = v === null || v === undefined || v === '';
      if (c.requerido && vacio && !(c.tipo === 'password' && fila)) errs[c.clave] = 'Este campo es obligatorio.';
      if (c.tipo === 'password' && vacio) continue; // al editar, vacio = no cambiar
      if (fila && !(c.tipo === 'password') && (fila[c.clave] ?? null) === (v === '' ? null : v)) continue; // PATCH solo con cambios
      cuerpo[c.clave] = v === '' ? null : v;
    }
    this.errores.set(errs);
    const primero = Object.keys(errs)[0];
    if (primero) {
      this.enfocarPrimero(`#f-${primero}`);
      return;
    }
    if (fila && !Object.keys(cuerpo).length) {
      this.cerrarForm();
      this.avisos.ok('No hubo cambios.');
      return;
    }

    this.guardando.set(true);
    this.errorForm.set('');
    const peticion = fila ? this.api.patch(`${this.ruta()}/${fila['id']}`, cuerpo) : this.api.post(this.ruta(), cuerpo);
    peticion.pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: () => {
        this.guardando.set(false);
        this.cerrarForm();
        this.avisos.ok(fila ? 'Cambios guardados.' : 'Registro creado.');
        this.lista.cargar();
      },
      error: (e: ApiError) => {
        this.guardando.set(false);
        const claves = new Set(this.campos().map((c) => c.clave));
        const enForm = e.status === 422 ? Object.fromEntries(Object.entries(e.porCampo()).filter(([k]) => claves.has(k))) : {};
        const sueltos = (e.detalle ?? []).filter((d) => !claves.has(d.campo)).map((d) => `${d.campo}: ${d.mensaje}`);
        this.errores.set(enForm);
        const hayCampos = Object.keys(enForm).length > 0;
        const base = hayCampos && !sueltos.length ? 'Revisa los campos marcados.' : e.message;
        this.errorForm.set([base, ...sueltos.filter((s) => !base.includes(s))].join(' '));
        const primero = Object.keys(enForm)[0];
        this.enfocarPrimero(primero ? `#f-${primero}` : 'dialog[open] [role=alert]');
      },
    });
  }

  pedirBorrar(f: Fila) {
    this.porBorrar.set(f);
    this.mostrar(this.confRef());
    this.host.nativeElement.querySelector<HTMLElement>('dialog[open] [autofocus]')?.focus();
  }
  borrar() {
    const f = this.porBorrar();
    if (!f || this.borrando()) return;
    this.borrando.set(true);
    this.api.delete(`${this.ruta()}/${f['id']}`).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: () => {
        this.borrando.set(false);
        this.cerrar(this.confRef());
        this.avisos.ok('Registro borrado.');
        this.lista.cargar(); // ListaPaginada retrocede si la pagina quedo vacia
      },
      error: (e: ApiError) => {
        this.borrando.set(false);
        this.cerrar(this.confRef());
        this.avisos.error(e.message);
      },
    });
  }
}
