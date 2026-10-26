import { DatePipe } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { forkJoin } from 'rxjs';
import { ApiError, ApiService } from '../core/api.service';
import { AuthService } from '../core/auth.service';
import { CatalogosService } from '../core/catalogos.service';
import { Corrida } from '../core/models';
import { CorridaResultado } from '../shared/corrida-resultado';

@Component({
  selector: 'app-inicio',
  imports: [DatePipe, RouterLink, CorridaResultado],
  template: `
    <h1>Hola, {{ auth.usuario()?.nombre }}</h1>
    <div aria-live="polite">
      @if (error()) { <p class="estado error" role="alert">{{ error() }}</p> }
      @else if (cargando()) { <p class="estado">Cargando…</p> }
    </div>
    @if (!cargando() && !error()) {
      <dl class="kpis">
        <div><dt>Personas</dt><dd><a [routerLink]="['/personas']">{{ totales().personas }}</a></dd></div>
        <div><dt>Fincas</dt><dd><a [routerLink]="['/fincas']">{{ cat.fincas().length }}</a></dd></div>
        <div><dt>Paraderos</dt><dd><a [routerLink]="['/paraderos']">{{ cat.paraderos().length }}</a></dd></div>
        <div><dt>Tipos de bus</dt><dd><a [routerLink]="['/tipos-bus']">{{ totales().tipos }}</a></dd></div>
      </dl>
      @if (ultima(); as c) {
        <h2>Última corrida (#{{ c.id }}, {{ c.creada | date: 'dd/MM/yyyy HH:mm' }}, {{ c.usuario }})</h2>
        <app-corrida-resultado [corrida]="c" />
      } @else {
        <p>Aún no hay corridas. <a [routerLink]="['/simulador']">Ejecutar el simulador</a>.</p>
      }
    }
  `,
})
export class Inicio implements OnInit {
  auth = inject(AuthService);
  private api = inject(ApiService);
  cat = inject(CatalogosService);
  cargando = signal(true);
  error = signal('');
  totales = signal({ personas: 0, tipos: 0 });
  ultima = signal<Corrida | null>(null);

  ngOnInit() {
    this.cat.asegurar();
    const uno = { por_pagina: 1 };
    forkJoin({
      personas: this.api.lista('/personas', uno),
      tipos: this.api.lista('/tipos-bus', uno),
      corridas: this.api.lista<Corrida>('/corridas', uno),
    }).subscribe({
      next: (r) => {
        this.totales.set({ personas: r.personas.total, tipos: r.tipos.total });
        const id = r.corridas.items[0]?.id;
        if (id == null) return this.cargando.set(false);
        this.api.get<Corrida>(`/corridas/${id}`).subscribe({
          next: (c) => { this.ultima.set(c); this.cargando.set(false); },
          error: (e: ApiError) => { this.error.set(e.message); this.cargando.set(false); },
        });
      },
      error: (e: ApiError) => { this.error.set(e.message); this.cargando.set(false); },
    });
  }
}
