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
  graph = {}
  numberOfDays = 7;

  constructor(private homeService: HomeService) { }

  ngOnInit() {
    this.resetGraph()

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

  resetGraph() {
    this.homeService.getAllTemperatures(this.numberOfDays).subscribe((result) => {
      this.graph = {
        data: [
          {type: "scatter", mode:"lines", x: result["result"]["basement"]["x"].map(dateString => new Date(dateString)), y: result["result"]["basement"]["y"], name:"Basement"},
          {type: "scatter", mode:"lines", x: result["result"]["1st floor"]["x"].map(dateString => new Date(dateString)), y: result["result"]["1st floor"]["y"], name:"1st Floor"},
          {type: "scatter", mode:"lines", x: result["result"]["upstairs"]["x"].map(dateString => new Date(dateString)), y: result["result"]["upstairs"]["y"], name:"Upstairs"}
        ],
        layout: {
          title: 'STATE OF THE TOWNHOME',
          yaxis: {
            title: 'Degrees Fahrenheit'
          }
        }
      };
    })
  }
}
