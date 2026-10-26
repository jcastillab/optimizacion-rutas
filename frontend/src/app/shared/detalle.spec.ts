import { lineasDetalle } from './detalle';

describe('lineasDetalle', () => {
  it('muestra antes → después por campo', () => {
    expect(lineasDetalle('{"antes":{"nombre":"A","lat":1},"despues":{"nombre":"B","lat":1}}'))
      .toEqual(['nombre: A → B', 'lat: 1 → 1']);
  });
  it('objeto plano y texto no JSON', () => {
    expect(lineasDetalle('{"fincas":{"creadas":3}}')).toEqual(['fincas: {"creadas":3}']);
    expect(lineasDetalle('hola <b>x</b>')).toEqual(['hola <b>x</b>']);
    expect(lineasDetalle(null)).toEqual([]);
  });
});
