import {describe,it,expect,vi,afterEach} from 'vitest';
import {render,screen,fireEvent,waitFor} from '@testing-library/react';
import {ShoppingStrategyPanel,type ShoppingStrategy,type ShoppingSource} from '../ShoppingStrategy';
import type {RadarState} from '../useRadar';
const base:ShoppingStrategy={strategy:'compare_both',calculated_strategy:'compare_both',display_name:'Compare Both',title:'Compare US and international coffee sources',summary:'Evidence does not support a stronger shopping priority yet.',primary_interest:'Coffee',recommended_currencies:['USD','EUR'],fx_period:'90D',fx_mode:'live',as_of:'2026-11-07',reason_codes:['missing_prices'],recommended_sources:[],evidence_status:'search_suggestion',limitations:[],shopping_priority:'auto',user_override:false,signature:'000000000000000000000001',user_id:1,analysis_version:1,analysis_signature:'profile-1',meaningful_product_ids:[],fx_evidence:[{currency:'EUR',rate_date:'2026-11-07',reference_date:'2026-08-09',purchasing_power_advantage:'2.85'}]};
function radar(s=base,extra={}){return {strategy:s,automatic:{loading:false,result:null},chooseShoppingPriority:vi.fn(),exploreStrategy:vi.fn(),viewStrategyFX:vi.fn(),compareStrategyMarkets:vi.fn(),ask:vi.fn(),chatBusy:false,...extra} as unknown as RadarState;}
const source:ShoppingSource={merchant:'Observed Store',product:'Observed coffee dripper',product_id:'actual',currency:'EUR',price_minor:5990,price_observed_at:'2026-11-07',url:'https://observed-store.com/products/dripper',source:'Observed publisher metadata',storefront_market:null,seller_country:null,basis:['personal_interest_match','observed_price_and_currency'],evidence_status:'observed_listing',link_access:{status:'user_pending',reason:'Manual review pending',checked_at:'2026-11-07',scope:'user',limitation:'Access unknown'}};
afterEach(()=>vi.unstubAllGlobals());
describe('shopping strategy panel',()=>{
 it.each([['explore_overseas','Explore Overseas'],['us_stores_first','US Stores First'],['compare_both','Compare Both']] as const)('shows the computed %s strategy without needing OpenAI',(_id,label)=>{
  render(<ShoppingStrategyPanel r={radar({...base,strategy:_id,display_name:label})}/>);
  expect(screen.getByText(label,{selector:'.strategy-choice'})).toBeInTheDocument();
  expect(screen.getByText(base.summary)).toBeInTheDocument();
  expect(screen.getByText('Interest · Coffee')).toBeInTheDocument();
  expect(screen.getByText('EUR · +2.9% USD power')).toBeInTheDocument();
 });
 it('displays real source evidence and unknown origin without enabling pending destination',()=>{
  render(<ShoppingStrategyPanel r={radar({...base,recommended_sources:[source]})}/>);
  expect(screen.getByText('Observed coffee dripper · €59.90')).toBeInTheDocument();
  expect(screen.getByText(/Storefront market unverified · Seller origin: Origin Unknown/)).toBeInTheDocument();
  expect(screen.getByText(source.url)).toBeInTheDocument();expect(screen.queryByRole('link')).not.toBeInTheDocument();
 });
 it('does not manufacture sites from a preferred currency',()=>{
  render(<ShoppingStrategyPanel r={radar()}/>);
  expect(screen.getByText(/No suitable site is verified yet/)).toBeInTheDocument();
  expect(screen.queryByRole('link')).not.toBeInTheDocument();
 });
 it('shows sourced US-market evidence while keeping legal country unknown',()=>{
  render(<ShoppingStrategyPanel r={radar({...base,recommended_sources:[{...source,storefront_market:'US',currency:'USD',link_access:{...source.link_access!,status:'user_confirmed'}}]})}/>);
  expect(screen.getByText(/Verified US storefront market · Seller origin: Origin Unknown/)).toBeInTheDocument();
  expect(screen.getByRole('link',{name:'Open recommended source ↗'})).toHaveAttribute('href',source.url);
 });
 it('all controls invoke functioning context actions',()=>{
  const r=radar();render(<ShoppingStrategyPanel r={r}/>);
  fireEvent.click(screen.getByRole('button',{name:'Explore Recommended Products'}));expect(r.exploreStrategy).toHaveBeenCalledOnce();
  fireEvent.click(screen.getByRole('button',{name:'View Currency Trends'}));expect(r.viewStrategyFX).toHaveBeenCalledOnce();
  fireEvent.click(screen.getByRole('button',{name:'Compare Markets'}));expect(r.compareStrategyMarkets).toHaveBeenCalledOnce();
  fireEvent.click(screen.getByRole('button',{name:'Ask AI Why'}));expect(r.ask).toHaveBeenCalledWith(expect.stringContaining('without searching'),undefined,true);
  fireEvent.change(screen.getByLabelText('Shopping priority'),{target:{value:'domestic'}});expect(r.chooseShoppingPriority).toHaveBeenCalledWith('domestic');
 });
 it('labels historical scenarios and user overrides explicitly',()=>{
  render(<ShoppingStrategyPanel r={radar({...base,fx_mode:'historical',user_override:true})}/>);
  expect(screen.getByText(/Historical Demonstration · observed 2026-11-07/)).toBeInTheDocument();
  expect(screen.getByText(/Automatic assessment: compare both/)).toBeInTheDocument();
 });
 it('keeps deterministic output during async enrichment failure',async()=>{
  vi.stubGlobal('fetch',vi.fn(async()=>({ok:false,status:503,json:async()=>({detail:'Unavailable'})})));
  render(<ShoppingStrategyPanel r={radar({...base,recommended_sources:[source],signature:'000000000000000000000002'},{automatic:{loading:false,result:{}}})}/>);
  await waitFor(()=>expect(fetch).toHaveBeenCalled(),{timeout:3000});
  expect(screen.getByText(base.summary)).toBeInTheDocument();
 });
});
