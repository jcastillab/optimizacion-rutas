import { TestBed } from '@angular/core/testing';
import { Router } from '@angular/router';
import { App } from './app';
import { AuthService } from './core/auth.service';
import { Corridas } from './pages/corridas';
import { CorridaDetalle } from './pages/corrida-detalle';
import { Login } from './pages/login';
import { Paginador } from './shared/paginador';
import { Usuarios } from './pages/usuarios';
import { Simulador } from './pages/simulador';
import { boton, configurar, escribir, estable, pagina } from './testing';

const u = (rol: string) => ({ id: 1, usuario: 'a', nombre: 'Ana', rol, activo: true }) as never;

describe('App (menú)', () => {
  async function montar(rol: string) {
    const http = configurar([{ path: '**', children: [] }]);
    TestBed.inject(AuthService).usuario.set(u(rol));
    const f = TestBed.createComponent(App);
    await estable(f);
    return { f, http, el: f.nativeElement as HTMLElement };
  }
  const textos = (el: HTMLElement) => [...el.querySelectorAll('nav a')].map((a) => a.textContent?.trim());

  it('el lector no ve Usuarios, Importar ni Eventos', async () => {
    const { el } = await montar('lector');
    expect(textos(el)).toContain('Simulador');
    for (const t of ['Usuarios', 'Importar', 'Eventos']) expect(textos(el)).not.toContain(t);
  });

  it('el admin los ve', async () => {
    const { el } = await montar('admin');
    for (const t of ['Usuarios', 'Importar', 'Eventos']) expect(textos(el)).toContain(t);
  });

  it('el enlace activo lleva aria-current="page"', async () => {
    const { f, el } = await montar('admin');
    await TestBed.inject(Router).navigateByUrl('/fincas');
    await estable(f);
    expect(el.querySelector('nav a[aria-current="page"]')?.textContent?.trim()).toBe('Fincas');
  });

  it('"Saltar al contenido" enfoca <main> sin navegar (por el <base href="/">)', async () => {
    const { el } = await montar('lector');
    const ev = new MouseEvent('click', { bubbles: true, cancelable: true });
    el.querySelector('a.saltar')!.dispatchEvent(ev);
    expect(ev.defaultPrevented).toBe(true);
    expect(document.activeElement).toBe(el.querySelector('main#contenido'));
  });

  it('al cambiar de ruta el foco pasa a <main>', async () => {
    const { f, el } = await montar('lector');
    const router = TestBed.inject(Router);
    await router.navigateByUrl('/a'); // primera navegación: se respeta
    await router.navigateByUrl('/b');
    await estable(f);
    expect(document.activeElement).toBe(el.querySelector('main#contenido'));
  });

  it('los avisos se quedan mientras el mouse está encima', async () => {
    vi.useFakeTimers();
    try {
      const { f, el } = await montar('lector');
      const n = (await import('./core/notificaciones.service')).NotificacionesService;
      const avisos = TestBed.inject(n);
      avisos.ok('Hecho');
      f.detectChanges();
      const t = el.querySelector('.toast')!;
      t.dispatchEvent(new Event('mouseenter'));
      vi.advanceTimersByTime(30000);
      expect(avisos.avisos().length).toBe(1);
      t.dispatchEvent(new Event('mouseleave'));
      vi.advanceTimersByTime(8000);
      expect(avisos.avisos().length).toBe(0);
    } finally {
      vi.useRealTimers();
    }
  });
});

