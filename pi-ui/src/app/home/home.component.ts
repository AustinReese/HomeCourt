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
        for (let i = 0; i < resultObject.length; i++) {
          resultObject[i]["Temperature"] = resultObject[i]["Temperature"] + String.fromCodePoint(8457)
          resultObject[i]["Humidity"] = resultObject[i]["Humidity"] + '%'
          var battery: number = (resultObject[i]["Battery"] as number)
          //resultObject[i]["Battery"] = Math.floor((battery / 4200) * 100) + '%'
          this.temperatureNodes = result['result'];
        }
      }
    })
  }
}
