import { Injectable, inject, signal } from '@angular/core';
import { EMPTY, Observable, expand, reduce } from 'rxjs';
import { ApiService } from './api.service';

export interface Ref { id: number; nombre: string; }
type Clave = 'fincas' | 'paraderos';
const CLAVES: Clave[] = ['fincas', 'paraderos'];

/** Fincas y paraderos completos (pagina hasta traer todo), en cache; se refrescan tras cualquier escritura. */
@Injectable({ providedIn: 'root' })
export class CatalogosService {
  private api = inject(ApiService);
  readonly fincas = signal<Ref[]>([]);
  readonly paraderos = signal<Ref[]>([]);
  private pedido = new Set<Clave>();

  constructor() {
    this.api.escrituras.subscribe((ruta) => {
      for (const k of CLAVES) {
        if (ruta.startsWith(`/${k}`) || ruta.startsWith('/importar')) {
          this.pedido.delete(k);
          this.asegurar(k);
        }
      }
    });
  }

  /** Pide el catalogo si aun no se pidio (o si se invalido). Sin argumentos, los dos. */
  asegurar(...claves: Clave[]) {
    for (const k of claves.length ? claves : CLAVES) {
      if (this.pedido.has(k)) continue;
      this.pedido.add(k);
      this.todo(`/${k}`).subscribe({
        next: (r) => (k === 'fincas' ? this.fincas : this.paraderos).set(r),
        error: () => this.pedido.delete(k), // se reintenta en el proximo uso
      });
    }
  }

  nombre(lista: Ref[], id: number | null | undefined) {
    return id == null ? '' : (lista.find((x) => x.id === id)?.nombre ?? `#${id}`);
  }

  private todo(ruta: string): Observable<Ref[]> {
    const pide = (pagina: number) => this.api.lista<Ref>(ruta, { pagina, por_pagina: 200 });
    return pide(1).pipe(
      expand((r) => (r.pagina * r.por_pagina < r.total ? pide(r.pagina + 1) : EMPTY)),
      reduce((acc, r) => [...acc, ...r.items], [] as Ref[]),
    );
  }
}
