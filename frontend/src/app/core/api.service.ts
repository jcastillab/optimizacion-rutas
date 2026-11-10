import { HttpClient, HttpErrorResponse, HttpParameterCodec, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, Subject, catchError, tap, throwError } from 'rxjs';
import { ErrorDetalle, Pagina } from './models';

/** Error del contrato ya traducido a algo legible. */
export class ApiError extends Error {
  constructor(
    public status: number,
    public codigo: string,
    mensaje: string,
    public detalle: ErrorDetalle[] | null = null,
    public requestId: string | null = null,
  ) {
    super(mensaje);
  }
  /** Mensajes de validacion indexados por campo. */
  porCampo(): Record<string, string> {
    return Object.fromEntries((this.detalle ?? []).map((d) => [d.campo, d.mensaje]));
  }
}

/** Codifica todo con encodeURIComponent: el codec por defecto deja pasar "+", que el servidor lee como espacio. */
class CodecEstricto implements HttpParameterCodec {
  encodeKey = (k: string) => encodeURIComponent(k);
  encodeValue = (v: string) => encodeURIComponent(v);
  decodeKey = (k: string) => decodeURIComponent(k);
  decodeValue = (v: string) => decodeURIComponent(v);
}

export type Params = Record<string, string | number | boolean | null | undefined>;

const MENSAJES_SIN_CUERPO: Record<number, string> = {
  0: 'No se pudo conectar con el servidor.',
  403: 'No tienes permiso para esta acción.',
  429: 'Demasiados intentos, espera unos minutos.',
};

@Injectable({ providedIn: 'root' })
export class ApiService {
  private http = inject(HttpClient);
  /** Emite cuando el servidor responde 401 (sesion vencida o ausente). */
  readonly noAutenticado = new Subject<void>();
  /** Emite la ruta de cada escritura (POST/PATCH/DELETE) que termino bien; sirve para invalidar caches. */
  readonly escrituras = new Subject<string>();

  private opts(params?: Params) {
    const p: Record<string, string> = {};
    for (const [k, v] of Object.entries(params ?? {})) {
      if (v !== null && v !== undefined && v !== '') p[k] = String(v);
    }
    return { withCredentials: true, params: new HttpParams({ fromObject: p, encoder: new CodecEstricto() }) };
  }

  private traducir = (e: HttpErrorResponse): Observable<never> => {
    const cuerpo = e.error?.error;
    let err: ApiError;
    if (cuerpo) {
      const soporte = e.status >= 500 && cuerpo.request_id ? ` Código de soporte: ${cuerpo.request_id}` : '';
      err = new ApiError(e.status, cuerpo.codigo, `${cuerpo.mensaje}${soporte}`, cuerpo.detalle ?? null, cuerpo.request_id ?? null);
    } else {
      err = new ApiError(
        e.status,
        e.status === 0 ? 'SIN_CONEXION' : 'ERROR',
        MENSAJES_SIN_CUERPO[e.status] ?? `Error inesperado (${e.status}).`,
      );
    }
    if (e.status === 401) this.noAutenticado.next();
    return throwError(() => err);
  };

  get<T>(ruta: string, params?: Params) {
    return this.http.get<T>(`/api${ruta}`, this.opts(params)).pipe(catchError(this.traducir));
  }
  lista<T>(ruta: string, params?: Params) {
    return this.get<Pagina<T>>(ruta, params);
  }
  post<T>(ruta: string, cuerpo: unknown = {}, params?: Params) {
    return this.http.post<T>(`/api${ruta}`, cuerpo, this.opts(params)).pipe(tap(() => this.escrituras.next(ruta)), catchError(this.traducir));
  }
  patch<T>(ruta: string, cuerpo: unknown) {
    return this.http.patch<T>(`/api${ruta}`, cuerpo, this.opts()).pipe(tap(() => this.escrituras.next(ruta)), catchError(this.traducir));
  }
  delete(ruta: string) {
    return this.http.delete<void>(`/api${ruta}`, this.opts()).pipe(tap(() => this.escrituras.next(ruta)), catchError(this.traducir));
  }
}