describe('Login', () => {
  async function montar() {
    const http = configurar();
    const f = TestBed.createComponent(Login);
    await estable(f);
    return { f, http, el: f.nativeElement as HTMLElement };
  }
  it('al abrir enfoca el usuario y el botón no se deshabilita por estar vacío', async () => {
    const { el } = await montar();
    expect(document.activeElement).toBe(el.querySelector('#usuario'));
    expect((boton(el, 'Ingresar') as HTMLButtonElement).disabled).toBe(false);
  });
  it('vacío: avisa y no envía', async () => {
    const { f, http, el } = await montar();
    boton(el, 'Ingresar').click();
    await estable(f);
    http.expectNone('/api/auth/login');
    expect(el.querySelector('[role=alert]')?.textContent).toContain('Ingresa tu usuario');
  });
  it('envía valores autocompletados aunque no hubo eventos de input', async () => {
    const { f, http, el } = await montar();
    vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
    el.querySelector<HTMLInputElement>('#usuario')!.value = 'ana'; // como el autocompletado: sin evento
    el.querySelector<HTMLInputElement>('#clave')!.value = ' secreta ';
    boton(el, 'Ingresar').click();
    const r = http.expectOne('/api/auth/login');
    expect(r.request.body).toEqual({ usuario: 'ana', clave: ' secreta ' });
    r.flush({ id: 1, usuario: 'ana', nombre: 'Ana', rol: 'lector', activo: true });
    await estable(f);
    expect(TestBed.inject(AuthService).usuario()?.usuario).toBe('ana');
  });
  it('401: muestra el mensaje del servidor', async () => {
    const { f, http, el } = await montar();
    el.querySelector<HTMLInputElement>('#usuario')!.value = 'ana';
    el.querySelector<HTMLInputElement>('#clave')!.value = 'mala';
    boton(el, 'Ingresar').click();
    http.expectOne('/api/auth/login').flush({ error: { codigo: 'NO_AUTENTICADO', mensaje: 'Usuario o clave incorrectos.' } }, { status: 401, statusText: 'x' });
    await estable(f);
    expect(el.querySelector('[role=alert]')?.textContent).toContain('Usuario o clave incorrectos.');
  });
});

describe('Usuarios (contraseña sin trim)', () => {
  it('envía la clave tal cual, con espacios', async () => {
    const http = configurar();
    const f = TestBed.createComponent(Usuarios);
    f.detectChanges();
    const el = f.nativeElement as HTMLElement;
    http.expectOne((r) => r.url === '/api/usuarios').flush(pagina([]));
    await estable(f);
    boton(el, 'Nuevo').click();
    await estable(f);
    escribir(el.querySelector('#f-usuario')!, ' ana ');
    escribir(el.querySelector('#f-nombre')!, 'Ana');
    escribir(el.querySelector('#f-clave')!, '  clave con espacios  ');
    boton(el, 'Guardar').click();
    const r = http.expectOne({ method: 'POST', url: '/api/usuarios' });
    expect(r.request.body.clave).toBe('  clave con espacios  ');
    expect(r.request.body.usuario).toBe('ana');
    expect(r.request.body.rol).toBe('lector');
    r.flush({});
    http.expectOne((x) => x.method === 'GET');
  });
});

describe('Paginador', () => {
  it('singular, plural y anuncia el cambio de página con aria-live', () => {
    configurar();
    const f = TestBed.createComponent(Paginador);
    f.componentRef.setInput('pagina', 1);
    f.componentRef.setInput('porPagina', 25);
    f.componentRef.setInput('total', 1);
    f.detectChanges();
    const el = f.nativeElement as HTMLElement;
    expect(el.textContent).toContain('1 registro · página 1 de 1');
    expect(el.querySelector('[aria-live=polite]')).toBeTruthy();
    f.componentRef.setInput('total', 60);
    f.detectChanges();
    expect(el.textContent).toContain('60 registros · página 1 de 3');
    const emitidos: number[] = [];
    f.componentInstance.cambiar.subscribe((p: number) => emitidos.push(p));
    boton(el, 'Siguiente').click();
    expect(emitidos).toEqual([2]);
    expect((boton(el, 'Anterior') as HTMLButtonElement).disabled).toBe(true);
  });
});

