import type {RadarState} from './useRadar';
export function MapLayerControls({r}:{r:RadarState}){
 if(r.showingDemo)return <div className="map-layer-controls"><strong>Demo Catalog map</strong><p>Sample product data · fictional seller locations and opportunity scores.</p></div>;
 const verified=r.automatic.result?.countries.length||0;
 return <section className="map-layer-controls" aria-label="Map evidence layers"><div role="tablist" aria-label="Map layers"><button role="tab" aria-selected={r.mapLayer==='discovery'} onClick={()=>r.setMapLayer('discovery')}>Discovery Markets</button><button role="tab" aria-selected={r.mapLayer==='verified'} onClick={()=>r.setMapLayer('verified')}>Verified Shopping Opportunities</button></div>
 {r.mapLayer==='discovery'?<p>Interest-led search destinations. Highlighting does not verify seller location, stock, shipping or price advantage.</p>:<p>Only source-confirmed seller locations from reachable real-product links. Match scores do not establish cheapest delivered prices.</p>}
 {r.mapLayer==='verified'&&verified===0&&<div className="map-layer-empty" role="status"><strong>No verified seller locations yet</strong><span>Origin Unknown products remain separate. Explore interest-based destinations instead.</span><button className="text-button" onClick={()=>r.setMapLayer('discovery')}>Explore Discovery Markets →</button></div>}
 </section>;
}
