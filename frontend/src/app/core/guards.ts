import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from './auth.service';

export const sesionGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  return auth.usuario() ? true : inject(Router).createUrlTree(['/login']);
};

export const adminGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  if (!auth.usuario()) return inject(Router).createUrlTree(['/login']);
  return auth.esAdmin() ? true : inject(Router).createUrlTree(['/']);
};

/** Con sesion activa, /login no tiene sentido: manda al inicio. */
export const loginGuard: CanActivateFn = () => (inject(AuthService).usuario() ? inject(Router).createUrlTree(['/']) : true);
