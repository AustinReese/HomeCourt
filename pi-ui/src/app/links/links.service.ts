import { HttpClient, HttpHeaders } from  '@angular/common/http';
import { Injectable } from  '@angular/core';

import { environment } from 'src/environments/environment';

@Injectable()
export class LinksService {

	private temperatureReportUrl = environment['api_host'] + 'getTemperatureReport';

	constructor(private http: HttpClient) { }

}
