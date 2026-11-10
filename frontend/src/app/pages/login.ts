import { AfterViewInit, Component, ElementRef, inject, signal, viewChild } from '@angular/core';
import { Router } from '@angular/router';
import { ApiError } from '../core/api.service';
import { AuthService } from '../core/auth.service';

@Component({
  selector: 'app-login',
  template: `
    <main class="login">
      <form class="tarjeta" (submit)="$event.preventDefault(); entrar(u.value, c.value)" novalidate>
        <h1>Transporte Sunshine</h1>
        <p>Ingresa con tu usuario.</p>
        @if (error()) { <p class="error" role="alert">{{ error() }}</p> }
        <div class="campo">
          <label for="usuario">Usuario</label>
          <input #u id="usuario" name="usuario" autocomplete="username" />
        </div>
        <div class="campo">
          <label for="clave">Contraseña</label>
          <input #c id="clave" name="clave" type="password" autocomplete="current-password" />
        </div>
        <button type="submit" class="btn primario" [disabled]="cargando()">
          {{ cargando() ? 'Ingresando…' : 'Ingresar' }}
        </button>
      </form>
    </main>
  `,
})
export class Login implements AfterViewInit {
  private auth = inject(AuthService);
  private router = inject(Router);
  private usuario = viewChild.required<ElementRef<HTMLInputElement>>('u');
  error = signal('');
  cargando = signal(false);

  ngAfterViewInit() {
    this.usuario().nativeElement.focus();
  }

  // Los valores se leen del DOM al enviar: el autocompletado del navegador no siempre dispara eventos de input.
  async entrar(usuario: string, clave: string) {
    if (!usuario.trim() || !clave) {
      this.error.set('Ingresa tu usuario y tu contraseña.');
      return;
    }
    this.cargando.set(true);
    this.error.set('');
    try {
      await this.auth.login(usuario.trim(), clave);
      this.router.navigate(['/']);
    } catch (e) {
      this.error.set(e instanceof ApiError ? e.message : 'No se pudo ingresar.');
    } finally {
      this.cargando.set(false);
    }
  }
}
