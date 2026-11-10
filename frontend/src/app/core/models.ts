export type Rol = 'admin' | 'lector';
export interface Usuario { id: number; usuario: string; nombre: string; rol: Rol; activo: boolean; }
export interface Pagina<T> { items: T[]; total: number; pagina: number; por_pagina: number; }
export interface ErrorDetalle { campo: string; mensaje: string; }
export interface Parada { id: number; nombre: string; lat: number; lon: number; }
export interface Resumen {
  rutas: number; buses: number; personas: number; costo_total: number;
  costo_red_actual: number; diferencia_pct: number | null; personas_sin_servicio: number; personas_sin_paradero?: number;
  /** Siempre en corridas nuevas; puede faltar en las viejas. */
  advertencias?: string[];
  /** Indicadores: solo en corridas nuevas. */
  ocupacion_pct?: number | null; costo_por_persona?: number | null; km_total?: number;
  minutos_prom?: number | null; minutos_max?: number | null; cobertura_pct?: number | null;
}
export interface RutaSimulada {
  ruta_simulada: number; finca_id: number; finca_nombre?: string; paraderos: Parada[]; personas: number; km: number;
  minutos_max: number; tipo_bus: string; capacidad: number; buses: number; costo_total: number;
}
export interface SinServicio { finca_id: number; paradero_id: number; personas: number; }
export interface Corrida {
  id: number; creada: string; usuario: string;
  parametros: { velocidad_kmh: number; tiempo_max_min: number };
  resumen: Resumen; rutas?: RutaSimulada[]; sin_servicio?: SinServicio[];
}
export interface Evento {
  id: number; fecha: string; usuario: string | null; accion: string; entidad: string | null;
  entidad_id: number | null; detalle: string | null; request_id: string | null;
}
export interface Finca { id: number; nombre: string; cod_nivel2: number | null; lat: number; lon: number; activo: boolean; }
