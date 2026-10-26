import { TestBed } from '@angular/core/testing';
import { boton, configurar, estable } from '../testing';
import { Importar } from './importar';

const RESULTADO = {
  fincas: { creadas: 3, actualizadas: 0 }, paraderos: { creadas: 10, actualizadas: 1 },
  personas: { creadas: 400, actualizadas: 2 }, tipos_bus: { creadas: 2, actualizadas: 0 },
  avisos: ['3 identificaciones repetidas fueron deduplicadas.', '5 registros difieren del Excel y no se modificaron.'],
};

describe('Importar', () => {
  async function montar() {
    const http = configurar();
    const f = TestBed.createComponent(Importar);
    await estable(f);
    return { f, http, el: f.nativeElement as HTMLElement };
  }

  it('por defecto no sobrescribe: sin parámetro, y la confirmación dice el modo', async () => {
    const { f, http, el } = await montar();
    expect(el.querySelector<HTMLInputElement>('input[name=sobrescribir]')!.checked).toBe(false);
    expect(el.textContent).toContain('Pisa ediciones hechas en la aplicación');
    boton(el, 'Importar datos del Excel local').click();
    await estable(f);
    expect(el.querySelector('dialog[open], dialog')?.textContent).toContain('solo crear lo que falta');
    f.componentInstance.importar();
    const r = http.expectOne((x) => x.url === '/api/importar/datos-locales');
    expect(r.request.method).toBe('POST');
    expect(r.request.params.has('sobrescribir')).toBe(false);
    r.flush(RESULTADO);
    await estable(f);
    for (const a of RESULTADO.avisos) expect(el.textContent).toContain(a);
    expect(el.textContent).toContain('400');
  });

  it('con la casilla marcada envía ?sobrescribir=true y la confirmación lo advierte', async () => {
    const { f, http, el } = await montar();
    const caja = el.querySelector<HTMLInputElement>('input[name=sobrescribir]')!;
    caja.checked = true;
    caja.dispatchEvent(new Event('change', { bubbles: true }));
    await estable(f);
    expect(el.querySelector('dialog')?.textContent).toContain('sobrescribir existentes');
    f.componentInstance.importar();
    const r = http.expectOne((x) => x.url === '/api/importar/datos-locales');
    expect(r.request.urlWithParams).toContain('sobrescribir=true');
    r.flush(RESULTADO);
  });

  it('muestra el estado de carga con el botón deshabilitado y el error del contrato', async () => {
    const { f, http, el } = await montar();
    f.componentInstance.importar();
    await estable(f);
    expect(el.textContent).toContain('Importando');
    expect((boton(el, 'Importar datos del Excel local') as HTMLButtonElement).disabled).toBe(true);
    http.expectOne((x) => x.url === '/api/importar/datos-locales').flush(
      { error: { codigo: 'VALIDACION', mensaje: 'Faltan los archivos de datos.' } }, { status: 422, statusText: 'x' });
    await estable(f);
    expect(el.querySelector('[role=alert]')?.textContent).toContain('Faltan los archivos');
    expect((boton(el, 'Importar datos del Excel local') as HTMLButtonElement).disabled).toBe(false);
  });
});
