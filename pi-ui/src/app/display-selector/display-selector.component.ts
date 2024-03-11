import { Component, OnInit } from '@angular/core';
import { AbstractControl, UntypedFormBuilder, UntypedFormControl, UntypedFormGroup, Validators } from '@angular/forms';

import { MatSelectModule as MatSelectModule } from '@angular/material/select';
import { MatFormFieldModule as MatFormFieldModule } from '@angular/material/form-field';
import { MatCheckboxModule as MatCheckboxModule } from '@angular/material/checkbox';

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
  form = new UntypedFormGroup({
    clock_hour_format: new UntypedFormControl(''),
    nfl_live_updates: new UntypedFormControl(''),
    selectedDisplay: new UntypedFormControl(''),
    test_script: new UntypedFormControl('')
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


  constructor(private formBuilder: UntypedFormBuilder,
    private displaySelectorService: DisplaySelectorService) { }

  ngOnInit(): void {
    this.displaySelectorService.getDisplayOptions().subscribe((result) => {
      this.allDisplayOptions = result['result'];
      let formObject = { selectedDisplay: new UntypedFormControl('') }
      for (const [key, value] of Object.entries(this.allDisplayOptions)) {
        for (let optionIdx in value){
          formObject[value[optionIdx]['displayOptionKey']] = new UntypedFormControl('')
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
