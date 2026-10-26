import { Injectable, signal } from '@angular/core';

export interface Aviso { id: number; tipo: 'ok' | 'error'; texto: string; }

@Injectable({ providedIn: 'root' })
export class NotificacionesService {
  readonly avisos = signal<Aviso[]>([]);
  private n = 0;
  private timers = new Map<number, ReturnType<typeof setTimeout>>();
  private tipos = new Map<number, Aviso['tipo']>();
  ok(texto: string) { this.agregar('ok', texto); }
  error(texto: string) { this.agregar('error', texto); }
  cerrar(id: number) {
    this.pausar(id);
    this.tipos.delete(id);
    this.avisos.update((a) => a.filter((x) => x.id !== id));
  }
  /** Con el mouse o el foco encima, el aviso no se cierra solo. */
  pausar(id: number) {
    clearTimeout(this.timers.get(id));
    this.timers.delete(id);
  }
  reanudar(id: number) {
    this.pausar(id);
    if (this.tipos.has(id)) {
      this.timers.set(id, setTimeout(() => this.cerrar(id), this.tipos.get(id) === 'error' ? 12000 : 7000));
    }
  }
  private agregar(tipo: Aviso['tipo'], texto: string) {
    const id = ++this.n;
    this.tipos.set(id, tipo);
    this.avisos.update((a) => [...a, { id, tipo, texto }]);
    this.reanudar(id);
  }
}
