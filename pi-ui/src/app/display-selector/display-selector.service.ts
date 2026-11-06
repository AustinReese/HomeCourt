import { HttpClient, HttpHeaders } from  '@angular/common/http';
import { Injectable } from  '@angular/core';

import { environment } from 'src/environments/environment';

@Injectable()
export class DisplaySelectorService {

	private displayOptionsURL = environment['api_host'] + 'getDisplayOptions';
	private submitOptionsURL = environment['api_host'] + 'submitApplicationOptions';
	private currentDisplayURL = environment['api_host'] + 'getCurrentDisplay';

	constructor(private http: HttpClient) { }

	getDisplayOptions() {
		return this.http.get<any>(this.displayOptionsURL);
	}

	/** What the LED controller is actually running right now. */
	getCurrentDisplay() {
		return this.http.get<any>(this.currentDisplayURL);
	}

	postDisplayOptions(controlsToPass) {
		let headers = new HttpHeaders().set('Content-Type', 'application/json');
		return this.http.post<any>(this.submitOptionsURL, controlsToPass, {headers: headers});
	}
}
