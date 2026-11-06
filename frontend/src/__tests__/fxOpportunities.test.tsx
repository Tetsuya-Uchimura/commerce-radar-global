import {describe,it,expect} from 'vitest';
import {render,screen} from '@testing-library/react';
import {mapCountries} from '../mapLayers';
import {countryColor} from '../WorldMap';
import {ProductFXEvidence,type FXIntelligence,type ProductFX} from '../FXOpportunities';
import type {Country} from '../api';
import type {RealProduct} from '../useAutomaticDiscovery';
const selected={purchasing_power_advantage:'6.6667',constant_price_usd_cost_change:'-6.25',fx_score:66.7,classification:'favorable',reference_rate:'1.12',reference_date:'2026-08-01'};
const market={currency:'EUR',period:'90D',mode:'live',source:'Frankfurter v2',current_rate:'1.05',rate_date:'2026-11-01',retrieved_at:'2026-11-01T16:00:00Z',stale:false,eligible:true,status:'favorable',selected,comparisons:{'90D':selected}};
const intel={markets:[market],period:'90D',mode:'live',as_of:'2026-11-01',label:'Live Market FX',signature:'actual-fx',favorable_currencies:['EUR'],notice:'No price guarantee'} as FXIntelligence;
const base={score:99,offer_count:8,complete_count:8,currency:'EUR',fx:null} as Country;
describe('FX evidence and currency-region map',()=>{
 it('colors shared currency regions equally without assigning merchant origin or product counts',()=>{
  const rows=mapCountries([{...base,code:'PT',name:'Portugal'},{...base,code:'DE',name:'Germany'}],null,undefined,undefined,'fx',false,'',intel);
  expect(rows[0].score).toBe(rows[1].score);expect(rows[0].score).toBe(66.7);
  expect(rows[0].offer_count).toBe(0);expect(countryColor(rows[0])).toBe('#8de1d6');
  expect(rows[0].explanation).toContain('Not seller location');
 });
 it('does not manufacture personalized opportunity when only FX data exists',()=>{
  const [row]=mapCountries([{...base,code:'PT',name:'Portugal'}],null,undefined,undefined,'personalized',false,'',intel);
  expect(row.score).toBeNull();expect(row.offer_count).toBe(0);expect(countryColor(row)).toBe('#293f51');
 });
 it('shows exact computed hypothetical amounts and source/unknown costs',()=>{
  const fx={verified:true,favorable:true,listing_fresh:true,period:'90D',status:'FX-Backed Find',score:88.3,factors:{interest:100,fx:66.7,novelty:100,evidence:100},weights:{interest:45,fx:35,novelty:10,evidence:10},market,current_usd_minor:10500,historical_usd_minor:11200,difference_usd_minor:700,price_observed_at:'2026-11-01T16:00:00Z',price_source:'Official listing',caveat:'Assumes unchanged local price. Shipping and tax unknown.'} as ProductFX;
  render(<ProductFXEvidence p={{currency:'EUR',price_minor:10000,fx_opportunity:fx} as RealProduct}/>);
  expect(screen.getByText('Current USD Equivalent: $105.00')).toBeInTheDocument();
  expect(screen.getByText('Hypothetical USD Equivalent at Historical FX: $112.00')).toBeInTheDocument();
  expect(screen.getByText('Estimated FX-Related Difference: $7.00 lower')).toBeInTheDocument();
  expect(screen.getByText(/Delivery Unknown/)).toBeInTheDocument();
 });
 it('never displays hypothetical benefit amounts for USD or unknown currency evidence',()=>{
  render(<ProductFXEvidence p={{currency:'USD',price_minor:1000,fx_opportunity:{verified:false,favorable:false,status:'USD listing · no foreign FX benefit',factors:{interest:100},market:null,caveat:'No foreign benefit'} as ProductFX} as RealProduct}/>);
  expect(screen.queryByText(/Historical FX Reference:/)).not.toBeInTheDocument();
  expect(screen.getByText('USD listing · no foreign FX benefit')).toBeInTheDocument();
 });
});
