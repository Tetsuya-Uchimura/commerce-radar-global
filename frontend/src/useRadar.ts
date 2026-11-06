import {mapCountries as buildMapCountries,type MapLayer} from './mapLayers';
import {useAutomaticDiscovery} from './useAutomaticDiscovery';
import {useEffect,useMemo,useState,useRef} from 'react';
import {api,query,defaultFilters,type Persona,type Filters,type DemoStatus,type Discovery,type Offer,type Purchase,type Order,type Explanation,type Answer} from './api';

export type View='map'|'discover'|'saved'|'compare'|'history'|'profile'|'settings'|'welcome'|'payment'|'fx'|'real'|'countries';
export type RadarState=ReturnType<typeof useRadar>;

export function useRadar(){
 const analysisVersion=useRef('');
 const [mapLayer,setMapLayer]=useState<MapLayer>('fx');
 const [countryComparison,setCountryComparison]=useState<string[]>([]);
 const [fxSelection,setFXSelection]=useState({currency:'EUR',period:'1Y'});
 const [realRequest,setRealRequest]=useState({query:'',country:'',provider:'auto' as 'auto'|'web'|'app_store'|'channel3'|'curated',request:0,goal:'best'});
 const [persona,setPersona]=useState<Persona>((localStorage.getItem('radar-persona') as Persona)||'coffee');
 const [view,setView]=useState<View>(location.pathname.startsWith('/payment/')?'payment':(location.hash.slice(1)||'map') as View);
 const [status,setStatus]=useState<DemoStatus|null>(null),[data,setData]=useState<Discovery|null>(null);
 const [ready,setReady]=useState(false),[loading,setLoading]=useState(true),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 const [filters,setFilters]=useState<Filters>(defaultFilters),[countryName,setCountryName]=useState(''),[refresh,setRefresh]=useState(0);
 const [detail,setDetail]=useState<Offer|null>(null),[explanation,setExplanation]=useState<Explanation|null>(null),[countryExplanation,setCountryExplanation]=useState<Explanation|null>(null);
 const [savedCompare,setSavedCompare]=useState<number[]>([]),[comparisons,setComparisons]=useState<Offer[]>([]);
 const [historyRows,setHistoryRows]=useState<Purchase[]>([]),[historySource,setHistorySource]=useState('all');
 const [chatOpen,setChatOpen]=useState(false),[chatInput,setChatInput]=useState(''),[chatBusy,setChatBusy]=useState(false),[focusOffer,setFocusOffer]=useState<number|undefined>();
 const [messages,setMessages]=useState<{question:string;answer:Answer}[]>([]);
 const [checkoutOpen,setCheckoutOpen]=useState(false),[checkoutMode,setCheckoutMode]=useState<'simulation'|'sandbox'>('simulation'),[quantity,setQuantity]=useState(1),[order,setOrder]=useState<Order|null>(null);
 const [interestDraft,setInterestDraft]=useState<string[]>([]),[budgetDraft,setBudgetDraft]=useState(15000),[mobileFilters,setMobileFilters]=useState(false),[search,setSearch]=useState('');
 const effectiveFilters=useMemo(()=>({...filters,saved_only:view==='saved'}),[filters,view]);
 const qs=useMemo(()=>query(effectiveFilters),[effectiveFilters]);
 const automatic=useAutomaticDiscovery(ready&&!!data,persona,data?.profile.user_id,data?.profile.search_plan,{query:realRequest.query||null,provider:realRequest.provider,country:filters.country||null,category:filters.category||null,budget_minor:filters.max_budget,kind:filters.digital_only?'digital':filters.physical_only?'physical':'any',excluded_countries:(filters.excluded_countries||'').split(',').filter(Boolean),goal:realRequest.goal,fx_period:filters.fx_period||'90D',opportunity_mode:filters.opportunity_mode||'live',listing_currency:filters.listing_currency},reloadData);
 const showingDemo=automatic.result?.mode==='Demo Products';
 const fxIntelligence=data?.fx_intelligence||automatic.result?.fx_intelligence;
 const mapCountries=buildMapCountries(data?.countries||[],automatic.result,data?.discovery_markets,data?.profile.search_plan,mapLayer,showingDemo,filters.excluded_countries,fxIntelligence);
 const mapLayerTitle=mapLayer==='fx'?'FX Advantage Map':mapLayer==='personalized'?'Personalized Opportunities':mapLayer==='verified'?'Verified Product Origins':showingDemo?'Demo Catalog':'Discovery Markets';
 const selectedCountry=mapCountries.find(c=>c.code===filters.country);
 useEffect(()=>setCountryExplanation(null),[mapLayer]);
 const profile=data?.profile;
 const personaInfo=status?.personas.find(p=>p.id===persona);
 function navigate(next:View){setView(next);setError('');setMobileFilters(false);if(next!=='payment'){history.pushState({},'',`/#${next}`);setOrder(null);}}
 function updateFilters(changes:Partial<Filters>){if(changes.category!==undefined&&changes.category!==filters.category)setRealRequest(r=>({...r,query:''}));setFilters(f=>({...f,...changes}));setCountryExplanation(null);}
 function chooseCountry(code:string,name:string){setCountryName(name);const currency=data?.countries.find(c=>c.code===code)?.currency;updateFilters({country:code,listing_currency:currency});}
 useEffect(()=>{const fn=()=>setView(location.pathname.startsWith('/payment/')?'payment':(location.hash.slice(1)||'map') as View);window.addEventListener('popstate',fn);return()=>window.removeEventListener('popstate',fn);},[]);
 useEffect(()=>{let live=true;setReady(false);setLoading(true);setError('');setData(null);
  api<DemoStatus>('/demo/status').then(s=>{if(live)setStatus(s);return api('/demo/session',{persona});}).then(()=>{if(live){setReady(true);localStorage.setItem('radar-persona',persona);}}).catch(e=>{if(live){setError(e.message);setLoading(false);}});
  return()=>{live=false;};
 },[persona]);
 useEffect(()=>{if(!ready)return;const controller=new AbortController();setLoading(true);
  const timer=setTimeout(()=>{api<Discovery>('/discovery'+qs,undefined,controller.signal).then(d=>{if(controller.signal.aborted)return;setData(d);setInterestDraft(d.profile.interests.map(i=>i.category));setBudgetDraft(d.profile.budget_usd);setError('');}).catch(e=>{if(e.name!=='AbortError')setError(e.message);}).finally(()=>{if(!controller.signal.aborted)setLoading(false);});},120);
  return()=>{clearTimeout(timer);controller.abort();};
 },[ready,qs,refresh]);
 useEffect(()=>{if(!ready)return;let live=true;api<Purchase[]>('/history').then(rows=>live&&setHistoryRows(rows)).catch(e=>live&&setError(e.message));return()=>{live=false;};},[ready,refresh]);
 useEffect(()=>{if(!ready||view!=='payment')return;let live=true;const id=location.pathname.split('/')[2];if(!id)return;api<Order>('/checkout/orders/'+encodeURIComponent(id)).then(o=>live&&setOrder(o)).catch(e=>live&&setError(e.message));return()=>{live=false;};},[ready,view]);
 useEffect(()=>{if(!ready||view!=='compare')return;let live=true;Promise.all(savedCompare.map(id=>api<Offer>('/offers/'+id+qs))).then(items=>live&&setComparisons(items)).catch(e=>live&&setError(e.message));return()=>{live=false;};},[view,savedCompare,qs,ready]);
 useEffect(()=>{setCountryExplanation(null);setExplanation(null);if(detail&&ready){let live=true;api<Offer>('/offers/'+detail.id+qs).then(p=>live&&setDetail(p)).catch(e=>live&&setError(e.message));return()=>{live=false;};}},[qs,ready]);
 function changePersona(next:Persona){if(busy||chatBusy||next===persona)return;setReady(false);setHistoryRows([]);setComparisons([]);setPersona(next);setDetail(null);setMessages([]);setSavedCompare([]);setFilters(defaultFilters);setRealRequest({query:'',country:'',provider:'auto',request:0,goal:'best'});setCountryComparison([]);setCountryName('');setChatOpen(false);navigate('map');}
 async function openOffer(p:Offer|number){setError('');setExplanation(null);setCheckoutOpen(false);setQuantity(1);setFocusOffer(typeof p==='number'?p:p.id);try{setDetail(typeof p==='number'?await api<Offer>('/offers/'+p+qs):p);}catch(e){setError((e as Error).message);}}
 async function toggleSave(p:Offer){try{await api('/saved/'+p.id,{saved:!p.saved});setData(d=>d?{...d,offers:d.offers.map(o=>o.id===p.id?{...o,saved:!p.saved}:o)}:d);if(detail?.id===p.id)setDetail({...p,saved:!p.saved});if(view==='saved')setRefresh(r=>r+1);}catch(e){setError((e as Error).message);}}
 function compare(p:Offer){setSavedCompare(ids=>ids.includes(p.id)?ids:[...ids.slice(-3),p.id]);setDetail(null);navigate('compare');}
 async function ask(text=chatInput,offerId?:number){if(!text.trim()||chatBusy)return;setChatOpen(true);setChatInput('');setChatBusy(true);setError('');try{const answer=await api<Answer>('/concierge'+qs,{message:text,...(offerId?{offer_id:offerId}:{})});setMessages(m=>[...m,{question:text,answer}]);for(const action of answer.actions){if(action.type==='set_filters'){updateFilters(action.filters);if(view!=='map')navigate('map');}if(action.type==='select_country'){chooseCountry(action.country,data?.countries.find(c=>c.code===action.country)?.name||action.country);navigate('map');}if(action.type==='compare_countries'){setCountryComparison(action.countries);navigate('countries');}
if(action.type==='show_fx'){setFXSelection({currency:action.currency,period:action.period});navigate('fx');}
if(action.type==='search_products'){setRealRequest(r=>({query:action.query,country:action.country||'',provider:action.provider||'auto',goal:action.goal||'best',request:r.request+1}));navigate('real');}
if(action.type==='open_offer'){await openOffer(action.offer_id);setChatOpen(false);}}}catch(e){setError((e as Error).message);setChatInput(text);}finally{setChatBusy(false);}}
 async function explainOffer(){if(!detail)return;setBusy(true);try{setExplanation(await api<Explanation>('/offers/'+detail.id+'/explanation'+qs,{}));}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
 async function explainCountry(){if(!selectedCountry)return;if(!showingDemo){setCountryExplanation({explanation:selectedCountry.explanation,limitation:mapLayer==='discovery'?'Exploration target only; seller location, inventory and value are unverified.':'Verified seller-location evidence only; no delivered-value claim.',source:mapLayer==='discovery'?'Interest-led exploration route':'Deterministic real-product evidence'});return;}setBusy(true);try{setCountryExplanation(await api<Explanation>('/countries/'+selectedCountry.code+'/explanation'+qs,{}));}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
 async function saveProfile(reset=false){setBusy(true);try{await api('/profile',{interests:reset?null:interestDraft,budget_usd:budgetDraft});setRefresh(r=>r+1);}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
 async function resetDemo(){if(!window.confirm('Reset synthetic histories, edited interests, and saves? All app payments and legacy data will be preserved.'))return;setBusy(true);try{await api('/demo/reset',{});setFilters(defaultFilters);setCountryName('');setRefresh(r=>r+1);}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
 async function createOrder(){if(!detail)return;setBusy(true);setError('');try{const payload={offer_id:detail.id,quantity,mode:checkoutMode,currency:'USD'};const fingerprint=JSON.stringify({persona,...payload});const last=JSON.parse(sessionStorage.getItem('global-checkout')||'null');const key=last?.fingerprint===fingerprint?last.key:crypto.randomUUID();sessionStorage.setItem('global-checkout',JSON.stringify({fingerprint,key}));const o=await api<Order>('/checkout/orders',{...payload,idempotency_key:key});setOrder(o);if(o.approval_url&&o.status!=='COMPLETED'){location.assign(o.approval_url);return;}setCheckoutOpen(false);setDetail(null);history.pushState({},'',`/payment/${o.id}`);setView('payment');}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
 async function captureOrder(){if(!order)return;setBusy(true);setError('');try{const result=await api<Order>('/checkout/orders/'+order.id+'/capture',{});setOrder(result);if(result.status==='COMPLETED'){sessionStorage.removeItem('global-checkout');setRefresh(r=>r+1);}}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
 async function refreshOrder(){if(!order)return;setBusy(true);try{setOrder(await api<Order>('/checkout/orders/'+order.id));setRefresh(r=>r+1);}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
 function reloadData(){setRefresh(r=>r+1);}
 function analysisApplied(version:number){const key=persona+':'+version;if(analysisVersion.current!==key){analysisVersion.current=key;setRefresh(r=>r+1);}}
 async function clearChat(){await api('/concierge/clear',{});setMessages([]);setFilters(defaultFilters);}
 useEffect(()=>{if(!ready)return;let alive=true;const poll=async()=>{try{const d=await api<{status:string;applied_version:number}>('/analysis');if(alive&&d.status==='completed')analysisApplied(d.applied_version);}catch{/* Workspace remains usable. */}};poll();const timer=setInterval(poll,2500);return()=>{alive=false;clearInterval(timer);};},[ready,persona]);
 const visibleOffers=data?.offers.filter(p=>`${p.name} ${p.country} ${p.category}`.toLowerCase().includes(search.toLowerCase()))||[];
 const firstName=personaInfo?.name.split(' ')[0]||'Explorer';
 const cardProps={onOpen:openOffer,onSave:toggleSave,onCompare:compare,onAsk:(p:Offer)=>{setFocusOffer(p.id);ask('Why is this product relevant to my interests?',p.id);}};
 const currentSource=data?.fx.effective_mode==='live'?'DAILY FX · FRANKFURTER':data?.fx.effective_mode==='cached'?'CACHED FX · DAILY REFERENCE':data?.fx.effective_mode==='mixed'?'MIXED FX · CHECK EACH SOURCE':'DEMO FX · SYNTHETIC SCENARIO';
 function setProductQuery(query:string){setRealRequest(r=>({...r,query}));}
 function setProductProvider(provider:typeof realRequest.provider){setRealRequest(r=>({...r,provider}));}
 return {fxIntelligence,setFXSelection,mapLayer,setMapLayer,mapLayerTitle,automatic,showingDemo,mapCountries,setProductQuery,setProductProvider,countryComparison,fxSelection,realRequest,reloadData,analysisApplied,clearChat,persona,view,status,data,ready,loading,error,busy,filters,countryName,detail,explanation,countryExplanation,savedCompare,comparisons,
  historyRows,historySource,chatOpen,chatInput,chatBusy,focusOffer,messages,checkoutOpen,checkoutMode,quantity,order,interestDraft,budgetDraft,mobileFilters,search,
  selectedCountry,profile,personaInfo,visibleOffers,firstName,cardProps,currentSource,qs,
  navigate,updateFilters,chooseCountry,changePersona,openOffer,toggleSave,compare,ask,explainOffer,explainCountry,saveProfile,resetDemo,createOrder,captureOrder,refreshOrder,
  setError,setFilters,setDetail,setCountryName,setSavedCompare,setHistorySource,setChatOpen,setChatInput,setFocusOffer,setCheckoutOpen,setCheckoutMode,setQuantity,
  setInterestDraft,setBudgetDraft,setMobileFilters,setSearch};
}
