import { Component, OnInit } from '@angular/core';
import { FormControl, ReactiveFormsModule } from '@angular/forms';

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
    this.lightsService.getBulbStatus().subscribe((result) => {
      if (result['result'] != 'error'){
        for (const device of result['result']){          
          this.devices.push({
            name: device.name,
            color: this.rgbToHex(device.r, device.g, device.b),
            brightness: device.brightness,
            status: device.status,
            ip: device.ip
          })
        }
      }
      else {
      }
    })
    console.log(this.devices)
  }

  hexToRgb(hex) {
    return hex.replace(/^#?([a-f\d])([a-f\d])([a-f\d])$/i
      ,(m, r, g, b) => '#' + r + r + g + g + b + b)
      .substring(1).match(/.{2}/g)
      .map(x => parseInt(x, 16))
  }

  rgbToHex = (r, g, b) => '#' + [r, g, b].map(x => {
    const hex = x.toString(16)
    return hex.length === 1 ? '0' + hex : hex
  }).join('')
  
  deviceChanged(device) {
    let post = { ...device }
    post.color = this.hexToRgb(device.color)
    this.lightsService.setBulbStatus(post).subscribe((result) => {
      console.log(result);
    });
  }

  statusChanged(device) {
    console.log(device);
    var post = { ...this.devices[0] }
    post.color = this.hexToRgb(this.devices[0].color)

    this.lightsService.setBulbStatus(post).subscribe((result) => {
      console.log(result);
    });
  }

  colorChanged(device) {
    var post = { ...this.devices[0] }
    post.color = this.hexToRgb(this.devices[0].color)

    this.lightsService.setBulbStatus(post).subscribe((result) => {
      console.log(result);
    });
  }

  brightnessChanged(device) {
    var post = { ...this.devices[0] }
    post.color = this.hexToRgb(this.devices[0].color)

    this.lightsService.setBulbStatus(post).subscribe((result) => {
      console.log(result);
    });
  }

}
