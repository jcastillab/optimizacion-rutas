import { Routes } from '@angular/router';
import { adminGuard, loginGuard, sesionGuard } from './core/guards';

export const routes: Routes = [
  { path: 'login', title: 'Ingresar', canActivate: [loginGuard], loadComponent: () => import('./pages/login').then((m) => m.Login) },
  {
    path: '',
    canActivate: [sesionGuard],
    children: [
      { path: '', pathMatch: 'full', title: 'Inicio', loadComponent: () => import('./pages/inicio').then((m) => m.Inicio) },
      { path: 'personas', title: 'Personas', loadComponent: () => import('./pages/personas').then((m) => m.Personas) },
      { path: 'paraderos', title: 'Paraderos', loadComponent: () => import('./pages/paraderos').then((m) => m.Paraderos) },
      { path: 'fincas', title: 'Fincas', loadComponent: () => import('./pages/fincas').then((m) => m.Fincas) },
      { path: 'tipos-bus', title: 'Tipos de bus', loadComponent: () => import('./pages/tipos-bus').then((m) => m.TiposBus) },
      { path: 'simulador', title: 'Simulador', loadComponent: () => import('./pages/simulador').then((m) => m.Simulador) },
      { path: 'corridas', title: 'Corridas', loadComponent: () => import('./pages/corridas').then((m) => m.Corridas) },
      { path: 'corridas/:id', title: 'Corrida', loadComponent: () => import('./pages/corrida-detalle').then((m) => m.CorridaDetalle) },
      { path: 'usuarios', title: 'Usuarios', canActivate: [adminGuard], loadComponent: () => import('./pages/usuarios').then((m) => m.Usuarios) },
      { path: 'importar', title: 'Importar', canActivate: [adminGuard], loadComponent: () => import('./pages/importar').then((m) => m.Importar) },
      { path: 'eventos', title: 'Eventos', canActivate: [adminGuard], loadComponent: () => import('./pages/eventos').then((m) => m.Eventos) },
    ],
  },
  { path: '**', redirectTo: '' },
];
