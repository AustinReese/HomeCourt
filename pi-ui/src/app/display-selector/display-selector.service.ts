import { HttpClient, HttpHeaders } from  '@angular/common/http';
import { Injectable } from  '@angular/core';

import { environment } from 'src/environments/environment';

@Injectable()
export class DisplaySelectorService {

	private displayOptionsURL = environment['api_host'] + 'getDisplayOptions';
	private submitOptionsURL = environment['api_host'] + 'submitApplicationOptions';

	constructor(private http: HttpClient) { }

	getDisplayOptions() {
    let headers = new HttpHeaders().set('Content-Type', 'application/json');
		return this.http.get<any[]>(this.displayOptionsURL);
	}

	postDisplayOptions(controlsToPass) {
		let headers = new HttpHeaders().set('Content-Type', 'application/json');
		return this.http.post<any[]>(this.submitOptionsURL, controlsToPass, {headers: headers});
  }
}
