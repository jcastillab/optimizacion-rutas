import { Component, computed, input, output } from '@angular/core';

@Component({
  selector: 'app-paginador',
  template: `
    <nav class="paginador" aria-label="Paginación">
      <span aria-live="polite" aria-atomic="true">{{ total() === 1 ? '1 registro' : total() + ' registros' }} · página {{ pagina() }} de {{ paginas() }}</span>
      <button type="button" class="btn" [disabled]="pagina() <= 1" (click)="cambiar.emit(pagina() - 1)">Anterior</button>
      <button type="button" class="btn" [disabled]="pagina() >= paginas()" (click)="cambiar.emit(pagina() + 1)">Siguiente</button>
    </nav>
  `,
})
export class Paginador {
  pagina = input.required<number>();
  porPagina = input.required<number>();
  total = input.required<number>();
  cambiar = output<number>();
  paginas = computed(() => Math.max(1, Math.ceil(this.total() / this.porPagina())));
}
