import { HttpClient, HttpHeaders } from  '@angular/common/http';
import { Injectable } from  '@angular/core';

import { environment } from 'src/environments/environment';

@Injectable()
export class LightsService {

	private getBulbListUrl = environment['api_host'] + 'getWizBulbs';
	private getBulbStatusUrl = environment['api_host'] + 'getWizBulbStatus';
	private setBulbStatusUrl = environment['api_host'] + 'setWizBulbs';

	constructor(private http: HttpClient) { }

	getBulbList() {
		return this.http.get<any>(this.getBulbListUrl);
	}

	getSingleBulbStatus(bulb: {name: string, ip: string}) {
		return this.http.post<any>(this.getBulbStatusUrl, bulb);
	}

	setBulbStatus(bulbStatus) {
		let headers = new HttpHeaders().set('Content-Type', 'application/json');
		return this.http.post<any[]>(this.setBulbStatusUrl, bulbStatus, {headers: headers});
	}
}
