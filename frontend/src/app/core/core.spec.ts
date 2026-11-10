import { TestBed } from '@angular/core/testing';
import { Router } from '@angular/router';
import { configurar } from '../testing';
import { ApiError, ApiService } from './api.service';
import { AuthService } from './auth.service';
import { CatalogosService } from './catalogos.service';
import { adminGuard, loginGuard, sesionGuard } from './guards';
import { NotificacionesService } from './notificaciones.service';

const usuario = (rol: string) => ({ id: 1, usuario: 'a', nombre: 'Ana', rol, activo: true }) as never;

describe('ApiService', () => {
  it('prefija /api, envía cookies y omite parámetros vacíos', () => {
    const http = configurar();
    TestBed.inject(ApiService).get('/fincas', { q: '', pagina: 2 }).subscribe();
    const r = http.expectOne((x) => x.url === '/api/fincas');
    expect(r.request.withCredentials).toBe(true);
    expect(r.request.params.keys()).toEqual(['pagina']);
    r.flush({});
  });

  it('codifica el "+" de la búsqueda como %2B (y no como espacio)', () => {
    const http = configurar();
    TestBed.inject(ApiService).get('/personas', { q: 'a+b c&d' }).subscribe();
    const r = http.expectOne((x) => x.url === '/api/personas');
    expect(r.request.urlWithParams).toBe('/api/personas?q=a%2Bb%20c%26d');
    r.flush({});
  });

  it('traduce el error del contrato con detalle por campo', () => {
    const http = configurar();
    let err!: ApiError;
    TestBed.inject(ApiService).post('/fincas', {}).subscribe({ error: (e) => (err = e) });
    http.expectOne('/api/fincas').flush(
      { error: { codigo: 'VALIDACION', mensaje: 'Datos inválidos.', detalle: [{ campo: 'lat', mensaje: 'Fuera de rango' }] } },
      { status: 422, statusText: 'x' },
    );
    expect(err.message).toBe('Datos inválidos.');
    expect(err.porCampo()).toEqual({ lat: 'Fuera de rango' });
  });

  it('500 agrega el código de soporte (request_id); 403 y 429 muestran el mensaje del servidor', () => {
    const http = configurar();
    const api = TestBed.inject(ApiService);
    const msgs: string[] = [];
    for (const [status, mensaje, rid] of [[500, 'Error interno.', '9f1c'], [403, 'No tienes permiso.', null], [429, 'Cuenta bloqueada 5 min.', null]] as const) {
      api.get('/x').subscribe({ error: (e) => msgs.push(e.message) });
      http.expectOne('/api/x').flush({ error: { codigo: 'X', mensaje, request_id: rid } }, { status, statusText: 'x' });
    }
    expect(msgs).toEqual(['Error interno. Código de soporte: 9f1c', 'No tienes permiso.', 'Cuenta bloqueada 5 min.']);
  });

  it('sin cuerpo: mensajes propios para sin conexión, 403 y 429, sin inventar 401', () => {
    const http = configurar();
    const api = TestBed.inject(ApiService);
    let avisos = 0;
    api.noAutenticado.subscribe(() => avisos++);
    const msgs: string[] = [];
    api.get('/x').subscribe({ error: (e) => msgs.push(e.message) });
    http.expectOne('/api/x').error(new ProgressEvent('error'));
    api.get('/x').subscribe({ error: (e) => msgs.push(e.message) });
    http.expectOne('/api/x').flush('', { status: 403, statusText: 'x' });
    expect(msgs).toEqual(['No se pudo conectar con el servidor.', 'No tienes permiso para esta acción.']);
    expect(avisos).toBe(0);
  });

  it('un 401 limpia la sesión y manda al login', () => {
    const http = configurar();
    const auth = TestBed.inject(AuthService);
    auth.usuario.set(usuario('admin'));
    const navegar = vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
    TestBed.inject(ApiService).get('/personas').subscribe({ error: () => {} });
    http.expectOne('/api/personas').flush({ error: { codigo: 'NO_AUTENTICADO', mensaje: 'Sesión vencida.' } }, { status: 401, statusText: 'x' });
    expect(auth.usuario()).toBeNull();
    expect(navegar).toHaveBeenCalledWith(['/login']);
  });
});

