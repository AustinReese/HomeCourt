import { ComponentFixture, TestBed, waitForAsync } from '@angular/core/testing';

import { DisplaySelectorComponent } from './display-selector.component';

describe('DisplaySelectorComponent', () => {
  let component: DisplaySelectorComponent;
  let fixture: ComponentFixture<DisplaySelectorComponent>;

  beforeEach(waitForAsync(() => {
    TestBed.configureTestingModule({
      declarations: [ DisplaySelectorComponent ]
    })
    .compileComponents();
  }));

  beforeEach(() => {
    fixture = TestBed.createComponent(DisplaySelectorComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
