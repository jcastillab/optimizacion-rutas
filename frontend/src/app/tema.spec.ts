
// Contraste WCAG de los tokens reales de styles.css (claro y oscuro).
type Tokens = Record<string, string>;

async function leerTokens(): Promise<{ claro: Tokens; oscuro: Tokens }> {
  // jsdom no inyecta styles.css: se lee el archivo real (especificador calculado para no requerir @types/node)
  const modulo = 'node:' + 'fs';
  const fs = await import(/* @vite-ignore */ modulo);
  const css: string = fs.readFileSync('src/styles.css', 'utf-8');

  const bloques = [...css.matchAll(/:root\s*\{([^}]*)\}/g)].map((m) => m[1]);
  const aTokens = (b: string): Tokens => Object.fromEntries([...b.matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)].map((m) => [m[1], m[2].trim()]));
  const [claro, oscuro] = bloques.map(aTokens);
  expect(css).toContain('prefers-color-scheme: dark'); // el segundo bloque es el del modo oscuro
  return { claro, oscuro: { ...claro, ...oscuro } };
}

const luz = (hex: string) => {
  const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
};
const contraste = (a: string, b: string) => {
  const [x, y] = [luz(a), luz(b)].sort((p, q) => q - p);
  return (x + 0.05) / (y + 0.05);
};

// [texto, fondo] como se usan en styles.css
const PARES: [string, string][] = [
  ['--texto', '--fondo'], ['--texto', '--superficie'], ['--suave', '--fondo'], ['--suave', '--superficie'],
  ['--enlace', '--fondo'], ['--enlace', '--superficie'],
  ['--cabecera-texto', '--cabecera-fondo'], ['--primario-texto', '--primario-fondo'], ['--activo-texto', '--activo-fondo'],
  ['--error', '--fondo'], ['--error', '--superficie'], ['--ok', '--superficie'],
];

describe('tema: contraste de los tokens (>= 4,5:1)', async () => {
  const { claro, oscuro } = await leerTokens();

  it('la hoja de estilos se cargó (si no, la prueba no prueba nada)', () => {
    expect(claro['--texto']).toMatch(/^#/);
    expect(oscuro['--primario-texto']).not.toBe(claro['--primario-texto']);
  });

  for (const [nombre, tokens] of [['claro', claro], ['oscuro', oscuro]] as const) {
    for (const [t, f] of PARES) {
      it(`${nombre}: ${t} sobre ${f}`, () => {
        expect(tokens[t], t).toMatch(/^#[0-9a-f]{6}$/i);
        expect(tokens[f], f).toMatch(/^#[0-9a-f]{6}$/i);
        expect(contraste(tokens[t], tokens[f])).toBeGreaterThanOrEqual(4.5);
      });
    }
  }
});
