import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter, Routes } from '@angular/router';
import { proveedorLocale } from './core/locale';

/** Configuración común de las pruebas: HTTP simulado, router vacío y el mismo locale que la app. */
export function configurar(rutas: Routes = [{ path: '**', children: [] }]) {
  TestBed.configureTestingModule({
    providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter(rutas), proveedorLocale],
  });
  return TestBed.inject(HttpTestingController);
}

export const pagina = (items: unknown[], total = items.length, p = 1, porPagina = 25) => ({ items, total, pagina: p, por_pagina: porPagina });

export async function estable(f: ComponentFixture<unknown>) {
  f.detectChanges();
  await f.whenStable();
  f.detectChanges();
}

/** Escribe en un campo como lo haría una persona (dispara el evento input). */
export function escribir(el: HTMLInputElement | HTMLSelectElement, valor: string) {
  el.value = valor;
  el.dispatchEvent(new Event(el instanceof HTMLSelectElement ? 'change' : 'input', { bubbles: true }));
}

export function boton(raiz: HTMLElement, texto: string | RegExp, selector = 'button, a'): HTMLElement {
  const el = [...raiz.querySelectorAll<HTMLElement>(selector)].find((b) =>
    typeof texto === 'string' ? b.textContent?.trim() === texto : texto.test(b.textContent ?? ''),
  );
  if (!el) throw new Error(`No hay botón "${texto}"`);
  return el;
}
