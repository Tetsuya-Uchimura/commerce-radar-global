export type LinkAccess={status:'user_pending'|'user_confirmed'|'reachable'|'restricted'|'unavailable'|'login_required'|'rate_limited'|'unconfirmed'|'unsafe';reason:string;checked_at:string;scope:string;limitation:string;cached?:boolean;http_status?:number;final_host?:string};
export function LinkStatus({access}:{access?:LinkAccess}){
 const labels={user_pending:'Awaiting user review',user_confirmed:'User-confirmed merchant',reachable:'Server reachable',restricted:'Access restricted',unavailable:'Link unavailable',login_required:'Login required',rate_limited:'Check rate-limited',unconfirmed:'Access unconfirmed',unsafe:'Unsafe link blocked'};
 if(access?.status==='user_pending')return <div className="link-access link-access--issue"><strong>Awaiting user review</strong><p className="fineprint">This merchant is not in your reviewed site list. No automated link check was performed.</p></div>;
 if(access?.status==='user_confirmed')return <div className="link-access"><strong>User-confirmed merchant</strong><p className="fineprint">Representative product link checked in your browser. This does not verify every product, seller location or purchase total.</p><small>User review: {access.checked_at.slice(0,10)} · no automated recheck</small></div>;
 return <div className={access?.status==='reachable'?'link-access':'link-access link-access--issue'}><strong>{access?labels[access.status]:'Access not checked'}</strong>{access&&<><p className="fineprint">{access.reason}</p><small>Checked {access.checked_at.slice(0,19)} UTC{access.cached?' · cached check':''}{access.http_status?' · HTTP '+access.http_status:''}</small></>}<p className="fineprint">Server check only; your browser, location and login may differ.</p></div>;
}
export function ProductLink({url,access}:{url:string;access?:LinkAccess}){
 if(access?.status!=='reachable'&&access?.status!=='user_confirmed')return <span className="product-link-disabled" aria-disabled="true">{access?.status==='unsafe'||access?.status==='unavailable'?'Destination unavailable':'Destination not verified · link disabled'}</span>;
 return <a className="button secondary" href={url} target="_blank" rel="noreferrer">Visit Store ↗</a>;
}
