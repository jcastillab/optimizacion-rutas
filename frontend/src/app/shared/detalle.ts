const txt = (v: unknown) => (v !== null && typeof v === 'object' ? JSON.stringify(v) : String(v ?? '—'));

/** `detalle` llega como JSON en texto ({"antes":{..},"despues":{..}} u otro objeto); si no es JSON, el texto tal cual. */
export function lineasDetalle(detalle: string | null): string[] {
  if (!detalle) return [];
  let d: unknown;
  try {
    d = JSON.parse(detalle);
  } catch {
    return [detalle];
  }
  if (d === null || typeof d !== 'object' || Array.isArray(d)) return [txt(d)];
  const o = d as Record<string, unknown>;
  const a = o['antes'];
  const z = o['despues'];
  if (a && z && typeof a === 'object' && typeof z === 'object') {
    const antes = a as Record<string, unknown>;
    const despues = z as Record<string, unknown>;
    const campos = [...new Set([...Object.keys(antes), ...Object.keys(despues)])];
    const extra = Object.entries(o).filter(([k]) => k !== 'antes' && k !== 'despues').map(([k, v]) => `${k}: ${txt(v)}`);
    return [...campos.map((c) => `${c}: ${txt(antes[c])} → ${txt(despues[c])}`), ...extra];
  }
  return Object.entries(o).map(([k, v]) => `${k}: ${txt(v)}`);
}
