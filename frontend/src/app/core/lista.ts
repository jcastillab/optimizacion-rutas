import { DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { EMPTY, Subject, catchError, switchMap, tap } from 'rxjs';
import { ApiError, ApiService, Params } from './api.service';

/**
 * Lista paginada por servidor. Cada carga cancela la anterior (switchMap), asi que una respuesta
 * vieja nunca pisa a una nueva; paginar usa los filtros *aplicados* en la ultima busqueda.
 * Crear dentro de un contexto de inyeccion (campo de un componente).
 */
export class ListaPaginada<T> {
  private api = inject(ApiService);
  readonly items = signal<T[]>([]);
  readonly total = signal(0);
  readonly pagina = signal(1);
  readonly cargando = signal(false);
  readonly error = signal('');
  readonly paginas = computed(() => Math.max(1, Math.ceil(this.total() / this.porPagina)));
  private aplicados: Params = {};
  private disparo = new Subject<void>();

  constructor(
    private ruta: string,
    readonly porPagina = 25,
  ) {
    this.disparo
      .pipe(
        tap(() => {
          this.cargando.set(true);
          this.error.set('');
        }),
        switchMap(() =>
          this.api.lista<T>(this.ruta, { ...this.aplicados, pagina: this.pagina(), por_pagina: this.porPagina }).pipe(
            catchError((e: ApiError) => {
              this.error.set(e.message);
              this.cargando.set(false);
              return EMPTY;
            }),
          ),
        ),
        takeUntilDestroyed(inject(DestroyRef)),
      )
      .subscribe((r) => {
        this.items.set(r.items);
        this.total.set(r.total);
        this.cargando.set(false);
        // la pagina quedo fuera de rango (p. ej. se borro el ultimo registro de la ultima pagina)
        if (this.pagina() > this.paginas()) {
          this.pagina.set(this.paginas());
          this.cargar();
        }
      });
  }

  cargar() {
    this.disparo.next();
  }
  /** Aplica filtros nuevos y vuelve a la pagina 1. */
  buscar(filtros: Params = {}) {
    this.aplicados = { ...filtros };
    this.pagina.set(1);
    this.cargar();
  }
  irA(p: number) {
    this.pagina.set(p);
    this.cargar();
  }
}
