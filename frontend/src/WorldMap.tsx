import {useEffect,useState} from 'react';
import {ComposableMap,Geographies,Geography,Marker,Graticule} from 'react-simple-maps';
import {ZoomableGroup} from 'react-simple-maps/zoom';
import {Plus,Minus,LocateFixed} from 'lucide-react';
import type {MapCountry} from './mapLayers';

export function countryColor(country:MapCountry|undefined,selected=false){
 if(selected)return country?.exploration?'#ffe3a4':'#d2fff2';
 if(country?.exploration)return '#9c874f';
 if(country?.currency_region){if(country.score===null)return '#293f51';return country.fxOpportunity?.status==='favorable'?'#8de1d6':country.fxOpportunity?.status==='unfavorable'?'#925b64':'#426b72';}
 if(!country||country.score===null)return '#293f51';
 return country.score>=80?'#8de1d6':country.score>=60?'#4f9a91':'#426b72';
}
type Props={strategy?:string;focusCurrencies?:string[];layer?:'fx'|'personalized'|'verified'|'discovery'|'demo';dataMode?:string;countries:MapCountry[];selected:string;onSelect:(code:string,name:string)=>void};
export default function WorldMap({countries,selected,onSelect,dataMode='Demo Catalog',layer='demo',strategy,focusCurrencies=[]}:Props){
 const [position,setPosition]=useState<{center:[number,number];zoom:number}>({center:[18,15],zoom:1});
 const [hover,setHover]=useState('');
 const [geoError,setGeoError]=useState(false);
 useEffect(()=>{const c=countries.find(n=>n.code===selected);setPosition(c?{center:[c.longitude,c.latitude],zoom:1.7}:{center:[18,15],zoom:1});},[selected]);
 const lookup=new Map(countries.map(c=>[String(Number(c.map_id)),c]));
 return <div className="world-map" data-testid="world-map"><div className="map-grid"/>
 <ComposableMap width={900} height={550} projection="geoEqualEarth" projectionConfig={{scale:160,center:[0,6]}} aria-label="Interactive global shopping opportunity map">
  <ZoomableGroup center={position.center} zoom={position.zoom} minZoom={1} maxZoom={6} onMoveEnd={({coordinates,zoom})=>setPosition({center:coordinates||[18,15],zoom:zoom??1})}>
   <Graticule stroke="#8de1d60a" strokeWidth={0.6}/>
   <Geographies geography="/world-110m.json" onError={()=>setGeoError(true)}>{({geographies})=>geographies.map(geo=>{
    const country=lookup.get(String(Number(geo.id)));
    const name=country?.name||String(geo.properties?.name||'Uncovered country');
    return <Geography key={geo.rsmKey} geography={geo} fill={countryColor(country,country?.code===selected)} stroke="#172b3e" strokeWidth={0.65}
     tabIndex={0} role="button" aria-label={`Explore ${name}${country?`, ${country.band}`:', Insufficient Data'}`}
     onMouseEnter={()=>setHover(name+(country?.currency_region?' · '+country.currency+' '+country.band+'; currency region, not seller origin':country?.exploration?' · Interest-led search target; seller location not verified':country?.score!=null?` · ${country.score} ${layer==='demo'?'demo opportunity match':'verified seller-location match'}`:' · No verified seller-location evidence'))} onMouseLeave={()=>setHover('')}
     onFocus={()=>setHover(name)} onBlur={()=>setHover('')}
     onClick={()=>onSelect(country?.code||'ZZ',name)} onKeyDown={event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();onSelect(country?.code||'ZZ',name);}}}
     style={{outline:'none',cursor:'pointer'}}/>;
   })}</Geographies>
   {countries.map(c=><Marker key={c.code} coordinates={[c.longitude,c.latitude]}>
    <g className="map-marker" role="button" tabIndex={0} aria-label={`Select ${c.name}`} onClick={()=>onSelect(c.code,c.name)} onKeyDown={e=>{if(e.key==='Enter')onSelect(c.code,c.name);}}>
     {(strategy==='us_stores_first'?c.code==='US':focusCurrencies.includes(c.currency))&&<circle data-strategy-focus={c.code} r={8/position.zoom} fill="none" stroke="#e6bf7b" strokeWidth={1/position.zoom}/>}<circle r={10/position.zoom} fill={countryColor(c)} opacity={0.12}/><circle r={3.2/position.zoom} fill={countryColor(c)} stroke={c.exploration?'#ffe3a4':'#d2fff2'} strokeDasharray={c.exploration?'2 1':undefined} strokeWidth={0.5/position.zoom}/>
     <text y={-13/position.zoom} textAnchor="middle" fill="#cde8e3" fontSize={9/position.zoom} letterSpacing={1/position.zoom}>{c.code}</text>
    </g>
   </Marker>)}
   <Marker coordinates={[-98,39]}><circle r={4/position.zoom} fill="#e6c38a"/><text y={15/position.zoom} fill="#d6c4a2" textAnchor="middle" fontSize={8/position.zoom}>YOUR HOME · USD</text></Marker>
  </ZoomableGroup>
 </ComposableMap>
 <div className="map-hover" aria-live="polite">{hover||'Select a country. Discover a different possibility.'}</div>
 <div className="map-controls"><button aria-label="Zoom in" onClick={()=>setPosition(p=>({...p,zoom:Math.min(6,p.zoom*1.35)}))}><Plus size={17}/></button><button aria-label="Zoom out" onClick={()=>setPosition(p=>({...p,zoom:Math.max(1,p.zoom/1.35)}))}><Minus size={17}/></button><button aria-label="Reset map view" onClick={()=>setPosition({center:[18,15],zoom:1})}><LocateFixed size={17}/></button></div>
 {geoError&&<p className="map-error">Map geometry unavailable. Use the country buttons below to continue.</p>}
 <div className="map-legend"><strong>{dataMode} · {layer==='fx'||layer==='personalized'?'currency regions, not seller origins':layer==='discovery'?'exploration targets, not verified opportunities':layer==='demo'?'fictional opportunities':'source-confirmed seller locations'}</strong>{layer==='fx'||layer==='personalized'?<><span><i style={{background:'#8de1d6'}}/>Favorable Currency</span><span><i style={{background:'#925b64'}}/>Unfavorable</span><span><i style={{background:'#293f51'}}/>Insufficient Data / no product evidence</span></>:layer==='discovery'?<><span><i style={{background:'#9c874f'}}/>Interest-led target</span><span><i style={{background:'#ffe3a4'}}/>Selected search target</span><span><i style={{background:'#293f51'}}/>Outside current routes</span></>:<><span><i style={{background:'#8de1d6'}}/>Strong match</span><span><i style={{background:'#4f9a91'}}/>Good match</span><span><i style={{background:'#426b72'}}/>Explore match</span><span><i style={{background:'#293f51'}}/>{layer==='demo'?'Insufficient demo data':'No verified seller data'}</span></>}</div>
 </div>;
}
