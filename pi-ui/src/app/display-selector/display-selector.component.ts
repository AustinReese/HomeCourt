import { Component, OnInit } from '@angular/core';
import { AbstractControl, FormBuilder, FormControl, FormGroup, Validators } from '@angular/forms';

import { MatSelectModule } from '@angular/material/select';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatCheckboxModule } from '@angular/material/checkbox';

import { DisplaySelectorService } from './display-selector.service';

@Component({
  selector: 'app-display-selector',
  templateUrl: './display-selector.component.html',
  styleUrls: ['./display-selector.component.css'],
  providers: [DisplaySelectorService]
})
export class DisplaySelectorComponent implements OnInit {

  displayOptionsLoaded = false;
  isSubmitted = false;
  form = new FormGroup({
    clock_hour_format: new FormControl(''),
    nfl_live_updates: new FormControl(''),
    selectedDisplay: new FormControl(''),
    test_script: new FormControl('')
  });
  displays = {
    'Off': 'off',
    'NFL Scoreboard': 'nfl',
    'NBA Scoreboard': 'nba',
    'Test': 'test', 
    'Clock': 'clock',
    'MNConn Scoreboard': 'mnconn'
  }
  selectedDisplayOptions: {}
  allDisplayOptions = []


  get selectedDisplay() {
    return this.form.get('selectedDisplay');
  }

  get selectedDisplayString() {
    return this.form.value['selectedDisplay']
  }


  constructor(private formBuilder: FormBuilder,
    private displaySelectorService: DisplaySelectorService) { }

  ngOnInit(): void {
    this.displaySelectorService.getDisplayOptions().subscribe((result) => {
      this.allDisplayOptions = result['result'];
      let formObject = { selectedDisplay: new FormControl('') }
      for (const [key, value] of Object.entries(this.allDisplayOptions)) {
        for (let optionIdx in value){
          formObject[value[optionIdx]['displayOptionKey']] = new FormControl('')
        }
      }
    this.form = this.formBuilder.group(formObject)
    })
  }


  changeDisplay(e) {
    this.displayOptionsLoaded = false;
    this.selectedDisplay.setValue(e.value, {
      onlySelf: true
    })
    this.selectedDisplayOptions = this.allDisplayOptions[this.selectedDisplayString];
    this.displayOptionsLoaded = true;
  }


  onSubmit() {
    this.isSubmitted = true;
    if (!this.form.valid) {
      console.log("Form Invalid")
      return false;
    } else {
      let controlsToPass = { 'display': this.selectedDisplayString};
      for (let control in this.form.controls){
        if (control.startsWith(this.selectedDisplayString)){
          if (this.form.controls[control].value == ''){
            controlsToPass[control] = false;
          } else{
            controlsToPass[control] = this.form.controls[control].value;
          }
        }
      }
      this.displaySelectorService.postDisplayOptions(controlsToPass).subscribe((result) => {
        console.log(result)
      })
    }
  }
}
