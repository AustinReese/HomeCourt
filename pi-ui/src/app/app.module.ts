import { BrowserModule } from '@angular/platform-browser';
import { BrowserAnimationsModule } from '@angular/platform-browser/animations';
import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';

import { AppComponent } from './app.component';
import { DisplaySelectorComponent } from './display-selector/display-selector.component';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';
import { HttpClient, HttpClientModule } from '@angular/common/http';

import { MatSelectModule as MatSelectModule } from '@angular/material/select';
import { MatFormFieldModule as MatFormFieldModule } from '@angular/material/form-field';
import { MatCheckboxModule as MatCheckboxModule } from '@angular/material/checkbox';
import { MatSlideToggleModule } from '@angular/material/slide-toggle'; 
import { MatInputModule } from '@angular/material/input'; 

import { HomeComponent } from './home/home.component';
import { LinksComponent } from './links/links.component';
import { LightsComponent } from './lights/lights.component';

import { NgxColorsModule } from 'ngx-colors';

import * as PlotlyJS from 'plotly.js-dist-min';
import { PlotlyModule } from 'angular-plotly.js';

PlotlyModule.plotlyjs = PlotlyJS;

@NgModule({
  declarations: [
    AppComponent,
    DisplaySelectorComponent,
    HomeComponent,
    LinksComponent,
    LightsComponent,
  ],
  imports: [
    BrowserModule,
    CommonModule,
    FormsModule,
    HttpClientModule,
    ReactiveFormsModule,
    BrowserAnimationsModule,
    MatSelectModule,
    MatFormFieldModule,
    MatCheckboxModule,
    MatSlideToggleModule,
    MatInputModule,
    NgxColorsModule,
    PlotlyModule
  ],
  providers: [],
  bootstrap: [AppComponent]
})
export class AppModule { }
