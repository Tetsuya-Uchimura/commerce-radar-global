import type {LinkAccess} from './LinkAccess';
import {useEffect,useRef,useState} from 'react';
import {api,type SearchPlan} from './api';
export type RealProduct={fx_opportunity?:import("./FXOpportunities").ProductFX;link_access?:LinkAccess;id:string;name:string;merchant:string;merchant_country:string|null;merchant_country_evidence?:{source:string;observed_at:string}|null;seller_country?:string|null;ship_from_country?:string|null;delivery_countries?:string[]|null;price_minor:number|null;currency:string|null;listing_usd_minor:number|null;estimated_total_usd:number|null;url:string;source:string;verified_at:string;data_source:string;recommendation_score:number;score_rule:string;verification:string;fx?:{rate:string;rate_date:string;source:string;stale:boolean}|null};
export type AutomaticResult={fx_intelligence?:import("./FXOpportunities").FXIntelligence;user_id:number;version:number;analysis_signature:string;signature:string;mode:'Real Products'|'Cached Real Products'|'Demo Products'|'Discovering';items:RealProduct[];unknown_origin:RealProduct[];countries:{code:string;score:number;offer_count:number;complete_count:number;basis:string}[];error:string|null;notice:string;query?:string;waiting_for_analysis?:boolean;discarded?:boolean;retry_after?:number;stale_cache?:boolean;recommendation:{best_fx_backed?:RealProduct|null;fx_backed_finds?:RealProduct[];fx_reason?:string;best_discovery:RealProduct|null;best_verified_value:RealProduct|null;discovery_reason:string;value_reason:string}};
export function useAutomaticDiscovery(enabled:boolean,persona:string,userId:number|undefined,plan:SearchPlan|undefined,conditions:Record<string,unknown>,reloadData:()=>void){
 const [result,setResult]=useState<AutomaticResult|null>(null),[loading,setLoading]=useState(false),[refreshToken,setRefreshToken]=useState(0),[retry,setRetry]=useState(0),[demoOnly,setDemoOnly]=useState(false);
 const sequence=useRef(0),lastRefresh=useRef(0);const conditionKey=JSON.stringify(conditions);
 useEffect(()=>{setDemoOnly(false);setResult(null);},[persona]);
 useEffect(()=>{if(!enabled)return;const id=++sequence.current;const controller=new AbortController();let poll:ReturnType<typeof setTimeout>|undefined;
  const force=lastRefresh.current!==refreshToken;lastRefresh.current=refreshToken;
  setLoading(true);setResult(null);
  const timer=setTimeout(async()=>{try{
   const value=await api<AutomaticResult>('/products/automatic',{...JSON.parse(conditionKey),expected_signature:plan?.signature,demo_only:demoOnly,refresh:force},controller.signal);
   if(sequence.current!==id||controller.signal.aborted)return;
   if(value.discarded||value.user_id!==userId||(plan&&value.analysis_signature!==plan.signature)){reloadData();poll=setTimeout(()=>setRetry(v=>v+1),1500);return;}
   if(value.waiting_for_analysis){poll=setTimeout(()=>{reloadData();setRetry(v=>v+1);},2500);return;}
   setResult(value);setLoading(false);
   if(value.retry_after)poll=setTimeout(()=>setRetry(v=>v+1),Math.max(2,value.retry_after)*1000);
  }catch(e){if(sequence.current!==id||controller.signal.aborted)return;setLoading(false);setResult({user_id:userId||0,version:plan?.version||0,analysis_signature:plan?.signature||'',signature:'error',mode:'Demo Products',items:[],unknown_origin:[],countries:[],error:(e as Error).message,notice:'Live product search unavailable · Sample product data',recommendation:{best_discovery:null,best_verified_value:null,discovery_reason:'',value_reason:''}});}},650);
  return()=>{clearTimeout(timer);if(poll)clearTimeout(poll);controller.abort();sequence.current++;};
 },[enabled,persona,userId,plan?.signature,conditionKey,refreshToken,retry,demoOnly]);
 return {result,loading,demoOnly,setDemoOnly,refreshProducts:()=>{setDemoOnly(false);setRefreshToken(v=>v+1);}};
}
