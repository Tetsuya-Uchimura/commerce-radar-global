import type {Country,SearchPlan} from './api';
import type {AutomaticResult} from './useAutomaticDiscovery';
export type MapLayer='verified'|'discovery';
export type DiscoveryMarket={code:string;name:string;interests:string[];selected:boolean;query:string;basis:string;reason:string;seller_location_verified:false;opportunity_score:null;source:string};
export type MapCountry=Country&{exploration?:DiscoveryMarket};
export function mapCountries(countries:Country[],result:AutomaticResult|null,markets:DiscoveryMarket[]|undefined,plan:SearchPlan|undefined,layer:MapLayer,demo:boolean,excluded:string=''):MapCountry[]{
 const omitted=new Set(excluded.split(','));
 return countries.filter(c=>!omitted.has(c.code)).map(c=>{
  if(demo)return c;
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
