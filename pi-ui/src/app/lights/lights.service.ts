import { HttpClient, HttpHeaders } from  '@angular/common/http';
import { Injectable } from  '@angular/core';

import { environment } from 'src/environments/environment';

@Injectable()
export class LightsService {

	private getBulbStatusUrl = environment['api_host'] + 'getWizBulbs';
	private setBulbStatusUrl = environment['api_host'] + 'setWizBulbs';


	constructor(private http: HttpClient) { }

	getBulbStatus() {
    	let headers = new HttpHeaders().set('Content-Type', 'application/json');
		return this.http.get<any[]>(this.getBulbStatusUrl);
	}

	setBulbStatus(bulbStatus) {
		let headers = new HttpHeaders().set('Content-Type', 'application/json');
		return this.http.post<any[]>(this.setBulbStatusUrl, bulbStatus, {headers: headers});
	}
}
