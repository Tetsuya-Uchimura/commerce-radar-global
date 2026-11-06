import {describe,it,expect,vi,afterEach} from 'vitest';
import {render,screen,waitFor} from '@testing-library/react';
import {RealProductSearch} from '../RealProducts';
import type {SearchPlan} from '../api';

afterEach(()=>vi.unstubAllGlobals());
const plan=(signature:string,category:string):SearchPlan=>({version:2,applied_version:2,signature,current_ai:true,status:'completed',queries:[{category,query:category+' creative courses',origin:'emerging_interests',interest_score:70}],scoring_rule:'Deterministic category rubric',notice:'Uncertain hypothesis'});
describe('AI-driven real discovery',()=>{
 it('searches updated analysis proposals and preserves budget/FX uncertainty',async()=>{
  const requests:Record<string,unknown>[]=[];
  vi.stubGlobal('fetch',vi.fn(async(_url:string,options:RequestInit)=>{requests.push(JSON.parse(String(options.body)));return {ok:true,json:async()=>({items:[{link_access:{status:'reachable',reason:'Observed HTTP response',checked_at:'2026-11-04T00:00:00Z',scope:'server',limitation:'Browser may differ'},id:'real',name:'Observed Camera Course',merchant:'observed.store',merchant_country:null,price_minor:399,currency:'EUR',listing_usd_minor:449,estimated_total_usd:null,url:'https://observed.store/products/course',source:'Channel3 product API',verified_at:'2026-11-04T00:00:00Z',verification:'Provider observed',fx:{rate:'1.125',rate_date:'2026-11-04',source:'Frankfurter',stale:false},budget_status:'unverified_total',recommendation_score:70}],error:null,recommendation:{reason:'No verified total within budget'}})};}));
  const {rerender}=render(<RealProductSearch plan={plan('photo','Photography')} country="JP" budgetMinor={10000} kind="physical" autoSearch/>);
  expect(await screen.findByText('Observed Camera Course')).toBeInTheDocument();
  expect(requests[0]).toMatchObject({query:'Photography creative courses',country:'JP',budget_minor:10000,kind:'physical'});
  expect(screen.getByText('USD listing estimate: $4.49')).toBeInTheDocument();
  expect(screen.getByText(/Purchase total: Unknown/)).toBeInTheDocument();
  expect(screen.getByRole('link',{name:/Visit Store/})).toHaveAttribute('href','https://observed.store/products/course');
  expect(screen.queryByText(/PayPal Sandbox/)).not.toBeInTheDocument();
  rerender(<RealProductSearch plan={plan('outdoor','Outdoor')} country="JP" budgetMinor={5000} kind="physical" autoSearch/>);
  await waitFor(()=>expect(requests.at(-1)).toMatchObject({query:'Outdoor creative courses',budget_minor:5000}));
 });
 it('discards a late result from an obsolete analysis version',async()=>{
  let firstResolve:((value:unknown)=>void)|undefined;
  vi.stubGlobal('fetch',vi.fn(async(_url:string,options:RequestInit)=>{
   const query=JSON.parse(String(options.body)).query;
   if(query.startsWith('Photography'))return new Promise(resolve=>{firstResolve=resolve;});
   return {ok:true,json:async()=>({items:[],error:null,recommendation:{reason:'Current Outdoor results'}})};
  }));
  const {rerender}=render(<RealProductSearch plan={plan('a','Photography')} autoSearch/>);
  rerender(<RealProductSearch plan={plan('b','Outdoor')} autoSearch/>);
  expect(await screen.findByText('Current Outdoor results')).toBeInTheDocument();
  firstResolve?.({ok:true,json:async()=>({items:[],error:null,recommendation:{reason:'Obsolete Photography results'}})});
  await waitFor(()=>expect(screen.queryByText('Obsolete Photography results')).not.toBeInTheDocument());
 });
});
