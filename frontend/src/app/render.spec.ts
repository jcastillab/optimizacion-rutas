import { TestBed } from '@angular/core/testing';
import { appConfig } from './app.config';
import { AuthService } from './core/auth.service';
import { proveedorLocale } from './core/locale';
import { Corrida } from './core/models';
import { Corridas } from './pages/corridas';
import { Eventos } from './pages/eventos';
import { Inicio } from './pages/inicio';
import { Simulador } from './pages/simulador';
import { CorridaResultado } from './shared/corrida-resultado';
import { configurar, estable, pagina } from './testing';

// Forma real de la respuesta del API (contrato actualizado: advertencias, snapshot de paraderos y finca)
const ADVERTENCIAS = [
  'Comparación orientativa: la red actual supone un bus por fila de tarifa (no confirmado con el proveedor).',
  'La simulación cubre solo a las personas que cruzan con el catálogo de rutas (413 de 471).',
  'Tiempos con velocidad promedio constante y distancia en línea recta.',
  'Los costos de bus son la mediana REGULAR por tipo.',
];
const corrida: Corrida = {
  id: 7, creada: '2026-10-26T14:03:00Z', usuario: 'ana',
  parametros: { velocidad_kmh: 25, tiempo_max_min: 60 },
  resumen: { buses: 17, costo_red_actual: 6604600, costo_total: 6339000, diferencia_pct: -4, personas: 413,
    personas_sin_paradero: 0, personas_sin_servicio: 2, rutas: 17, advertencias: ADVERTENCIAS },
  rutas: [{ buses: 1, capacidad: 40, costo_total: 458000, finca_id: 1, finca_nombre: 'FINCA SNAPSHOT', km: 21.54, minutos_max: 51.7,
    paraderos: [{ id: 3, lat: 4.7, lon: -74.2, nombre: 'PARADERO UNO' }, { id: 4, lat: 4.8, lon: -74.1, nombre: 'PARADERO DOS' }],
    personas: 38, ruta_simulada: 1, tipo_bus: 'BUS' }],
  sin_servicio: [{ finca_id: 1, paradero_id: 5, personas: 2 }],
};
const sinComparar: Corrida = { ...corrida, resumen: { ...corrida.resumen, diferencia_pct: null } };

function montar() {
  // mismo locale que la app: si se quita de app.config, estas pruebas fallan
  expect(appConfig.providers).toContain(proveedorLocale);
  return configurar();
}
const texto = (el: HTMLElement) => el.textContent ?? '';

