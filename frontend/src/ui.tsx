import {Radar,Compass} from 'lucide-react';
import type {Filters} from './api';
export function Brand(){return <div className="brand"><span><Radar size={29} strokeWidth={1.6}/></span><div>commerce<span>radar <small>FX-DRIVEN DISCOVERY</small></span></div></div>;}
export function Empty({text}:{text:string}){return <div className="empty"><Compass size={31}/><p>{text}</p></div>;}
export function SortSelect({filters,onChange}:{filters:Filters;onChange:(f:Partial<Filters>)=>void}){return <select aria-label="Sort opportunities" value={filters.sort} onChange={e=>onChange({sort:e.target.value})}><option value="best">Best match</option><option value="fx">Best FX opportunity</option><option value="cost">Lowest estimated cost</option><option value="unique">Most unique</option><option value="recent">Recently discovered</option></select>;}
