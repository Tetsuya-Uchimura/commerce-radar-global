import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest';
import {act,renderHook} from '@testing-library/react';
import {useAutomaticDiscovery} from '../useAutomaticDiscovery';
import type {SearchPlan} from '../api';
const plan=(version:number):SearchPlan=>({version,applied_version:version,signature:'plan-'+version,current_ai:true,status:'completed',queries:[],scoring_rule:'Auditable',notice:'Hypothesis'});
const envelope=(body:Record<string,unknown>)=>({user_id:1,version:Number(String(body.expected_signature).split('-')[1]),analysis_signature:body.expected_signature,mode:'Real Products',items:[],unknown_origin:[],countries:[],recommendation:{best_discovery:null,best_verified_value:null},error:null});
beforeEach(()=>vi.useFakeTimers());
afterEach(()=>{vi.useRealTimers();vi.unstubAllGlobals();});
async function settle(){await act(async()=>{await vi.advanceTimersByTimeAsync(700);});}
describe('automatic product lifecycle',()=>{
 it('Scenario B refreshes only the latest completed history/analysis version and debounces edits',async()=>{
  const bodies:Record<string,unknown>[]=[];
  vi.stubGlobal('fetch',vi.fn(async(_url:string,init:RequestInit)=>{const body=JSON.parse(String(init.body));bodies.push(body);return {ok:true,json:async()=>envelope(body)};}));
  const reload=vi.fn();
  const {result,rerender}=renderHook(({version,budget})=>useAutomaticDiscovery(true,'coffee',1,plan(version),{budget_minor:budget},reload),{initialProps:{version:1,budget:10000}});
  await settle();expect(bodies).toHaveLength(1);
  rerender({version:2,budget:10000});rerender({version:3,budget:8000});rerender({version:3,budget:5000});
  await settle();expect(bodies).toHaveLength(2);expect(bodies[1]).toMatchObject({expected_signature:'plan-3',budget_minor:5000});
  expect(result.current.result?.version).toBe(3);
  rerender({version:3,budget:5000});await settle();expect(bodies).toHaveLength(2);
  act(()=>result.current.refreshProducts());await settle();expect(bodies[2].refresh).toBe(true);
  rerender({version:3,budget:4000});await settle();expect(bodies[3].refresh).toBe(false);
 });
 it('discards late responses and never restores an obsolete history version',async()=>{
  let resolveOld:((value:unknown)=>void)|undefined;
  vi.stubGlobal('fetch',vi.fn(async(_url:string,init:RequestInit)=>{const body=JSON.parse(String(init.body));
   if(body.expected_signature==='plan-1')return new Promise(resolve=>{resolveOld=resolve;});
   return {ok:true,json:async()=>envelope(body)};
  }));
  const {result,rerender}=renderHook(({version})=>useAutomaticDiscovery(true,'coffee',1,plan(version),{},vi.fn()),{initialProps:{version:1}});
  await settle();rerender({version:2});await settle();expect(result.current.result?.version).toBe(2);
  await act(async()=>{resolveOld?.({ok:true,json:async()=>envelope({expected_signature:'plan-1'})});});
  expect(result.current.result?.version).toBe(2);
 });
});
