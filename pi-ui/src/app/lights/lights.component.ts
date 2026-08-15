import { Component, OnInit } from '@angular/core';
import { ReactiveFormsModule } from '@angular/forms';

import { LightsService } from './lights.service'

@Component({
  selector: 'app-lights',
  templateUrl: './lights.component.html',
  styleUrls: ['./lights.component.css'],
  providers: [LightsService, ReactiveFormsModule]
})
export class LightsComponent implements OnInit {

  devices = [];

  constructor(private lightsService: LightsService) { }

  ngOnInit() {
    this.lightsService.getBulbList().subscribe((result) => {
      if (result['result'] != 'error') {
        for (const bulb of result['result']) {
          const index = this.devices.length;
          this.devices.push({
            name: bulb.name,
            ip: bulb.ip,
            loading: true,
            status: false,
            hue: 0,
            brightness: 100,
            mode: 'color',
            temp: 0,
            colorOpen: false
          });
          this.lightsService.getSingleBulbStatus(bulb).subscribe({
            next: (statusResult) => {
              const s = statusResult['result'];
              if (s != null && s != 'error') {
                const mode = s.temp != null ? 'temp' : 'color';
                this.devices[index] = {
                  name: s.name,
                  ip: s.ip,
                  loading: false,
                  status: s.status,
                  hue: s.r != null ? this.rgbToHue(s.r, s.g, s.b) : 0,
                  brightness: s.brightness,
                  mode: mode,
                  temp: s.temp || 0,
                  colorOpen: false
                };
              } else {
                this.devices[index].loading = false;
              }
            },
            error: () => {
              this.devices[index].loading = false;
            }
          });
        }
      }
    });
  }

  hslToRgb(h: number): number[] {
    const s = 1, l = 0.5;
    const c = (1 - Math.abs(2 * l - 1)) * s;
    const x = c * (1 - Math.abs((h / 60) % 2 - 1));
    const m = l - c / 2;
    let r = 0, g = 0, b = 0;
    if (h < 60) { r = c; g = x; }
    else if (h < 120) { r = x; g = c; }
    else if (h < 180) { g = c; b = x; }
    else if (h < 240) { g = x; b = c; }
    else if (h < 300) { r = x; b = c; }
    else { r = c; b = x; }
    return [Math.round((r + m) * 255), Math.round((g + m) * 255), Math.round((b + m) * 255)];
  }

  hslToHex(h: number): string {
    const [r, g, b] = this.hslToRgb(h);
    return '#' + [r, g, b].map(x => {
      const hex = (x || 0).toString(16);
      return hex.length === 1 ? '0' + hex : hex;
    }).join('');
  }

  rgbToHue(r: number, g: number, b: number): number {
    r /= 255; g /= 255; b /= 255;
    const max = Math.max(r, g, b), min = Math.min(r, g, b);
    const d = max - min;
    if (d === 0) return 0;
    let h = 0;
    if (max === r) h = ((g - b) / d) % 6;
    else if (max === g) h = (b - r) / d + 2;
    else h = (r - g) / d + 4;
    h = Math.round(h * 60);
    return h < 0 ? h + 360 : h;
  }

  getCurrentColor(device): string {
    if (device.mode === 'temp') {
      switch (device.temp) {
        case 2700: return '#ffcc66';
        case 4000: return '#fffbe6';
        case 6500: return '#cce6ff';
        default: return '#fff';
      }
    }
    return this.hslToHex(device.hue);
  }

  getCurrentLabel(device): string {
    if (device.mode === 'temp') {
      switch (device.temp) {
        case 2700: return 'Warm White';
        case 4000: return 'Daylight';
        case 6500: return 'Cool White';
        default: return 'White';
      }
    }
    return 'Custom Color';
  }

  togglePower(device) {
    device.status = !device.status;
    this.statusChanged(device);
  }

  colorChanged(device) {
    device.mode = 'color';
    device.temp = 0;
    const [r, g, b] = this.hslToRgb(device.hue);
    this.lightsService.setBulbStatus({
      name: device.name, ip: device.ip,
      status: true, color: [r, g, b], brightness: device.brightness
    }).subscribe(() => {});
  }

  tempChanged(device, kelvin: number) {
    device.mode = 'temp';
    device.temp = kelvin;
    this.lightsService.setBulbStatus({
      name: device.name, ip: device.ip,
      status: true, temp: kelvin, brightness: device.brightness
    }).subscribe(() => {});
  }

  brightnessChanged(device) {
    if (device.mode === 'temp') {
      this.tempChanged(device, device.temp);
    } else {
      this.colorChanged(device);
    }
  }

  statusChanged(device) {
    if (device.status) {
      if (device.mode === 'temp') {
        this.tempChanged(device, device.temp);
      } else {
        this.colorChanged(device);
      }
    } else {
      this.lightsService.setBulbStatus({
        name: device.name, ip: device.ip, status: false,
        color: [0, 0, 0], brightness: 0
      }).subscribe(() => {});
    }
  }
}
