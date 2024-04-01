import { HttpClient, HttpHeaders } from  '@angular/common/http';
import { Injectable } from  '@angular/core';

import { environment } from 'src/environments/environment';

@Injectable()
export class HomeService {

	private temperatureReportUrl = environment['api_host'] + 'getTemperatureReport';

	constructor(private http: HttpClient) { }

	getTemperatureReport() {
    	let headers = new HttpHeaders().set('Content-Type', 'application/json');
		return this.http.get<any[]>(this.temperatureReportUrl);
	}
}
