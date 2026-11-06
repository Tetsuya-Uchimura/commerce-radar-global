import type {RadarState} from './useRadar';
import {FXOpportunityControls} from './FXOpportunities';
export function MapLayerControls({r}:{r:RadarState}){
 const verified=r.automatic.result?.countries.length||0;
 return <section className="map-layer-controls" aria-label="Map evidence layers"><div role="tablist" aria-label="Map layers">{(['fx','personalized','verified','discovery'] as const).map(layer=><button key={layer} role="tab" aria-selected={r.mapLayer===layer} onClick={()=>r.setMapLayer(layer)}>{{fx:'FX Advantage Map',personalized:'Personalized Opportunities',verified:'Verified Product Origins',discovery:'Discovery Markets'}[layer]}</button>)}</div><FXOpportunityControls r={r}/>
 {r.mapLayer==='discovery'?<p>Interest-led search destinations. Highlighting does not verify seller location, stock, shipping or price advantage.</p>:r.mapLayer==='verified'?<p>Only source-confirmed seller locations from reachable real-product links. Match scores do not establish cheapest delivered prices.</p>:<p>{r.mapLayer==='fx'?'Currency regions only; favorable FX does not verify a product or its origin.':'Only relevant real listings in favorable currencies. Origin Unknown may qualify by listing currency without assigning seller location.'}</p>}
 {r.mapLayer==='verified'&&verified===0&&<div className="map-layer-empty" role="status"><strong>No verified seller locations yet</strong><span>Origin Unknown products remain separate. Explore interest-based destinations instead.</span><button className="text-button" onClick={()=>r.setMapLayer('discovery')}>Explore Discovery Markets →</button></div>}
 </section>;
}
