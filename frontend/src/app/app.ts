import { Component, ElementRef, inject, viewChild } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { filter, skip } from 'rxjs';
import { AuthService } from './core/auth.service';
import { NotificacionesService } from './core/notificaciones.service';

const ENLACES = [
  { ruta: '/', texto: 'Inicio', admin: false },
  { ruta: '/personas', texto: 'Personas', admin: false },
  { ruta: '/paraderos', texto: 'Paraderos', admin: false },
  { ruta: '/fincas', texto: 'Fincas', admin: false },
  { ruta: '/tipos-bus', texto: 'Tipos de bus', admin: false },
  { ruta: '/simulador', texto: 'Simulador', admin: false },
  { ruta: '/corridas', texto: 'Corridas', admin: false },
  { ruta: '/usuarios', texto: 'Usuarios', admin: true },
  { ruta: '/importar', texto: 'Importar', admin: true },
  { ruta: '/eventos', texto: 'Eventos', admin: true },
];

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  template: `
    <a class="saltar" href="#contenido" (click)="saltar($event)">Saltar al contenido</a>
    @if (auth.usuario(); as u) {
      <header class="cabecera">
        <strong class="marca">Transporte Sunshine</strong>
        <nav aria-label="Principal">
          @for (l of enlaces; track l.ruta) {
            @if (!l.admin || auth.esAdmin()) {
              <a [routerLink]="l.ruta" routerLinkActive="activo" ariaCurrentWhenActive="page"
                [routerLinkActiveOptions]="{ exact: l.ruta === '/' }">{{ l.texto }}</a>
            }
          }
        </nav>
        <span class="sesion">{{ u.nombre }} ({{ u.rol }})
          <button type="button" class="btn" (click)="auth.logout()">Salir</button></span>
      </header>
    }
    <main id="contenido" #principal tabindex="-1" class="contenido"><router-outlet /></main>

    <div class="toasts" aria-live="polite" aria-atomic="false">
      @for (a of avisos.avisos(); track a.id) {
        <div class="toast" [class.error]="a.tipo === 'error'" [attr.role]="a.tipo === 'error' ? 'alert' : 'status'"
          (mouseenter)="avisos.pausar(a.id)" (mouseleave)="avisos.reanudar(a.id)"
          (focusin)="avisos.pausar(a.id)" (focusout)="avisos.reanudar(a.id)">
          {{ a.texto }}
          <button type="button" class="cerrar" aria-label="Cerrar aviso" (click)="avisos.cerrar(a.id)">×</button>
        </div>
      }
    </div>
  `,
})
export class App {
  auth = inject(AuthService);
  avisos = inject(NotificacionesService);
  enlaces = ENLACES;
  private principal = viewChild.required<ElementRef<HTMLElement>>('principal');

  constructor() {
    // al cambiar de ruta el foco pasa al contenido (la primera navegacion, la de carga, se respeta)
    inject(Router).events
      .pipe(filter((e) => e instanceof NavigationEnd), skip(1), takeUntilDestroyed())
      .subscribe(() => this.principal().nativeElement.focus());
  }

  // con <base href="/"> el ancla #contenido navegaria a la raiz: se enfoca a mano
  saltar(ev: Event) {
    ev.preventDefault();
    this.principal().nativeElement.focus();
  }
}