describe('Corridas', () => {
  const corr = (id: number) => ({ id, creada: '2026-10-26T14:03:00Z', usuario: 'ana', parametros: { velocidad_kmh: 25, tiempo_max_min: 60 },
    resumen: { rutas: 1, buses: 1, personas: 1, costo_total: 1000, costo_red_actual: 1, diferencia_pct: null, personas_sin_servicio: 0 } });

  it('borrar la última fila de la última página retrocede una página', async () => {
    const http = configurar();
    TestBed.inject(AuthService).usuario.set(u('admin'));
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    const f = TestBed.createComponent(Corridas);
    f.detectChanges();
    const el = f.nativeElement as HTMLElement;
    http.expectOne((r) => r.url === '/api/corridas').flush(pagina([corr(1)], 26, 1));
    await estable(f);
    boton(el, 'Siguiente').click();
    http.expectOne((r) => r.params.get('pagina') === '2').flush(pagina([corr(26)], 26, 2));
    await estable(f);
    expect(el.textContent).toContain('página 2 de 2');
    expect(el.textContent).toContain('—'); // diferencia_pct nulo
    boton(el, 'Borrar').click();
    http.expectOne({ method: 'DELETE', url: '/api/corridas/26' }).flush(null, { status: 204, statusText: 'x' });
    http.expectOne((r) => r.method === 'GET' && r.params.get('pagina') === '2').flush(pagina([], 25, 2));
    const p1 = http.expectOne((r) => r.method === 'GET' && r.params.get('pagina') === '1');
    p1.flush(pagina([corr(1)], 25, 1));
    await estable(f);
    expect(el.textContent).toContain('página 1 de 1');
  });
});

describe('CorridaDetalle', () => {
  it('reacciona al cambio de :id y codifica el id en la URL', async () => {
    const http = configurar();
    const f = TestBed.createComponent(CorridaDetalle);
    f.componentRef.setInput('id', '7');
    await estable(f);
    const c = (id: number) => ({ id, creada: '2026-10-26T14:03:00Z', usuario: 'ana', parametros: { velocidad_kmh: 25, tiempo_max_min: 60 },
      resumen: { rutas: 1, buses: 1, personas: 1, costo_total: 1, costo_red_actual: 1, diferencia_pct: 0, personas_sin_servicio: 0 }, rutas: [], sin_servicio: [] });
    http.expectOne('/api/corridas/7').flush(c(7));
    http.match((r) => r.url === '/api/fincas' || r.url === '/api/paraderos').forEach((r) => r.flush(pagina([])));
    await estable(f);
    expect(f.nativeElement.textContent).toContain('Corrida #7');

    f.componentRef.setInput('id', '8/../x');
    await estable(f);
    http.expectOne('/api/corridas/8%2F..%2Fx').flush(c(8));
    await estable(f);
    expect(f.nativeElement.textContent).toContain('Corrida #8');
  });
});

describe('Simulador', () => {
  it('omite claves vacías y muestra detalle[] por campo en un 422', async () => {
    const http = configurar();
    const f = TestBed.createComponent(Simulador);
    await estable(f);
    const el = f.nativeElement as HTMLElement;
    escribir(el.querySelector('[name=velocidad_kmh]')!, '');
    escribir(el.querySelector('[name=tiempo_max_min]')!, '45');
    boton(el, 'Ejecutar simulación').click();
    const r = http.expectOne('/api/simulador/ejecutar');
    expect(r.request.body).toEqual({ tiempo_max_min: 45 });
    r.flush({ error: { codigo: 'VALIDACION', mensaje: 'Datos inválidos.', detalle: [{ campo: 'tiempo_max_min', mensaje: 'Máximo 300.' }, { campo: 'otro', mensaje: 'x' }] } },
      { status: 422, statusText: 'x' });
    await estable(f);
    expect(el.querySelector('#e-t')?.textContent).toContain('Máximo 300.');
    expect(el.querySelector('[role=alert]')?.textContent).toContain('otro: x');
  });
});
