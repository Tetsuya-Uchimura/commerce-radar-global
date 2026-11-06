import {describe,it,expect,vi,beforeEach} from 'vitest';
import {render,screen,fireEvent,waitFor} from '@testing-library/react';
import {readFileSync} from 'node:fs';
import App from '../App';
import {countryColor} from '../WorldMap';
import type {Country,Offer,FX,Discovery,Profile} from '../api';

// jsdom cannot lay out responsive charts or d3's SVG viewBox. Map geography,
// click handlers, selection state, filters, and real app effects remain mounted.
vi.mock('react-simple-maps/zoom',()=>({ZoomableGroup:({children}:{children:React.ReactNode})=><g>{children}</g>}));
vi.mock('recharts',()=>({ResponsiveContainer:()=>null,CartesianGrid:()=>null,AreaChart:()=>null,LineChart:()=>null,Line:()=>null,YAxis:()=>null,Legend:()=>null,Area:()=>null,XAxis:()=>null,Tooltip:()=>null}));
const geometry=JSON.parse(readFileSync(process.cwd()+'/public/world-110m.json','utf8'));
const fx:FX={currency:'EUR',quote:'JPY',direction:'JPY per 1 EUR',rate:'157',rate_date:'2026-11-03',change_30:'3',change_90:'8',power_vs_90_average:'4',fx_score:60,source:'Synthetic Demo FX',last_updated:'2026-11-03T00:00:00',stale:false,warning:'Synthetic scenario, not market FX.',history:[]};
const countries:Country[]=[{code:'PT',name:'Portugal',map_id:'620',currency:'EUR',longitude:-8,latitude:39,score:85,band:'Strong Opportunity',offer_count:6,complete_count:6,fx,explanation:'Six fictional offers with complete estimates.'},{code:'CA',name:'Canada',map_id:'124',currency:'CAD',longitude:-106,latitude:56,score:62,band:'Good Opportunity',offer_count:6,complete_count:6,fx:{...fx,currency:'CAD'},explanation:'Six fictional offers.'}];
function offer(id:number,name:string,code:string,digital:boolean):Offer{return {id,product_id:id,name,description:'Fictional demo offer.',category:digital?'Coffee':'Outdoor',kind:digital?'online_course':'physical',digital,country_code:code,country:code==='PT'?'Portugal':'Canada',country_currency:'EUR',currency:'EUR',local_price_minor:2500,image_url:'/images/product-0.svg',merchant:'Commerce Radar Demo Merchant',product_url:null,shipping_available:true,stock:25,checkout_available:true,checkout_quote_usd:4500,source:'Synthetic Demo Catalog',verified_at:'2026-11-03T00:00:00',score:86,factors:{interest:100,cost:50,fx:60,novelty:100,availability:100,budget:100},weights:{interest:30,cost:25,fx:15,novelty:15,availability:10,budget:5},cost:{currency:'USD',components:{product:3925,shipping:0,taxes:392,other_fees:0,conversion_estimate:151},total_usd:4468,known_subtotal_usd:4468,unknown:[],complete:true,conversion_percent:'3.5',conversion_source:'Assumed estimate, not PayPal fees',fx_currency:'EUR',fx_rate:'157',shipping_adjustment_usd:0,price_verified_at:'2026-11-03T00:00:00',estimate_only:true,tax_note:'Synthetic estimate',checkout_quote_usd:4500},fx,comparison:{label:'Global Discovery',reference_usd:null,difference_usd:null,advantage_percent:null,equivalence_group:null},explanation:'An interest-based fictional discovery.',explanation_source:'Deterministic explanation · no LLM',saved:false,refund_terms:'No real fulfillment.'};}
const offers=[offer(1,'Lisbon Coffee Workshop','PT',true),offer(2,'Canadian Trail Kit','CA',false)];
const requests:string[]=[];
const posts:{path:string;body:Record<string,unknown>}[]=[];
let persona='coffee';
let productScenario='demo';
const profile=():Profile=>({user_id:persona==='coffee'?1:3,interests:[{category:persona==='coffee'?'Coffee':'Outdoor',score:100,purchases:20}],emerging_interests:[],preferred_price_range:{currency:'USD',min:2000,max:5000},purchase_count:36,frequency_per_30_days:6,product_preferences:[],international_countries:[],budget_usd:15000,customized:false,sources:{synthetic_global:36},reference_date:'2026-11-03'});
beforeEach(()=>{requests.length=0;posts.length=0;persona='coffee';productScenario='demo';vi.stubGlobal('fetch',vi.fn(async(input:RequestInfo|URL,init?:RequestInit)=>{
 const url=String(input);requests.push(url);
 if(url==='/world-110m.json')return {ok:true,json:async()=>geometry};
 const path=new URL(url,'http://localhost').pathname;
 if(init?.method==='POST')posts.push({path,body:JSON.parse(String(init.body))});
 let result:unknown={};
 if(path==='/api/demo/status')result={demo_mode:true,source:'Synthetic',demo_date:'2026-11-03',sandbox_configured:false,checkout_currency:'USD',currencies_sandbox_verified:[],personas:[{id:'coffee',name:'Alex Morgan',title:'Coffee Enthusiast'},{id:'outdoor',name:'Jamie Rivers',title:'Outdoor Explorer'},{id:'creator',name:'Sam Chen',title:'Digital Creator'}],categories:['Coffee','Outdoor'],countries:2,offers:2,scenarios:[{id:'balanced',title:'Balanced discovery'}]};
 else if(path==='/api/demo/session'){persona=JSON.parse(String(init?.body)).persona;result={persona};}
 else if(path==='/api/products/automatic'){
  const body=JSON.parse(String(init?.body));const demo=productScenario==='demo'||productScenario==='failure'||body.demo_only;
  const item={link_access:{status:productScenario==='restricted'?'restricted':productScenario==='broken'?'unavailable':'reachable',reason:productScenario==='restricted'?'Browser verification required':'Observed HTTP response',checked_at:'2026-11-04T00:00:00Z',scope:'server',limitation:'Browser may differ'},id:'observed',name:persona==='coffee'?'Observed Coffee Dripper':'Observed Trail Kit',merchant:'Observed Store',merchant_country:null,price_minor:2500,currency:'USD',listing_usd_minor:2500,estimated_total_usd:null,url:'https://observed.store/products/dripper',source:'Channel3 product API',verified_at:'2026-11-04T00:00:00Z',data_source:productScenario==='cached'?'Cached Product':'Real Product',recommendation_score:75,verification:'Observed provider listing'};
  const items=demo||productScenario==='empty'?[]:[item];
  result={user_id:persona==='coffee'?1:persona==='outdoor'?3:4,version:1,analysis_signature:'',signature:'scenario',mode:demo?'Demo Products':productScenario==='cached'?'Cached Real Products':'Real Products',items,unknown_origin:items,countries:[],error:productScenario==='failure'||productScenario==='cached'?'Channel3 authentication failed.':null,notice:demo?'Sample product data · Live product search unavailable':'Origin Unknown products do not generate country scores.',recommendation:{best_discovery:items[0]||null,best_verified_value:null,discovery_reason:'Interest match only; no cheapest guarantee',value_reason:'Complete costs missing'}};
 }
 else if(path==='/api/products/search')result={items:[],error:null,recommendation:{reason:'No verified total for this search'}};
 else if(path==='/api/history')result=[];
 else if(path==='/api/fx/chart')result={currency:'EUR',rate:'1.1',inverse_rate:'0.90909',history:[{date:'2026-01-01',rate:'1.2'},{date:'2026-11-04',rate:'1.1'}],rate_date:'2026-11-04',last_updated:'2026-11-04T00:00:00',source:'Frankfurter v2',high:'1.2',low:'1.1',period_change:'9.09',change_30:'2',change_90:'3',change_365:'4'};
 else if(path==='/api/analysis')result={version:1,applied_version:0,status:'unavailable',message:'AI analysis unavailable. Previous analysis is preserved.',result:null,previous:null,current_features:{scores:{Coffee:100}},usage:{calls:0,input_tokens:0,output_tokens:0},model:'gpt-6-luna'};
 else if(path==='/api/discovery'){
   const q=new URL(url,'http://localhost').searchParams;
   let rows=offers;
   if(q.get('country'))rows=rows.filter(p=>p.country_code===q.get('country'));
   if(q.get('digital_only')==='true')rows=rows.filter(p=>p.digital);
   if(q.get('category'))rows=rows.filter(p=>p.category===q.get('category'));
   result={profile:profile(),countries,offers:rows,fx:{effective_mode:'demo',rates:{EUR:fx},warning:null},weights:{},all_offer_count:rows.length};
 }else if(path==='/api/concierge'){
  const shopping=String(init?.body).includes('日本のコーヒー');
  const buy=String(init?.body).includes('buy');
  result={explanation:buy?'Opening details. No payment initiated.':'Showing digital coffee workshops in Portugal under 5,000 JPY.',limitation:'Synthetic data.',source:'Statistical template · no LLM',actions:shopping?[{type:'set_filters',filters:{category:'Coffee',max_budget:10000,physical_only:true,digital_only:false}},{type:'select_country',country:'JP'},{type:'search_products',query:'Japanese coffee brewing equipment',country:'JP',provider:'web',budget_minor:10000,kind:'physical'}]:buy?[{type:'open_offer',offer_id:1}]:[{type:'set_filters',filters:{digital_only:true,category:'Coffee',max_budget:10000}},{type:'select_country',country:'PT'}],offer_ids:[1]};
 }
 else if(path.startsWith('/api/offers/'))result=offers.find(p=>p.id===Number(path.split('/')[3]));
 return {ok:true,json:async()=>result};
}));});

