import { Component, OnInit } from '@angular/core';

import { HomeService } from './home.service';

@Component({
  selector: 'app-home',
  templateUrl: './home.component.html',
  styleUrls: ['./home.component.css'],
  providers: [HomeService]
})
export class HomeComponent implements OnInit {

  temperatureNodes = []

  constructor(private homeService: HomeService) { }

  ngOnInit() {
    this.homeService.getTemperatureReport().subscribe((result) => {
      var resultObject = result['result'];
      if (resultObject == 'error') {
        this.temperatureNodes = []
      }
      else {
        resultObject[0]["Temperature"] = resultObject[0]["Temperature"] + String.fromCodePoint(8457)
        resultObject[0]["Humidity"] = resultObject[0]["Humidity"] + '%'
        var battery: number = (resultObject[0]["Battery"] as number)
        resultObject[0]["Battery"] = Math.floor((battery / 3600) * 100) + '%'
        this.temperatureNodes = result['result'];
      }
    })
  }
}
