import { HttpTestingController } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { boton, configurar, escribir, estable, pagina } from '../testing';
import { Campo, CrudTable } from './crud-table';

const campos: Campo[] = [
  { clave: 'nombre', etiqueta: 'Nombre', tipo: 'text', requerido: true },
  { clave: 'lat', etiqueta: 'Latitud', tipo: 'number', requerido: true },
  { clave: 'activo', etiqueta: 'Activa', tipo: 'checkbox' },
];
const finca = { id: 1, nombre: 'YARUMO', lat: 4, activo: true };

// Nota: <dialog>.showModal() no existe en jsdom; el componente usa el atributo "open" como respaldo.
// El comportamiento real de showModal (foco atrapado, Esc) solo se probó a mano en navegador.
describe('CrudTable (interacción con el DOM)', () => {
  let f: ComponentFixture<CrudTable>;
  let http: HttpTestingController;
  let el: HTMLElement;

  async function montar(puedeEscribir = true, filas: object[] = [finca], total = filas.length) {
    http = configurar();
    f = TestBed.createComponent(CrudTable);
    f.componentRef.setInput('titulo', 'Fincas');
    f.componentRef.setInput('ruta', '/fincas');
    f.componentRef.setInput('singular', 'finca');
    f.componentRef.setInput('columnas', [{ clave: 'nombre', titulo: 'Nombre' }]);
    f.componentRef.setInput('campos', campos);
    f.componentRef.setInput('puedeEscribir', puedeEscribir);
    f.detectChanges();
    el = f.nativeElement;
    http.expectOne((r) => r.url === '/api/fincas').flush(pagina(filas, total));
    await estable(f);
  }
  const lista = (filas: object[] = [finca], total = filas.length) =>
    http.expectOne((r) => r.url === '/api/fincas' && r.method === 'GET').flush(pagina(filas, total));
  const campo = (id: string) => el.querySelector<HTMLInputElement>(`#f-${id}`)!;
  const guardar = () => boton(el, 'Guardar').click();
  async function abrirNuevo() {
    boton(el, 'Nuevo').click();
    await estable(f);
  }

  it('el lector no ve Nuevo, Editar ni Borrar', async () => {
    await montar(false);
    expect(el.textContent).toContain('YARUMO');
    expect(boton(el, 'Buscar')).toBeTruthy();
    expect([...el.querySelectorAll('button')].some((b) => b.textContent?.trim() === 'Nuevo')).toBe(false);
    expect(el.querySelector('table button')).toBeNull();
    expect(el.querySelector('th')?.textContent).not.toContain('Acciones');
  });

  it('los botones de fila tienen nombre accesible con contexto', async () => {
    await montar();
    expect(el.querySelector('[aria-label="Editar finca YARUMO"]')).toBeTruthy();
    expect(el.querySelector('[aria-label="Borrar finca YARUMO"]')).toBeTruthy();
  });

  it('crear: escribe en el formulario, envía POST y recarga la lista', async () => {
    await montar();
    await abrirNuevo();
    escribir(campo('nombre'), '  Nueva  ');
    escribir(campo('lat'), '4.5');
    guardar();
    const post = http.expectOne('/api/fincas');
    expect(post.request.method).toBe('POST');
    expect(post.request.body).toEqual({ nombre: 'Nueva', lat: 4.5, activo: true });
    post.flush({ id: 2 });
    await estable(f);
    expect(el.querySelector('dialog[open]')).toBeNull();
    lista([finca, { id: 2, nombre: 'Nueva', lat: 4.5, activo: true }]);
    await estable(f);
    expect(el.textContent).toContain('Nueva');
  });

  it('al abrir el diálogo el foco queda en el primer campo', async () => {
    await montar();
    await abrirNuevo();
    expect(document.activeElement).toBe(campo('nombre'));
  });

  it('validación en el cliente: no envía, marca el campo y enfoca el primero inválido', async () => {
    await montar();
    await abrirNuevo();
    escribir(campo('nombre'), 'X');
    guardar();
    await estable(f);
    http.expectNone('/api/fincas');
    expect(el.querySelector('#e-lat')?.textContent).toContain('obligatorio');
    expect(campo('lat').getAttribute('aria-invalid')).toBe('true');
    expect(campo('lat').getAttribute('aria-required')).toBe('true');
    expect(document.activeElement).toBe(campo('lat'));
  });

  it('editar: PATCH solo con lo que cambió', async () => {
    await montar();
    boton(el, 'Editar').click();
    await estable(f);
    expect(campo('nombre').value).toBe('YARUMO');
    escribir(campo('lat'), '5');
    guardar();
    const patch = http.expectOne('/api/fincas/1');
    expect(patch.request.method).toBe('PATCH');
    expect(patch.request.body).toEqual({ lat: 5 });
    patch.flush({});
    await estable(f);
    lista();
  });

  it('editar sin cambios no manda nada', async () => {
    await montar();
    boton(el, 'Editar').click();
    await estable(f);
    guardar();
    http.expectNone('/api/fincas/1');
    expect(el.querySelector('dialog[open]')).toBeNull();
  });

  it('no envía dos veces si se pulsa Guardar mientras guarda', async () => {
    await montar();
    await abrirNuevo();
    escribir(campo('nombre'), 'A');
    escribir(campo('lat'), '1');
    guardar();
    f.componentInstance.guardar();
    http.expectOne('/api/fincas').flush({ id: 3 });
    lista();
  });

  it('borrar pide confirmación; Cancelar no borra y Borrar sí', async () => {
    await montar();
    boton(el, 'Borrar').click();
    await estable(f);
    const dlg = el.querySelector<HTMLElement>('dialog[open]')!;
    expect(dlg.textContent).toContain('Confirmar borrado');
    expect(document.activeElement?.textContent?.trim()).toBe('Cancelar');
    boton(dlg, 'Cancelar').click();
    http.expectNone('/api/fincas/1');
    expect(el.querySelector('dialog[open]')).toBeNull();

    boton(el, 'Borrar').click();
    await estable(f);
    boton(el.querySelector<HTMLElement>('dialog[open]')!, 'Borrar').click();
    const del = http.expectOne('/api/fincas/1');
    expect(del.request.method).toBe('DELETE');
    del.flush(null, { status: 204, statusText: 'No Content' });
    await estable(f);
    lista([]);
    await estable(f);
    expect(el.textContent).toContain('No hay registros');
  });

  it('409: muestra el mensaje del servidor en el diálogo', async () => {
    await montar();
    await abrirNuevo();
    escribir(campo('nombre'), 'YARUMO');
    escribir(campo('lat'), '4');
    guardar();
    http.expectOne('/api/fincas').flush(
      { error: { codigo: 'CONFLICTO', mensaje: 'Ya existe una finca con los mismos datos (nombre).', detalle: [{ campo: 'nombre', mensaje: 'duplicado' }] } },
      { status: 409, statusText: 'Conflict' },
    );
    await estable(f);
    expect(el.querySelector('dialog [role=alert]')?.textContent).toContain('Ya existe una finca con los mismos datos (nombre).');
    expect(el.querySelector('dialog[open]')).toBeTruthy();
  });

  it('422: error por campo y mensaje general con los campos que no están en el formulario', async () => {
    await montar();
    await abrirNuevo();
    escribir(campo('nombre'), 'A');
    escribir(campo('lat'), '99');
    guardar();
    http.expectOne('/api/fincas').flush(
      { error: { codigo: 'VALIDACION', mensaje: 'Datos inválidos.', detalle: [
        { campo: 'lat', mensaje: 'Debe estar entre -90 y 90.' }, { campo: 'cod_nivel2', mensaje: 'Requerido.' }] } },
      { status: 422, statusText: 'x' },
    );
    await estable(f);
    expect(el.querySelector('#e-lat')?.textContent).toContain('entre -90 y 90');
    expect(el.querySelector('dialog [role=alert]')?.textContent).toContain('cod_nivel2: Requerido.');
    expect(document.activeElement).toBe(campo('lat'));
  });

  it('paginado: Siguiente pide la página 2 y conserva los filtros aplicados, no lo escrito', async () => {
    await montar(true, [finca], 60);
    escribir(el.querySelector<HTMLInputElement>('input[type=search]')!, 'sin aplicar');
    boton(el, 'Siguiente').click();
    const r = http.expectOne((x) => x.url === '/api/fincas');
    expect(r.request.params.get('pagina')).toBe('2');
    expect(r.request.params.has('q')).toBe(false);
    r.flush(pagina([{ ...finca, id: 26, nombre: 'PAG2' }], 60, 2));
    await estable(f);
    expect(el.textContent).toContain('PAG2');
    expect(el.textContent).toContain('página 2 de 3');
  });

  it('respuestas fuera de orden no pisan la página mostrada', async () => {
    await montar(true, [finca], 100);
    boton(el, 'Siguiente').click();
    const r2 = http.expectOne((x) => x.url === '/api/fincas');
    f.detectChanges();
    boton(el, 'Siguiente').click();
    const r3 = http.expectOne((x) => x.url === '/api/fincas' && x.params.get('pagina') === '3');
    expect(r2.cancelled).toBe(true); // la petición anterior se canceló
    r3.flush(pagina([{ ...finca, nombre: 'TRES' }], 100, 3));
    await estable(f);
    expect(el.textContent).toContain('TRES');
  });

  it('búsqueda con "+" se envía codificada (%2B)', async () => {
    await montar();
    escribir(el.querySelector<HTMLInputElement>('input[type=search]')!, 'a+b');
    boton(el, 'Buscar').click();
    const r = http.expectOne((x) => x.url === '/api/fincas');
    expect(r.request.urlWithParams).toContain('q=a%2Bb');
    r.flush(pagina([]));
  });

  it('error de carga: aviso y Reintentar', async () => {
    http = configurar();
    f = TestBed.createComponent(CrudTable);
    for (const [k, v] of Object.entries({ titulo: 'Fincas', ruta: '/fincas', columnas: [], campos })) f.componentRef.setInput(k, v);
    f.detectChanges();
    el = f.nativeElement;
    http.expectOne((r) => r.url === '/api/fincas').flush(
      { error: { codigo: 'ERROR_INTERNO', mensaje: 'Algo falló.', request_id: 'abc123' } }, { status: 500, statusText: 'x' });
    await estable(f);
    expect(el.querySelector('[role=alert]')?.textContent).toContain('Algo falló. Código de soporte: abc123');
    boton(el, 'Reintentar').click();
    lista([]);
  });
});
