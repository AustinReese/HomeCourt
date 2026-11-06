import { Component, OnInit } from '@angular/core';

import { DisplaySelectorService } from './display-selector.service';

/** Tile accents. Bold primaries only — muted colors look broken on black. */
const ACCENTS = {
  nfl:    '#e8352a',  // red
  nba:    '#f5b301',  // yellow
  snake:  '#19b55a',  // green
  film:   '#f2e4c0',  // warm ivory — not a primary, but bright enough to hold
  weather:'#00c2ff',  // sky blue
  clock:  '#1877f2',  // blue
  mnconn: '#00b4d8',  // cyan
  test:   '#9b5de5'   // violet
};
const DEFAULT_ACCENT = '#1877f2';

/** Collapse a burst of taps into one restart of the LED process. */
const PUSH_DEBOUNCE_MS = 300;

@Component({
  selector: 'app-display-selector',
  templateUrl: './display-selector.component.html',
  styleUrls: ['./display-selector.component.css'],
  providers: [DisplaySelectorService]
})
export class DisplaySelectorComponent implements OnInit {

  loading = true;
  loadFailed = false;
  power = false;
  selectedKey = '';
  /** displayOptionKey -> chosen value, kept for every display so switching back remembers. */
  values: { [key: string]: any } = {};
  displays: any[] = [];
  status = '';

  private pushTimer: any = null;

  constructor(private displaySelectorService: DisplaySelectorService) { }

  ngOnInit(): void {
    this.displaySelectorService.getDisplayOptions().subscribe({
      next: (result) => {
        const all = result && result['result'] ? result['result'] : [];
        // 'off' is still a real display to the LED controller, but here it is
        // the power switch, not a tile.
        this.displays = all.filter((d) => d['displayKey'] !== 'off');
        for (const display of this.displays) {
          display['accent'] = ACCENTS[display['displayKey']] || DEFAULT_ACCENT;
          for (const option of display['displayOptions']) {
            this.values[option['displayOptionKey']] = this.defaultValue(option);
          }
        }
        if (this.displays.length) {
          this.selectedKey = this.displays[0]['displayKey'];
        }
        this.loadCurrent();
      },
      error: () => {
        this.loading = false;
        this.loadFailed = true;
      }
    });
  }

  private defaultValue(option) {
    if (option['formType'] === 'checkbox') {
      return false;
    }
    const selections = option['displayOptionSelections'];
    return selections && selections.length ? selections[0]['selectionKey'] : '';
  }

  /** Seed the controls from whatever the sign is showing, so the UI isn't a guess. */
  private loadCurrent() {
    this.displaySelectorService.getCurrentDisplay().subscribe({
      next: (result) => {
        const current = result ? result['result'] : null;
        if (current && current['display']) {
          if (current['display'] === 'off') {
            this.power = false;
          } else if (this.displays.some((d) => d['displayKey'] === current['display'])) {
            this.selectedKey = current['display'];
            this.power = true;
            for (const key of Object.keys(current)) {
              if (key !== 'display' && key in this.values) {
                this.values[key] = current[key];
              }
            }
          }
        }
        this.loading = false;
      },
      error: () => { this.loading = false; }
    });
  }

  get selectedDisplay() {
    return this.displays.find((d) => d['displayKey'] === this.selectedKey);
  }

  get selectedOptions() {
    const display = this.selectedDisplay;
    return display ? display['displayOptions'] : [];
  }

  get accent() {
    const display = this.selectedDisplay;
    return display ? display['accent'] : DEFAULT_ACCENT;
  }

  get statusText() {
    if (this.loading) { return 'Checking the sign…'; }
    if (this.loadFailed) { return 'Can’t reach the sign'; }
    if (!this.power) { return 'Off'; }
    const display = this.selectedDisplay;
    return display ? 'Showing ' + display['displayName'] : 'On';
  }

  togglePower() {
    this.power = !this.power;
    this.push();
  }

  selectDisplay(key: string) {
    // Picking a display while the sign is off turns it on, which is what
    // tapping a tile obviously means.
    if (this.selectedKey === key && this.power) { return; }
    this.selectedKey = key;
    this.power = true;
    this.push();
  }

  chooseSelection(optionKey: string, selectionKey: string) {
    if (this.values[optionKey] === selectionKey) { return; }
    this.values[optionKey] = selectionKey;
    this.push();
  }

  toggleCheckbox(optionKey: string) {
    this.values[optionKey] = !this.values[optionKey];
    this.push();
  }

  private buildPayload() {
    if (!this.power) {
      return { display: 'off' };
    }
    const payload = { display: this.selectedKey };
    for (const option of this.selectedOptions) {
      const key = option['displayOptionKey'];
      payload[key] = this.values[key];
    }
    return payload;
  }

  private push() {
    this.status = 'sending';
    if (this.pushTimer) { clearTimeout(this.pushTimer); }
    this.pushTimer = setTimeout(() => {
      this.pushTimer = null;
      this.displaySelectorService.postDisplayOptions(this.buildPayload()).subscribe({
        next: (result) => {
          this.status = result && result['result'] === 'success' ? 'ok' : 'error';
          this.clearStatusLater();
        },
        error: () => {
          this.status = 'error';
          this.clearStatusLater();
        }
      });
    }, PUSH_DEBOUNCE_MS);
  }

  private clearStatusLater() {
    setTimeout(() => {
      if (this.status !== 'sending') { this.status = ''; }
    }, 1600);
  }
}
