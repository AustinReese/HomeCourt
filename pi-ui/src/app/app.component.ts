import { Component } from '@angular/core';
import { DisplaySelectorComponent } from './display-selector/display-selector.component';

@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.css'],
})

export class AppComponent {
  title = 'pi-ui';
  selectedApp = 'lights'

  homeSelect(){
    this.selectedApp = 'home'
  }

  lightsSelect(){
    this.selectedApp = 'lights'
  }

  linksSelect(){
    this.selectedApp = 'links'
  }

  ledSelect(){
    this.selectedApp = 'led'
  }
}