describe('AuthService', () => {
  it('cargar() consulta /auth/yo y calcula esAdmin', async () => {
    const http = configurar();
    const auth = TestBed.inject(AuthService);
    const p = auth.cargar();
    http.expectOne('/api/auth/yo').flush(usuario('lector'));
    await p;
    expect(auth.usuario()?.nombre).toBe('Ana');
    expect(auth.esAdmin()).toBe(false);
  });

  it('logout con error del servidor avisa y de todos modos cierra la sesión local', async () => {
    const http = configurar();
    const auth = TestBed.inject(AuthService);
    auth.usuario.set(usuario('admin'));
    vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
    const p = auth.logout();
    http.expectOne('/api/auth/logout').flush({ error: { codigo: 'ERROR_INTERNO', mensaje: 'x' } }, { status: 500, statusText: 'x' });
    await p;
    expect(auth.usuario()).toBeNull();
    expect(TestBed.inject(NotificacionesService).avisos()[0].texto).toBe('No se pudo cerrar la sesión en el servidor.');
  });
});

describe('guards con router real', () => {
  const rutas = [
    { path: 'login', canActivate: [loginGuard], children: [] },
    { path: 'admin', canActivate: [adminGuard], children: [] },
    { path: 'datos', canActivate: [sesionGuard], children: [] },
    { path: '', children: [] },
  ];
  async function ir(url: string, u: unknown) {
    TestBed.resetTestingModule();
    configurar(rutas);
    TestBed.inject(AuthService).usuario.set(u as never);
    const router = TestBed.inject(Router);
    await router.navigateByUrl(url);
    return router.url;
  }
  it('sin sesión: datos y admin van a /login', async () => {
    expect(await ir('/datos', null)).toBe('/login');
    expect(await ir('/admin', null)).toBe('/login');
  });
  it('lector: datos sí, admin no (va al inicio)', async () => {
    expect(await ir('/datos', usuario('lector'))).toBe('/datos');
    expect(await ir('/admin', usuario('lector'))).toBe('/');
  });
  it('admin entra a admin', async () => {
    expect(await ir('/admin', usuario('admin'))).toBe('/admin');
  });
  it('con sesión, /login redirige a /', async () => {
    expect(await ir('/login', usuario('lector'))).toBe('/');
    expect(await ir('/login', null)).toBe('/login');
  });
});

describe('CatalogosService', () => {
  const ref = (id: number) => ({ id, nombre: `F${id}` });
  it('pagina hasta traer todo, usa caché y se refresca tras una escritura', async () => {
    const http = configurar();
    const cat = TestBed.inject(CatalogosService);
    cat.asegurar('fincas');
    cat.asegurar('fincas'); // segunda llamada: sin petición nueva
    http.expectOne((r) => r.params.get('pagina') === '1').flush({ items: [ref(1), ref(2)], total: 3, pagina: 1, por_pagina: 2 });
    http.expectOne((r) => r.params.get('pagina') === '2').flush({ items: [ref(3)], total: 3, pagina: 2, por_pagina: 2 });
    http.expectNone(() => true);
    expect(cat.fincas().map((x) => x.id)).toEqual([1, 2, 3]);

    TestBed.inject(ApiService).post('/fincas', {}).subscribe();
    http.expectOne({ method: 'POST', url: '/api/fincas' }).flush({});
    http.expectOne((r) => r.method === 'GET' && r.url === '/api/fincas').flush({ items: [ref(1)], total: 1, pagina: 1, por_pagina: 200 });
    expect(cat.fincas().length).toBe(1);
    expect(cat.nombre(cat.fincas(), 99)).toBe('#99');
  });
});

describe('NotificacionesService', () => {
  it('no cierra el aviso mientras está pausado (hover/foco) y lo cierra al reanudar', () => {
    vi.useFakeTimers();
    try {
      const n = new NotificacionesService();
      n.error('algo');
      const id = n.avisos()[0].id;
      n.pausar(id);
      vi.advanceTimersByTime(60000);
      expect(n.avisos().length).toBe(1);
      n.reanudar(id);
      vi.advanceTimersByTime(5000);
      expect(n.avisos().length).toBe(1); // los errores duran 12 s
      vi.advanceTimersByTime(8000);
      expect(n.avisos().length).toBe(0);
    } finally {
      vi.useRealTimers();
    }
  });
});
