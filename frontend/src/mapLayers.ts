import type {Country,SearchPlan} from './api';
import type {AutomaticResult} from './useAutomaticDiscovery';
import type {FXIntelligence,FXMarket} from './FXOpportunities';
export type MapLayer='fx'|'personalized'|'verified'|'discovery';
export type DiscoveryMarket={code:string;name:string;interests:string[];selected:boolean;query:string;basis:string;reason:string;seller_location_verified:false;opportunity_score:null;source:string};
export type MapCountry=Country&{exploration?:DiscoveryMarket;fxOpportunity?:FXMarket;currency_region?:boolean};
export function mapCountries(countries:Country[],result:AutomaticResult|null,markets:DiscoveryMarket[]|undefined,plan:SearchPlan|undefined,layer:MapLayer,demo:boolean,excluded:string='',intel?:FXIntelligence):MapCountry[]{
 const omitted=new Set(excluded.split(','));
 return countries.filter(c=>!omitted.has(c.code)).map(c=>{
  if(layer==='fx'||layer==='personalized'){
   const market=intel?.markets.find(m=>m.currency===c.currency);
   const matches=(result?.recommendation?.fx_backed_finds||[]).filter(p=>p.currency===c.currency);
   const score=layer==='fx'?(market?.eligible?market.selected?.fx_score??null:null):(matches.length?Math.max(...matches.map(p=>p.fx_opportunity?.score||0)):null);
   return {...c,score,offer_count:matches.length,complete_count:0,fxOpportunity:market,currency_region:true,
    band:layer==='personalized'&&matches.length?'Meaningful Shopping Opportunity':market?.display_label||'Insufficient FX Data',explanation:layer==='fx'?'Currency region; USD purchasing power vs historical observation. Not seller location, product stock or a discount.':'Meaningful Shopping Opportunity: relevant, source-priced foreign-currency products; seller origin is separate. No confirmed product means no opportunity score.'};
  }
  if(demo&&layer==='discovery')return c;
  if(layer==='discovery'){
   const suggestion=markets?.find(m=>m.code===c.code);
   // The local fallback is also only an explicit route, never geographic evidence.
   const exploration=suggestion||{code:c.code,name:c.name,interests:plan?.queries.slice(0,3).map(q=>q.category)||[],selected:false,query:plan?.queries[0]?.query||'',basis:'Supported search destination',reason:`Explore ${c.name} using your interests. Seller location and price advantage are not verified.`,seller_location_verified:false as const,opportunity_score:null,source:'Exploration route'};
   return {...c,score:null,offer_count:0,complete_count:0,band:'Interest-led exploration target',explanation:exploration.reason,exploration};
  }
  const real=result?.countries.find(n=>n.code===c.code);
  return {...c,score:real?.score??null,offer_count:real?.offer_count||0,complete_count:real?.complete_count||0,
   band:real?'Verified seller location':'No verified seller-country evidence',explanation:real?.basis||'No source-confirmed seller location. Origin Unknown products do not generate a country score.'};
 });
}
