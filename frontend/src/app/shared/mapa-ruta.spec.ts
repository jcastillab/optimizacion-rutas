import { proyectar } from './mapa-ruta';

describe('proyectar', () => {
  it('pone el norte arriba y el oeste a la izquierda, dentro del lienzo', () => {
    const [sur, norte] = proyectar([{ lat: 0, lon: 0 }, { lat: 1, lon: 1 }], 100, 100, 0);
    expect(sur.x).toBeCloseTo(0, 0);
    expect(sur.y).toBeCloseTo(100, 0);
    expect(norte.x).toBeCloseTo(100, 0);
    expect(norte.y).toBeCloseTo(0, 0);
  });
  it('no divide por cero con un solo punto ni con puntos alineados', () => {
    const uno = proyectar([{ lat: 4.8, lon: -74.2 }]);
    expect(Number.isFinite(uno[0].x) && Number.isFinite(uno[0].y)).toBe(true);
    const alineados = proyectar([{ lat: 4, lon: -74 }, { lat: 4.1, lon: -74 }]);
    expect(alineados.every((p) => Number.isFinite(p.x) && Number.isFinite(p.y))).toBe(true);
  });
});