describe('global discovery journey',()=>{
 it('starts with a world map and clicking a country updates the product panel',async()=>{
  render(<App/>);expect(await screen.findByTestId('world-map')).toBeInTheDocument();
  await screen.findByText('Canadian Trail Kit');
  fireEvent.click(await screen.findByRole('button',{name:'Discover Portugal'}));
  await waitFor(()=>expect(requests.some(p=>p.includes('country=PT'))).toBe(true));
  await waitFor(()=>expect(screen.queryByText('Canadian Trail Kit')).not.toBeInTheDocument());
  expect(await screen.findByText('Lisbon Coffee Workshop')).toBeInTheDocument();
  expect(screen.getByText('Demo country opportunity score')).toBeInTheDocument();
 });
 it('switches only between defined consumer personas',async()=>{
  render(<App/>);await screen.findByText('Canadian Trail Kit');
  fireEvent.change(screen.getByLabelText('Demo persona'),{target:{value:'outdoor'}});
  await waitFor(()=>expect(persona).toBe('outdoor'));
  expect(await screen.findByText('Jamie Rivers')).toBeInTheDocument();
  expect(screen.queryByText('Merchant')).not.toBeInTheDocument();
 });
 it('concierge actions operate the country selection and filters',async()=>{
  render(<App/>);await screen.findByText('Canadian Trail Kit');
  fireEvent.click(screen.getByRole('button',{name:'AI Concierge'}));
  fireEvent.click(screen.getByText('Find digital products under $100 including all costs'));
  expect(await screen.findByText('Statistical template · no LLM')).toBeInTheDocument();
  await waitFor(()=>expect(requests.some(p=>p.includes('/discovery?')&&p.includes('country=PT')&&p.includes('digital_only=true')&&p.includes('max_budget=10000'))).toBe(true));
  await waitFor(()=>expect(screen.queryByText('Canadian Trail Kit')).not.toBeInTheDocument());
  expect(requests.some(p=>p.includes('/checkout/'))).toBe(false);
 });
 it('exposes cost details and a separate fixed checkout quote',async()=>{
  render(<App/>);await screen.findByText('Lisbon Coffee Workshop');
  fireEvent.click(screen.getByRole('button',{name:'View Lisbon Coffee Workshop'}));
  expect(await screen.findByRole('dialog',{name:'Product opportunity details'})).toBeInTheDocument();
  expect(screen.getByText('The whole estimated cost')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:'Review checkout conditions'}));
  expect(screen.getByText('Fixed amount to approve')).toBeInTheDocument();
  expect(screen.getByRole('button',{name:'Continue to simulation'})).toBeInTheDocument();
 });
 it('unknown map countries do not receive an invented opportunity score',()=>{
  expect(countryColor(undefined)).toBe('#293f51');
  expect(countryColor({...countries[0],score:null})).toBe('#293f51');
  expect(countryColor(countries[0])).toBe('#8de1d6');
 });
 it('buy intent opens review details without initiating checkout',async()=>{
  render(<App/>);await screen.findByText('Lisbon Coffee Workshop');
  fireEvent.click(screen.getByRole('button',{name:'Ask AI about Lisbon Coffee Workshop'}));
  await screen.findByText('Statistical template · no LLM');
  fireEvent.change(screen.getByLabelText('Message global concierge'),{target:{value:'I want to buy this product'}});
  fireEvent.click(screen.getByRole('button',{name:'Send concierge message'}));
  expect(await screen.findByRole('dialog',{name:'Product opportunity details'})).toBeInTheDocument();
  expect(screen.queryByRole('dialog',{name:'AI Global Shopping Concierge'})).not.toBeInTheDocument();
  expect(requests.some(p=>p.includes('/checkout/'))).toBe(false);
 });
 it('edits purchase history through a validated USD form',async()=>{
  render(<App/>);await screen.findByText('Lisbon Coffee Workshop');
  fireEvent.click(screen.getByRole('button',{name:'History'}));
  fireEvent.click(await screen.findByRole('button',{name:'Add transaction'}));
  fireEvent.change(screen.getByLabelText('Transaction merchant_name'),{target:{value:'Test Demo Store'}});
  fireEvent.change(screen.getByLabelText('Transaction product_name'),{target:{value:'Photography Course'}});
  fireEvent.change(screen.getByLabelText('Transaction price'),{target:{value:'12.34'}});
  fireEvent.click(screen.getByRole('button',{name:'Save & analyze'}));
  await waitFor(()=>expect(posts.some(p=>p.path==='/api/history'&&p.body.currency==='USD'&&p.body.price==='12.34')).toBe(true));
  expect(screen.queryByRole('dialog',{name:'Edit purchase history'})).not.toBeInTheDocument();
 });
 it('requests the chosen historical FX period',async()=>{
  render(<App/>);await screen.findByText('Lisbon Coffee Workshop');
  fireEvent.click(screen.getByRole('button',{name:'FX charts'}));
  fireEvent.click(await screen.findByRole('button',{name:'5Y'}));
  await waitFor(()=>expect(requests.some(p=>p.includes('/fx/chart?currency=EUR&period=5Y'))).toBe(true));
  expect(screen.getByText('Latest Available Daily FX Rate')).toBeInTheDocument();
 });
 it('links Japanese shopping intent to country filters and real search',async()=>{
  render(<App/>);await screen.findByText('Lisbon Coffee Workshop');
  fireEvent.click(screen.getByRole('button',{name:'AI Concierge'}));
  fireEvent.change(screen.getByLabelText('Message global concierge'),{target:{value:'日本のコーヒー器具を100ドル以内で探したい'}});
  fireEvent.click(screen.getByRole('button',{name:'Send concierge message'}));
  await waitFor(()=>expect(posts.some(p=>p.path==='/api/products/automatic'&&p.body.query==='Japanese coffee brewing equipment'&&p.body.country==='JP'&&p.body.budget_minor===10000&&p.body.kind==='physical')).toBe(true));
  expect(await screen.findByText('Sample product data · Live product search unavailable')).toBeInTheDocument();
 });

 it('Scenario A automatically shows real cards on the initial map and persona switch',async()=>{
  productScenario='real';render(<App/>);
  expect(await screen.findByRole('link',{name:'Visit Store ↗'})).toBeInTheDocument();
  expect(screen.getAllByText('Observed Coffee Dripper').length).toBeGreaterThan(0);
  expect(screen.getByText('Origin Unknown')).toBeInTheDocument();
  expect(screen.queryByText('Lisbon Coffee Workshop')).not.toBeInTheDocument();
  expect(screen.queryByRole('button',{name:/Search real products/i})).not.toBeInTheDocument();
  expect(posts.filter(p=>p.path==='/api/products/automatic')).toHaveLength(1);
  fireEvent.click(screen.getByRole('button',{name:'Real products'}));
  expect(await screen.findByRole('link',{name:'Visit Store ↗'})).toBeInTheDocument();
  expect(posts.filter(p=>p.path==='/api/products/automatic')).toHaveLength(1);
  fireEvent.change(screen.getByLabelText('Demo persona'),{target:{value:'outdoor'}});
  await waitFor(()=>expect(screen.getAllByText('Observed Trail Kit').length).toBeGreaterThan(0));
 });
 it('Scenario D labels cached real results and preserves the provider error',async()=>{
  productScenario='cached';render(<App/>);
  expect(await screen.findByText('Cached Product')).toBeInTheDocument();
  expect(screen.getByRole('alert')).toHaveTextContent('Channel3 authentication failed.');
  expect(screen.queryByText('Lisbon Coffee Workshop')).not.toBeInTheDocument();
 });
 it('Scenario D falls back to visibly labelled Demo Products without cache',async()=>{
  productScenario='failure';render(<App/>);
  expect(await screen.findByText('Lisbon Coffee Workshop')).toBeInTheDocument();
  expect(screen.getByRole('alert')).toHaveTextContent('Channel3 authentication failed.');
  expect(screen.getAllByText(/Demo Product · Sample product data/).length).toBeGreaterThan(0);
 });
 it('successful zero results stay empty until the user explicitly chooses Demo Products',async()=>{
  productScenario='empty';render(<App/>);
  expect(await screen.findByText('No products match these search conditions.')).toBeInTheDocument();
  expect(screen.queryByText('Lisbon Coffee Workshop')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:'Switch to Demo Products'}));
  expect(await screen.findByText('Lisbon Coffee Workshop')).toBeInTheDocument();
 });

 it('separates interest-led exploration from verified country evidence without another product search',async()=>{
  productScenario='real';render(<App/>);
  await screen.findByRole('link',{name:'Visit Store ↗'});
  expect(screen.getByRole('tab',{name:'Discovery Markets'})).toHaveAttribute('aria-selected','true');
  expect(screen.getByText(/Highlighting does not verify seller location/)).toBeInTheDocument();
  const before=posts.filter(p=>p.path==='/api/products/automatic').length;
  fireEvent.click(screen.getByRole('tab',{name:'Verified Shopping Opportunities'}));
  expect(screen.getByRole('tab',{name:'Verified Shopping Opportunities'})).toHaveAttribute('aria-selected','true');
  expect(screen.getByText('No verified seller locations yet')).toBeInTheDocument();
  expect(screen.getByText('Origin Unknown')).toBeInTheDocument();
  expect(screen.queryByText(/85/)).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:'Explore Discovery Markets →'}));
  expect(screen.getByRole('tab',{name:'Discovery Markets'})).toHaveAttribute('aria-selected','true');
  expect(posts.filter(p=>p.path==='/api/products/automatic')).toHaveLength(before);
 });

 it('keeps human-verification candidates visible without offering an unverified destination link',async()=>{
  productScenario='restricted';render(<App/>);
  expect(await screen.findByRole('region',{name:'Access-unverified product candidates'})).toBeInTheDocument();
  expect(screen.getAllByText('Observed Coffee Dripper').length).toBeGreaterThan(0);
  expect(screen.getByText('Access restricted')).toBeInTheDocument();
  expect(screen.queryByRole('link',{name:'Visit Store ↗'})).not.toBeInTheDocument();
  expect(screen.getByText('Destination not verified · link disabled')).toBeInTheDocument();
  expect(screen.queryByText(/Unavailable or unconfirmed links/)).not.toBeInTheDocument();
 });
 it('keeps confirmed broken destinations in a separate unavailable group',async()=>{
  productScenario='broken';render(<App/>);
  expect(await screen.findByText('Unavailable or unsafe links (1)')).toBeInTheDocument();
  expect(screen.queryByRole('region',{name:'Access-unverified product candidates'})).not.toBeInTheDocument();
  expect(screen.queryByRole('link')).not.toBeInTheDocument();
 });

});
