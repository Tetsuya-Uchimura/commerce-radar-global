import {describe,it,expect} from 'vitest';
import {mapCountries} from '../mapLayers';
import {countryColor} from '../WorldMap';
import type {Country} from '../api';
import type {AutomaticResult} from '../useAutomaticDiscovery';
const country={code:'JP',name:'Japan',score:90,band:'Demo',offer_count:5,complete_count:5,explanation:'Synthetic',currency:'JPY',map_id:'392',longitude:138,latitude:37,fx:null} as Country;
describe('map evidence separation',()=>{
 it('colors exploration targets without inventing any opportunity score',()=>{
  const [c]=mapCountries([country],null,undefined,undefined,'discovery',false);
  expect(c.score).toBeNull();expect(c.exploration?.seller_location_verified).toBe(false);
  expect(countryColor(c)).toBe('#9c874f');
  expect(c.explanation).toContain('not verified');
 });
 it('keeps the verified layer empty until explicit country evidence exists',()=>{
  const [c]=mapCountries([country],{countries:[]} as unknown as AutomaticResult,undefined,undefined,'verified',false);
  expect(c.score).toBeNull();expect(c.offer_count).toBe(0);expect(c.exploration).toBeUndefined();
  expect(countryColor(c)).toBe('#293f51');
 });
 it('uses actual confirmed country matches and preserves explicit Demo mode',()=>{
  const result={countries:[{code:'JP',score:74,offer_count:2,complete_count:0,basis:'Source-observed seller location'}]} as unknown as AutomaticResult;
  expect(mapCountries([country],result,undefined,undefined,'verified',false)[0].score).toBe(74);
  expect(mapCountries([country],result,undefined,undefined,'discovery',true)[0].score).toBe(90);
  expect(mapCountries([country],result,undefined,undefined,'discovery',false,'JP')).toHaveLength(0);
 });
});
