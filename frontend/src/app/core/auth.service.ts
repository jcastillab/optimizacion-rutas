import { Injectable, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { ApiService } from './api.service';
import { Usuario } from './models';
import { NotificacionesService } from './notificaciones.service';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private api = inject(ApiService);
  private router = inject(Router);
  private avisos = inject(NotificacionesService);
  readonly usuario = signal<Usuario | null>(null);
  readonly esAdmin = computed(() => this.usuario()?.rol === 'admin');

  constructor() {
    this.api.noAutenticado.subscribe(() => {
      this.usuario.set(null);
      if (!this.router.url.startsWith('/login')) this.router.navigate(['/login']);
    });
  }

  /** Consulta la sesion del servidor; sin sesion (o sin backend) queda anonimo. */
  async cargar(): Promise<void> {
    try {
      this.usuario.set(await firstValueFrom(this.api.get<Usuario>('/auth/yo')));
    } catch {
      this.usuario.set(null);
    }
  }
  async login(usuario: string, clave: string): Promise<void> {
    this.usuario.set(await firstValueFrom(this.api.post<Usuario>('/auth/login', { usuario, clave })));
  }
  async logout(): Promise<void> {
    try {
      await firstValueFrom(this.api.post('/auth/logout'));
    } catch {
      this.avisos.error('No se pudo cerrar la sesión en el servidor.');
    } finally {
      this.usuario.set(null);
      this.router.navigate(['/login']);
    }
  }
}