function verifica(el: HTMLElement) {
  const t = texto(el);
  expect(t).toContain('6.339.000');
  expect(t).toContain('6.604.600');
  expect(t).toContain('-4,0 %');
  expect(t).toContain('Comparación orientativa con la red actual');
  expect(t).not.toMatch(/ahorro/i);
  expect(t).toContain('458.000');
  expect(t).toContain('21,5');
  expect(t).toContain('BUS (40)');
  // snapshot: nombres de finca y paraderos salen de la corrida
  expect(t).toContain('FINCA SNAPSHOT');
  expect(t).toContain('PARADERO UNO, PARADERO DOS (2)');
  expect(t).toContain('2 persona(s) en el paradero #5, finca FINCA SNAPSHOT');
  // advertencias: las 4, visibles (role=note) y antes de la cifra de diferencia
  const nota = el.querySelector('[role=note]')!;
  for (const a of ADVERTENCIAS) expect(nota.textContent).toContain(a);
  expect(nota.querySelectorAll('li').length).toBe(4);
  const dif = [...el.querySelectorAll('dt')].find((d) => d.textContent?.includes('Comparación'))!;
  expect(nota.compareDocumentPosition(dif) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(el.querySelectorAll('tbody tr').length).toBe(1);
}

describe('render con datos reales del API', () => {
  it('CorridaResultado: cifras, advertencias, snapshot y sin pedir catálogos vivos', () => {
    const http = montar();
    const f = TestBed.createComponent(CorridaResultado);
    f.componentRef.setInput('corrida', corrida);
    f.detectChanges();
    http.expectNone(() => true);
    verifica(f.nativeElement);
    expect(texto(f.nativeElement)).not.toContain('no tienen paradero');
  });

  it('diferencia_pct nulo: "No comparable", sin color y nunca 0 %', () => {
    const http = montar();
    const f = TestBed.createComponent(CorridaResultado);
    f.componentRef.setInput('corrida', sinComparar);
    f.detectChanges();
    http.expectNone(() => true);
    const el: HTMLElement = f.nativeElement;
    expect(texto(el)).toContain('No comparable');
    expect(texto(el)).not.toMatch(/\b0,0 %/);
    expect(el.querySelector('.mejor, .peor')).toBeNull();
    expect(el.querySelector('[role=note]')).toBeTruthy(); // las advertencias siguen visibles
  });

  it('corrida vieja sin advertencias: no hay recuadro ni error', () => {
    montar();
    const f = TestBed.createComponent(CorridaResultado);
    f.componentRef.setInput('corrida', { ...corrida, resumen: { ...corrida.resumen, advertencias: undefined } });
    f.detectChanges();
    expect(f.nativeElement.querySelector('[role=note]')).toBeNull();
  });

  it('avisa personas sin paradero solo si > 0', () => {
    montar();
    const f = TestBed.createComponent(CorridaResultado);
    f.componentRef.setInput('corrida', { ...corrida, resumen: { ...corrida.resumen, personas_sin_paradero: 4 } });
    f.detectChanges();
    expect(texto(f.nativeElement)).toContain('4 persona(s) no tienen paradero');
  });

  it('Simulador', async () => {
    const http = montar();
    const f = TestBed.createComponent(Simulador);
    f.detectChanges();
    f.componentInstance.ejecutar();
    http.expectOne('/api/simulador/ejecutar').flush(corrida);
    await estable(f);
    verifica(f.nativeElement);
  });

  it('Corridas: total del servidor, sin fila fantasma, "—" si no es comparable', async () => {
    const http = montar();
    const f = TestBed.createComponent(Corridas);
    f.detectChanges();
    const lista = { ...corrida, rutas: undefined, sin_servicio: undefined };
    http.expectOne((r) => r.url === '/api/corridas').flush(pagina([lista, { ...lista, id: 6, resumen: sinComparar.resumen }]));
    await estable(f);
    const t = texto(f.nativeElement);
    expect(t).toContain('2 registros');
    expect(t).toContain('6.339.000');
    expect(t).toContain('-4,0 %');
    expect(f.nativeElement.querySelectorAll('tbody tr').length).toBe(2);
    const filas = f.nativeElement.querySelectorAll('tbody tr');
    expect(filas[1].textContent).toContain('—');
    expect(filas[1].textContent).not.toMatch(/0,0 %/);
  });

  it('Inicio: muestra la última corrida con sus advertencias', async () => {
    const http = montar();
    TestBed.inject(AuthService).usuario.set({ id: 1, usuario: 'a', nombre: 'Ana', rol: 'admin', activo: true });
    const f = TestBed.createComponent(Inicio);
    f.detectChanges();
    for (const r of http.match((q) => q.url !== '/api/corridas' && q.url !== '/api/corridas/7')) r.flush(pagina([], 5));
    http.expectOne((r) => r.url === '/api/corridas').flush(pagina([corrida], 1));
    http.expectOne('/api/corridas/7').flush(corrida);
    await estable(f);
    verifica(f.nativeElement);
    expect(texto(f.nativeElement)).toContain('26/10/2026');
  });

  it('Eventos: fecha y detalle antes → después', async () => {
    const http = montar();
    const f = TestBed.createComponent(Eventos);
    f.detectChanges();
    http.expectOne((r) => r.url === '/api/eventos').flush(pagina([
      { id: 1, fecha: '2026-10-26T14:03:00Z', usuario: 'ana', accion: 'editar', entidad: 'finca', entidad_id: 1,
        detalle: '{"antes":{"nombre":"A"},"despues":{"nombre":"B"}}', request_id: 'x' },
    ]));
    await estable(f);
    const t = texto(f.nativeElement);
    expect(t).toContain('nombre: A → B');
    expect(t).toContain('26/10/2026');
    expect(t).toContain('1 registro ·');
  });
});
